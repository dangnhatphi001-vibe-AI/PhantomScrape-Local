from __future__ import annotations

import asyncio
import time
from dataclasses import asdict, dataclass, field
from typing import Literal
from urllib.parse import urlsplit

import httpx

from .extract import extract_markdown, is_challenge, needs_rendering

Mode = Literal["auto", "http", "browser"]
MAX_BYTES = 10 * 1024 * 1024


class ScrapeError(ValueError):
    pass


@dataclass
class Document:
    url: str
    final_url: str
    title: str
    status_code: int
    engine: str
    markdown: str
    elapsed_ms: float
    warnings: list[str] = field(default_factory=list)

    def as_result(self, max_chars: int) -> dict:
        result = asdict(self)
        result["total_chars"] = len(self.markdown)
        result["truncated"] = len(self.markdown) > max_chars
        result["markdown"] = self.markdown[:max_chars]
        return result


def validate_url(url: str) -> str:
    try:
        parsed = urlsplit(url.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError
        if parsed.username or parsed.password:
            raise ValueError
        _ = parsed.port
    except ValueError as exc:
        raise ScrapeError("Use an HTTP(S) URL without embedded credentials.") from exc
    return url.strip()


class LocalScraper:
    def __init__(self, max_bytes: int = MAX_BYTES):
        self.max_bytes = max_bytes
        self._slots = asyncio.Semaphore(3)
        self._browser_lock = asyncio.Lock()
        self._playwright = None
        self._browser = None

    async def close(self):
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    async def scrape(self, url: str, mode: Mode = "auto", timeout: float = 45) -> Document:
        url = validate_url(url)
        if mode not in {"auto", "http", "browser"}:
            raise ScrapeError("mode must be auto, http, or browser")
        if not 1 <= timeout <= 180:
            raise ScrapeError("timeout must be between 1 and 180 seconds")
        started = time.perf_counter()
        try:
            async with asyncio.timeout(timeout), self._slots:
                warnings = []
                engine = "browser" if mode == "browser" else "http"
                if mode == "browser":
                    html, final_url, status, content_type = await self._fetch_browser(url, timeout)
                else:
                    html, final_url, status, content_type = await self._fetch_http(url, timeout)
                    if mode == "auto" and (
                        status in {403, 429, 503} or is_challenge(html)
                        or ("html" in content_type and needs_rendering(html, extract_markdown(html, final_url)[1]))
                    ):
                        warnings.append(f"HTTP response ({status}) required browser rendering.")
                        html, final_url, status, content_type = await self._fetch_browser(url, timeout)
                        engine = "browser"
                if status >= 400:
                    raise ScrapeError(f"Upstream returned HTTP {status} at {final_url}.")
                if is_challenge(html):
                    raise ScrapeError("Site still presents a verification/challenge page; no article extracted.")
                if "html" in content_type:
                    title, markdown = await asyncio.to_thread(extract_markdown, html, final_url)
                elif content_type.startswith("text/"):
                    title, markdown = "", html.strip()
                else:
                    raise ScrapeError(f"Unsupported content type: {content_type or 'unknown'}; HTML/text only.")
                if not markdown:
                    raise ScrapeError("No readable content found. Try mode=browser for a JavaScript page.")
                if len(markdown) < 120:
                    warnings.append("Very little text extracted; this may be a short page or incomplete rendering.")
                return Document(url, final_url, title, status, engine, markdown,
                                round((time.perf_counter() - started) * 1000, 2), warnings)
        except TimeoutError as exc:
            raise ScrapeError(f"Request exceeded the {timeout:g}s total deadline.") from exc
        except httpx.HTTPError as exc:
            raise ScrapeError(f"HTTP request failed: {exc}") from exc

    async def _fetch_http(self, url: str, timeout: float) -> tuple[str, str, int, str]:
        # Per-call cookie jars prevent one scrape's session leaking into another.
        async with httpx.AsyncClient(
            timeout=timeout, follow_redirects=False, trust_env=False,
            headers={"User-Agent": "PhantomScrape-Local/0.1", "Accept": "text/html,text/plain;q=0.9,*/*;q=0.1"},
        ) as client:
            for _ in range(11):
                async with client.stream("GET", url) as response:
                    if response.status_code in {301, 302, 303, 307, 308} and "location" in response.headers:
                        url = validate_url(str(response.url.join(response.headers["location"])))
                        continue
                    content_type = response.headers.get("content-type", "").lower()
                    if not ("html" in content_type or content_type.startswith("text/")):
                        raise ScrapeError(f"Unsupported content type: {content_type or 'unknown'}; HTML/text only.")
                    chunks = bytearray()
                    async for chunk in response.aiter_bytes():
                        chunks.extend(chunk)
                        if len(chunks) > self.max_bytes:
                            raise ScrapeError(f"Response exceeds {self.max_bytes} bytes.")
                    # Preserve declared charset; infer when a server omits it.
                    if "charset=" in content_type:
                        text = bytes(chunks).decode(response.encoding or "utf-8", errors="replace")
                    else:
                        from charset_normalizer import from_bytes
                        decoded = from_bytes(bytes(chunks)).best()
                        text = str(decoded) if decoded is not None else bytes(chunks).decode("utf-8", errors="replace")
                    return text, str(response.url), response.status_code, content_type
            raise ScrapeError("Too many redirects (maximum 10).")

    async def _start_browser(self):
        async with self._browser_lock:
            if self._browser:
                return
            try:
                from playwright.async_api import async_playwright
            except ImportError as exc:
                raise ScrapeError("Browser mode needs Playwright: pip install playwright; playwright install chromium") from exc
            playwright = await async_playwright().start()
            try:
                browser = await playwright.chromium.launch(headless=True)
            except BaseException:
                await playwright.stop()
                raise
            self._playwright, self._browser = playwright, browser

    async def _fetch_browser(self, url: str, timeout: float) -> tuple[str, str, int, str]:
        context = None
        try:
            await self._start_browser()
            # New context isolates cookies, storage, permissions and pages per request.
            context = await self._browser.new_context(accept_downloads=False)
            page = await context.new_page()
            navigations = []

            def track_navigation(response):
                if response.request.is_navigation_request() and response.frame == page.main_frame:
                    navigations.append(response)

            page.on("response", track_navigation)
            response = await page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
            if response is None:
                raise ScrapeError("Browser navigation produced no HTTP response.")
            # Rendering can finish without networkidle (analytics may run forever).
            await page.wait_for_timeout(1200)
            await page.wait_for_function(
                "document.body && document.body.innerText.trim().length > 0", timeout=min(timeout * 1000, 5000)
            )
            response = navigations[-1] if navigations else response
            content_type = response.headers.get("content-type", "text/html").lower()
            html = await page.content() if "html" in content_type else await page.locator("body").inner_text()
            if len(html.encode("utf-8")) > self.max_bytes:
                raise ScrapeError(f"Rendered HTML exceeds {self.max_bytes} bytes.")
            return html, page.url, response.status, content_type
        except ScrapeError:
            raise
        except Exception as exc:
            raise ScrapeError(f"Browser fetch failed: {exc}. Check: python -m playwright install chromium") from exc
        finally:
            if context:
                await context.close()
