from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from markdownify import markdownify
import trafilatura


def extract_markdown(html: str, url: str) -> tuple[str, str]:
    """Keep article/docs structure, including code whitespace and relative links."""
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    for node in list(soup.select("script, style, noscript, iframe, svg")):
        node.decompose()
    for node in soup.select("a[href], img[src]"):
        attr = "href" if node.name == "a" else "src"
        value = str(node[attr])
        if value.lower().startswith(("javascript:", "data:")):
            del node[attr]
        else:
            node[attr] = urljoin(url, value)

    # Docs often have several articles inside one main. Keep them all.
    root = soup.find("main") or soup.find("article") or soup.find(attrs={"role": "main"})
    if root is not None:
        for node in list(root.select("nav, aside, footer, [aria-hidden='true']")):
            node.decompose()
        markdown = markdownify(str(root), heading_style="ATX", bullets="-")
    else:
        markdown = trafilatura.extract(
            str(soup), url=url, output_format="markdown", include_links=True,
            include_tables=True, include_comments=False,
        )
        if not markdown:
            for node in list(soup.select("nav, aside, footer, header")):
                node.decompose()
            markdown = markdownify(str(soup.body or soup), heading_style="ATX", bullets="-")
    # Do not strip individual lines: that destroys indentation in code blocks.
    return title, markdown.strip()


def is_challenge(html: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True).lower() if soup.title else ""
    if title in {"just a moment...", "attention required! | cloudflare", "access denied"}:
        return True
    text = soup.get_text(" ", strip=True).lower()
    # A long article mentioning CAPTCHA or robots is not a challenge page.
    return len(text) < 6000 and any(marker in text for marker in (
        "verify you are human", "checking your browser before accessing",
        "performing security verification", "enable javascript and cookies to continue",
        "our systems have detected unusual traffic",
    ))


def needs_rendering(html: str, markdown: str) -> bool:
    if len(markdown.strip()) >= 120:
        return False
    soup = BeautifulSoup(html, "html.parser")
    return bool(soup.find("script")) and (
        bool(soup.select("#root, #app, #__next"))
        or bool(re.search(r"enable javascript|requires javascript", html, re.I))
    )
