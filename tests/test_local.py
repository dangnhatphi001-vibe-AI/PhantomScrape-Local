import asyncio
import json
import os
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from phantom_local.engine import LocalScraper, ScrapeError
from phantom_local.extract import extract_markdown, is_challenge
from phantom_local.storage import save_document

ARTICLE = '''<!doctype html><html><head><title>Tài liệu Python</title></head><body>
<nav>MENU OUTSIDE</nav><main><h1>Hướng dẫn</h1><nav>MENU INSIDE</nav>
<p>Nội dung tiếng Việt để thử trích xuất. Đây là tài liệu có nội dung thực tế
đủ dài để kiểm tra việc lấy bài viết và không nhầm thành một trang chặn bot.</p>
<p><a href="/next">Trang tiếp</a></p><pre><code>def hello():
    print("xin chào")
</code></pre><table><tr><th>Tên</th><th>Giá</th></tr>
<tr><td>Local</td><td>0</td></tr></table></main><footer>FOOTER</footer></body></html>'''


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/article")
            self.end_headers()
            return
        if self.path == "/slow":
            time.sleep(2)
        code, body = 200, ARTICLE
        content_type = "text/html; charset=utf-8"
        if self.path == "/missing":
            code, body = 404, "<h1>Not found</h1>"
        elif self.path == "/challenge":
            body = "<title>Just a moment...</title><p>Verify you are human</p>"
        elif self.path == "/large":
            body = "<main>" + "x" * 5000 + "</main>"
        elif self.path == "/js":
            body = "<html><title>Rendered</title><body><div id='root'></div><script>setTimeout(() => document.getElementById('root').innerHTML = '<main><h1>JS works</h1><p>' + 'Browser rendered content. '.repeat(15) + '</p></main>', 100)</script></body></html>"
        elif self.path == "/js-redirect":
            body = "<html><body>Redirecting<script>location.replace('/missing')</script></body></html>"
        elif self.path == "/set-cookie":
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Set-Cookie", "secret=first; Path=/")
            self.end_headers()
            self.wfile.write(ARTICLE.encode())
            return
        elif self.path == "/cookie":
            body = "<main><p>" + (self.headers.get("Cookie") or "NO COOKIE") + "</p></main>"
        elif self.path == "/plain":
            body = "Nội dung Markdown\n\n    giữ thụt dòng"
            content_type = "text/markdown; charset=utf-8"
        elif self.path == "/binary":
            body, content_type = "%PDF-1.4", "application/pdf"
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.end_headers()
        try:
            self.wfile.write(body.encode())
        except BrokenPipeError:
            pass


@pytest.fixture(scope="module")
def base_url():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()
    thread.join()


def test_extraction_structure():
    title, md = extract_markdown(ARTICLE, "https://example.com/docs/start")
    assert title == "Tài liệu Python"
    assert "MENU" not in md and "FOOTER" not in md
    assert "Nội dung tiếng Việt" in md
    assert "https://example.com/next" in md
    assert '    print("xin chào")' in md
    assert "| Tên | Giá |" in md


def test_article_mentions_are_not_challenges():
    assert not is_challenge("<article>How to verify a robot, CAPTCHA and Cloudflare explained.</article>")
    assert is_challenge("<title>Just a moment...</title>")


def test_http_metadata_storage_and_isolation(base_url, tmp_path):
    async def run():
        scraper = LocalScraper()
        try:
            doc = await scraper.scrape(base_url + "/redirect", "http")
            assert doc.final_url == base_url + "/article"
            assert doc.status_code == 200 and doc.engine == "http"
            assert doc.as_result(10)["truncated"]
            first = save_document(doc, tmp_path)
            second = save_document(doc, tmp_path)
            assert first != second
            assert doc.markdown in first.read_text()
            await scraper.scrape(base_url + "/set-cookie", "http")
            clean = await scraper.scrape(base_url + "/cookie", "http")
            assert "NO COOKIE" in clean.markdown
            plain = await scraper.scrape(base_url + "/plain", "http")
            assert "    giữ thụt dòng" in plain.markdown
            assert scraper._browser is None
        finally:
            await scraper.close()
    asyncio.run(run())


@pytest.mark.parametrize("path,error", [("/missing", "HTTP 404"), ("/challenge", "challenge"), ("/binary", "Unsupported content type")])
def test_errors_are_not_successes(base_url, path, error):
    async def run():
        scraper = LocalScraper()
        try:
            with pytest.raises(ScrapeError, match=error):
                await scraper.scrape(base_url + path, "http")
        finally:
            await scraper.close()
    asyncio.run(run())


def test_response_limit_and_deadline(base_url):
    async def run():
        scraper = LocalScraper(max_bytes=1000)
        try:
            with pytest.raises(ScrapeError, match="exceeds"):
                await scraper.scrape(base_url + "/large", "http")
            with pytest.raises(ScrapeError, match="deadline"):
                await scraper.scrape(base_url + "/slow", "http", timeout=1)
        finally:
            await scraper.close()
    asyncio.run(run())


def test_browser_auto_rendering_status_and_cookies(base_url):
    async def run():
        scraper = LocalScraper()
        try:
            doc = await scraper.scrape(base_url + "/js")
            assert doc.engine == "browser" and "JS works" in doc.markdown
            with pytest.raises(ScrapeError, match="HTTP 404"):
                await scraper.scrape(base_url + "/missing", "browser")
            with pytest.raises(ScrapeError, match="HTTP 404"):
                await scraper.scrape(base_url + "/js-redirect", "browser")
            with pytest.raises(ScrapeError, match="challenge"):
                await scraper.scrape(base_url + "/challenge", "browser")
            redirect = await scraper.scrape(base_url + "/redirect", "browser")
            assert redirect.final_url == base_url + "/article"
            await scraper.scrape(base_url + "/set-cookie", "browser")
            clean = await scraper.scrape(base_url + "/cookie", "browser")
            assert "NO COOKIE" in clean.markdown
            plain = await scraper.scrape(base_url + "/plain", "browser")
            assert plain.markdown == "Nội dung Markdown\n\n    giữ thụt dòng"
        finally:
            await scraper.close()
    asyncio.run(run())


def test_cli_output_and_overwrite(base_url, tmp_path):
    output = tmp_path / "page.md"
    command = [sys.executable, "-m", "phantom_local", "scrape", base_url + "/article", "--mode", "http", "-o", str(output)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert "Nội dung tiếng Việt" in output.read_text()
    duplicate = subprocess.run(command, capture_output=True, text=True, timeout=15)
    assert duplicate.returncode == 1
    failed = subprocess.run([sys.executable, "-m", "phantom_local", "scrape", base_url + "/missing", "--mode", "http"], capture_output=True, text=True, timeout=15)
    assert failed.returncode == 1 and failed.stdout == ""


def test_mcp_stdio_discovery_calls_and_batch_errors(base_url, tmp_path):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    async def run():
        config = json.loads(subprocess.check_output([sys.executable, "-m", "phantom_local", "config"], text=True))
        generated = config["mcpServers"]["phantom-local"]
        params = StdioServerParameters(command=generated["command"], args=generated["args"],
            cwd=str(tmp_path), env={**os.environ, "PHANTOM_OUTPUT_DIR": str(tmp_path / "saved")})
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as client:
                await client.initialize()
                listing = await client.list_tools()
                assert {tool.name for tool in listing.tools} == {"scrape_url", "scrape_urls"}
                good = await client.call_tool("scrape_url", {"url": base_url + "/article", "mode": "http", "save": True})
                assert not good.isError
                data = good.structuredContent
                assert "Nội dung tiếng Việt" in data["markdown"]
                assert Path(data["saved_path"]).is_file()
                bad = await client.call_tool("scrape_url", {"url": base_url + "/missing", "mode": "http"})
                assert bad.isError
                batch = await client.call_tool("scrape_urls", {"urls": [base_url + "/article", base_url + "/missing"], "mode": "http"})
                assert not batch.isError
                assert "markdown" in batch.structuredContent["results"][0]
                assert "HTTP 404" in batch.structuredContent["results"][1]["error"]
                invalid = await client.call_tool("scrape_urls", {"urls": []})
                assert invalid.isError
    asyncio.run(run())
