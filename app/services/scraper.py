from __future__ import annotations

import asyncio
import base64
import logging
import time
from collections.abc import Mapping
from typing import Any, cast, get_args

from curl_cffi import requests
from curl_cffi.requests import BrowserTypeLiteral, ProxySpec
from curl_cffi.requests.errors import RequestsError
from fastapi import HTTPException, status

from app.core.config import settings
from app.schemas.payload import ScrapeRequest, ScrapeResponse


logger = logging.getLogger("anti_detect_proxy.scraper")

SUPPORTED_IMPERSONATE = frozenset(get_args(BrowserTypeLiteral))


class ScraperService:
    def __init__(self) -> None:
        self._default_impersonate = settings.default_impersonate
        self._sessions: dict[BrowserTypeLiteral, requests.AsyncSession] = {}
        self._session_lock = asyncio.Lock()
        self._closed = False

    async def start(self) -> None:
        async with self._session_lock:
            self._closed = False

    async def fetch(self, payload: ScrapeRequest) -> ScrapeResponse:
        target_url = str(payload.url)
        impersonate = self._resolve_impersonate(payload.impersonate)
        timeout = payload.timeout_seconds or settings.request_timeout_seconds
        follow_redirects = (
            settings.follow_redirects
            if payload.follow_redirects is None
            else payload.follow_redirects
        )
        verify_tls = (
            settings.verify_tls
            if payload.verify_tls is None
            else payload.verify_tls
        )
        headers = self._build_headers(payload.headers)
        proxy_config = self._build_proxy_config(payload.proxy)
        request_kwargs = self._build_request_kwargs(payload)

        logger.info(
            "fetching url=%s method=%s impersonate=%s",
            target_url,
            payload.method,
            impersonate,
        )
        started = time.perf_counter()

        try:
            session = await self._get_session(impersonate)
            response = await session.request(
                method=payload.method,
                url=target_url,
                headers=headers,
                params=dict(payload.params),
                cookies=dict(payload.cookies),
                proxies=proxy_config,
                timeout=timeout,
                verify=verify_tls,
                allow_redirects=follow_redirects,
                default_headers=True,
                **request_kwargs,
            )
        except RequestsError as exc:
            message = str(exc)
            logger.warning(
                "request failed url=%s error=%s",
                target_url,
                message,
            )
            if self._is_timeout_error(message):
                raise HTTPException(
                    status_code=status.HTTP_408_REQUEST_TIMEOUT,
                    detail=f"upstream request timed out: {message}",
                ) from exc
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"upstream request failed: {message}",
            ) from exc
        except ValueError as exc:
            logger.warning(
                "invalid scrape payload url=%s error=%s",
                target_url,
                exc,
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc

        elapsed_ms = (time.perf_counter() - started) * 1000
        content = response.content or b""
        bytes_received = len(content)

        logger.info(
            "fetched url=%s final_url=%s status=%s bytes=%s elapsed_ms=%.2f",
            target_url,
            response.url,
            response.status_code,
            bytes_received,
            elapsed_ms,
        )

        if bytes_received > settings.max_response_bytes:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=(
                    "upstream response exceeded maximum size "
                    f"({bytes_received} > {settings.max_response_bytes} bytes)"
                ),
            )

        response_headers = self._normalize_response_headers(response.headers)
        content_type = response_headers.get("content-type")
        text: str | None = None
        base64_body: str | None = None

        if payload.return_binary:
            base64_body = base64.b64encode(content).decode("ascii")
        else:
            text = self._decode_response_text(response, content)

        return ScrapeResponse(
            url=target_url,
            final_url=str(response.url),
            status_code=response.status_code,
            reason=response.reason,
            ok=response.ok,
            elapsed_ms=round(elapsed_ms, 3),
            headers=response_headers,
            content_type=content_type,
            text=text,
            base64_body=base64_body,
            bytes_received=bytes_received,
        )

    @staticmethod
    def _resolve_impersonate(
        impersonate: str | None,
    ) -> BrowserTypeLiteral:
        resolved = (impersonate or settings.default_impersonate).strip()
        resolved = resolved or settings.default_impersonate
        if resolved not in SUPPORTED_IMPERSONATE:
            allowed = ", ".join(sorted(SUPPORTED_IMPERSONATE))
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"unsupported impersonate profile '{resolved}'. "
                    f"Allowed values: {allowed}"
                ),
            )
        return cast(BrowserTypeLiteral, resolved)

    async def _get_session(
        self,
        impersonate: BrowserTypeLiteral,
    ) -> requests.AsyncSession:
        if self._closed:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="scraper service is shutting down",
            )

        cached = self._sessions.get(impersonate)
        if cached is not None:
            return cached

        async with self._session_lock:
            if self._closed:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="scraper service is shutting down",
                )
            cached = self._sessions.get(impersonate)
            if cached is not None:
                return cached

            session = requests.AsyncSession(
                impersonate=impersonate,
                max_clients=settings.session_max_clients,
            )
            self._sessions[impersonate] = session
            logger.info(
                "created pooled AsyncSession impersonate=%s max_clients=%s",
                impersonate,
                settings.session_max_clients,
            )
            return session

    async def close(self) -> None:
        async with self._session_lock:
            self._closed = True
            sessions = tuple(self._sessions.items())
            self._sessions.clear()

        if not sessions:
            logger.info("no scraper sessions to close")
            return

        close_results = await asyncio.gather(
            *(session.close() for _, session in sessions),
            return_exceptions=True,
        )
        session_results = zip(sessions, close_results, strict=True)
        for (impersonate, _), result in session_results:
            if isinstance(result, Exception):
                logger.warning(
                    "failed to close AsyncSession impersonate=%s error=%s",
                    impersonate,
                    result,
                )
            else:
                logger.info("closed AsyncSession impersonate=%s", impersonate)

    @staticmethod
    def _build_request_kwargs(payload: ScrapeRequest) -> dict[str, Any]:
        if payload.json_body is not None:
            return {"json": payload.json_body}
        if payload.body is not None:
            return {"data": payload.body}
        return {}

    @staticmethod
    def _build_proxy_config(proxy: str | None) -> ProxySpec | None:
        if proxy is None:
            return None
        return cast(ProxySpec, {"http": proxy, "https": proxy})

    @staticmethod
    def _build_headers(
        user_headers: Mapping[str, str],
    ) -> dict[str, str] | None:
        if not user_headers:
            return None
        return dict(user_headers)

    @staticmethod
    def _normalize_response_headers(
        headers: Mapping[str, str],
    ) -> dict[str, str]:
        return {str(key).lower(): str(value) for key, value in headers.items()}

    @staticmethod
    def _decode_response_text(
        response: requests.Response,
        content: bytes,
    ) -> str:
        if not content:
            return ""
        try:
            return response.text
        except UnicodeDecodeError:
            return content.decode("utf-8", errors="replace")

    @staticmethod
    def _is_timeout_error(message: str) -> bool:
        normalized = message.lower()
        timeout_markers = (
            "timed out",
            "timeout",
            "operation timed out",
            "curl: (28)",
        )
        return any(marker in normalized for marker in timeout_markers)
