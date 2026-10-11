from __future__ import annotations

from fastapi import APIRouter, status, HTTPException
import logging

logger = logging.getLogger("anti_detect_proxy.api")

from app.schemas.payload import HealthResponse, ScrapeRequest, ScrapeResponse
from app.services.scraper import ScraperService
from app.services.browser import BrowserService
from app.services.proxy_rotator import ProxyRotator


router = APIRouter(tags=["scraper"])
scraper_service = ScraperService()
browser_service = BrowserService()
proxy_rotator = ProxyRotator()


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.post(
    "/scrape",
    response_model=ScrapeResponse,
    status_code=status.HTTP_200_OK,
)
async def scrape(payload: ScrapeRequest) -> ScrapeResponse:
    from app.services.cleaner import html_to_markdown
    import time

    if payload.use_browser:
        start = time.perf_counter()
        html = await browser_service.fetch(str(payload.url), payload.proxy)
        elapsed_ms = (time.perf_counter() - start) * 1000
        
        content_type = "text/html; charset=utf-8"
        if payload.return_markdown:
            html = html_to_markdown(html)
            content_type = "text/markdown; charset=utf-8"

        return ScrapeResponse(
            url=str(payload.url),
            final_url=str(payload.url),
            status_code=200,
            reason="OK",
            ok=True,
            elapsed_ms=elapsed_ms,
            headers={"Content-Type": content_type},
            content_type=content_type,
            text=html,
            bytes_received=len(html)
        )
        
    response = await scraper_service.fetch(payload)
    
    # Smart Auto-Fallback: Check if request was blocked by Cloudflare/WAF or shows verification wall
    is_blocked = False
    if response.status_code in (403, 503, 429):
        is_blocked = True
    elif response.text:
        lowered_text = response.text.lower()
        waf_signatures = [
            "cloudflare", "ddos-guard", "perimeterx", "just a moment", 
            "verify you are human", "checking your browser", "please wait", 
            "verify", "robot", "captcha", "security challenge", "blocked",
            "turnstile", "hcaptcha", "recaptcha", "google.com/sorry",
            "unusual traffic", "truy cập vào google"
        ]
        if any(sig in lowered_text for sig in waf_signatures):
            is_blocked = True

    if is_blocked and payload.auto_fallback:
        # Fallback to Stealth Browser Engine to bypass security
        
        html = None
        elapsed_ms = 0
        max_retries = 3
        success = False
        proxy_url = payload.proxy
        current_proxy = None
        
        for attempt in range(max_retries):
            current_proxy = proxy_url
            if not current_proxy:
                current_proxy = await proxy_rotator.get_proxy()
                
            try:
                logger.info(f"Attempting browser fetch with proxy (Attempt {attempt+1}/{max_retries}): {current_proxy}")
                start_time = time.perf_counter()
                html = await browser_service.fetch(str(payload.url), current_proxy)
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                success = True
                break
            except Exception as e:
                logger.warning(f"Browser fetch failed with proxy {current_proxy}: {e}")
                if current_proxy and not payload.proxy:
                    await proxy_rotator.remove_proxy(current_proxy)
                if payload.proxy:
                    break  # Don't retry if it is the user's custom proxy
        
        if not success:
            # Last resort attempt: try without proxy
            try:
                logger.info("All proxies failed. Attempting final browser fetch without proxy...")
                start_time = time.perf_counter()
                html = await browser_service.fetch(str(payload.url), None)
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                success = True
                current_proxy = None
            except Exception as e:
                logger.error(f"Final browser fetch without proxy failed: {e}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Bypass failed. Downstream proxy or browser error: {str(e)}"
                )
        
        content_type = "text/html; charset=utf-8"
        if payload.return_markdown:
            html = html_to_markdown(html)
            content_type = "text/markdown; charset=utf-8"

        response_headers = {"Content-Type": content_type, "X-Bypass-Fallback": "true"}
        if current_proxy and not payload.proxy:
            response_headers["X-Fallback-Proxy-Used"] = "true"

        return ScrapeResponse(
            url=str(payload.url),
            final_url=str(payload.url),
            status_code=200,
            reason="OK (Bypassed via Auto-Fallback & Proxy)",
            ok=True,
            elapsed_ms=elapsed_ms,
            headers=response_headers,
            content_type=content_type,
            text=html,
            bytes_received=len(html)
        )

    if payload.return_markdown and response.text:
        response.text = html_to_markdown(response.text)
        response.content_type = "text/markdown; charset=utf-8"
        response.bytes_received = len(response.text)
    return response
