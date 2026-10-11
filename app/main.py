from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import os

from app.api.endpoints import router, scraper_service, browser_service, proxy_rotator
from app.core.config import settings

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))


logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

logger = logging.getLogger("anti_detect_proxy.app")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    logger.info("application startup")
    await scraper_service.start()
    await browser_service.start()
    await proxy_rotator.start()
    try:
        yield
    finally:
        logger.info("application shutdown: closing sessions")
        await proxy_rotator.stop()
        await browser_service.close()
        await scraper_service.close()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.enable_docs else None,
    redoc_url="/redoc" if settings.enable_docs else None,
    openapi_url="/openapi.json" if settings.enable_docs else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_methods,
    allow_headers=settings.cors_headers,
)


@app.middleware("http")
async def request_logging_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "%s %s -> %s %.2fms",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.2f}"
    return response


app.include_router(router, prefix=settings.api_prefix)


@app.get("/", response_class=HTMLResponse)
async def serve_frontend(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
