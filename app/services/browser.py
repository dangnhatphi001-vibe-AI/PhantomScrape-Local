from __future__ import annotations

import asyncio
import logging

from playwright.async_api import async_playwright, Browser, BrowserContext, Playwright
from playwright_stealth import Stealth


logger = logging.getLogger("anti_detect_proxy.browser")


from urllib.parse import urlparse

def parse_playwright_proxy(proxy_url: str | None) -> dict | None:
    if not proxy_url:
        return None
    try:
        parsed = urlparse(proxy_url)
        server = f"{parsed.scheme}://{parsed.hostname}"
        if parsed.port:
            server += f":{parsed.port}"
        
        pw_proxy = {"server": server}
        if parsed.username:
            pw_proxy["username"] = parsed.username
        if parsed.password:
            pw_proxy["password"] = parsed.password
        return pw_proxy
    except Exception:
        return None


class BrowserService:
    def __init__(self) -> None:
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._lock = asyncio.Lock()
        self._closed = False

    async def start(self) -> None:
        async with self._lock:
            if self._playwright is not None:
                return
            self._closed = False
            logger.info("starting playwright browser engine...")
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"],
            )
            self._context = await self._browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
            )
            logger.info("playwright browser started successfully.")

    async def close(self) -> None:
        async with self._lock:
            self._closed = True
            logger.info("closing playwright browser engine...")
            if self._context:
                await self._context.close()
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
            self._context = None
            self._browser = None
            self._playwright = None

    async def fetch(self, url: str, proxy_url: str | None = None) -> str:
        if self._browser is None:
            raise RuntimeError("BrowserService is not started")

        is_temp_context = False
        context = self._context

        if proxy_url:
            proxy_config = parse_playwright_proxy(proxy_url)
            if proxy_config:
                logger.info("creating dynamic browser context with proxy: %s", proxy_config["server"])
                context = await self._browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    viewport={"width": 1920, "height": 1080},
                    proxy=proxy_config
                )
                is_temp_context = True

        if context is None:
            raise RuntimeError("Browser context is not initialized")

        page = await context.new_page()
        # Apply stealth to bypass bot detection (Cloudflare, Reddit JS Challenge)
        await Stealth().apply_stealth_async(page)
        
        try:
            logger.info("navigating to %s with playwright...", url)
            # Use networkidle to ensure the JS has finished loading resources
            await page.goto(url, wait_until="networkidle", timeout=30000)
            
            title = await page.title()
            
            # Wait longer if a known JS challenge is detected
            if "Just a moment..." in title or "Please wait" in title:
                logger.info("detected JS challenge. Waiting 5s for JS resolution...")
                await page.wait_for_timeout(5000)
            else:
                # Give it a second to render dynamic content
                await page.wait_for_timeout(1500)
                
            # Await page state again in case of dynamic redirects
            await page.wait_for_load_state("domcontentloaded")
            content = await page.content()
            return content
        finally:
            await page.close()
            if is_temp_context:
                await context.close()
