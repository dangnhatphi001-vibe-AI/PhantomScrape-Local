from __future__ import annotations

from typing import Any, Literal

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


HttpMethod = Literal[
    "GET",
    "POST",
    "PUT",
    "PATCH",
    "DELETE",
    "HEAD",
    "OPTIONS",
]


class ScrapeRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        json_schema_extra={
            "example": {
                "url": "https://www.reddit.com/r/python/",
                "use_browser": False,
                "auto_fallback": True,
                "return_markdown": True
            }
        }
    )

    url: AnyHttpUrl
    method: HttpMethod = "GET"
    headers: dict[str, str] = Field(default_factory=dict)
    params: dict[str, str | int | float | bool] = Field(default_factory=dict)
    cookies: dict[str, str] = Field(default_factory=dict)
    body: str | bytes | dict[str, Any] | list[Any] | None = None
    json_body: dict[str, Any] | list[Any] | None = None
    proxy: str | None = Field(
        default=None,
        description="HTTP, HTTPS, or SOCKS proxy URL.",
    )
    impersonate: str | None = Field(
        default=None,
        description="curl_cffi impersonation profile.",
    )
    timeout_seconds: float | None = Field(default=None, gt=0.0, le=300.0)
    follow_redirects: bool | None = None
    verify_tls: bool | None = None
    return_binary: bool = False
    use_browser: bool = Field(
        default=False,
        description="Set to true to use Playwright headless browser for bypassing advanced JS challenges.",
    )
    return_markdown: bool = Field(
        default=False,
        description="Set to true to convert the scraped HTML output to clean, readable Markdown (perfect for AI models).",
    )
    auto_fallback: bool = Field(
        default=True,
        description="If true and use_browser is false, automatically fallback to using the stealth browser if WAF blocks (Cloudflare, Datadog) are detected.",
    )

    @field_validator("headers")
    @classmethod
    def validate_headers(cls, value: dict[str, str]) -> dict[str, str]:
        cleaned: dict[str, str] = {}
        for key, header_value in value.items():
            normalized_key = key.strip()
            if not normalized_key:
                raise ValueError("header names must not be empty")
            if "\r" in normalized_key or "\n" in normalized_key:
                raise ValueError(
                    "header names must not contain CRLF characters",
                )
            normalized_value = str(header_value).strip()
            if "\r" in normalized_value or "\n" in normalized_value:
                raise ValueError(
                    "header values must not contain CRLF characters",
                )
            cleaned[normalized_key] = normalized_value
        return cleaned

    @field_validator("proxy")
    @classmethod
    def validate_proxy(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        valid_prefixes = ("http://", "https://", "socks4://", "socks5://")
        if not normalized.startswith(valid_prefixes):
            raise ValueError(
                "proxy must start with http://, https://, "
                "socks4://, or socks5://",
            )
        return normalized

    @model_validator(mode="after")
    def validate_body_fields(self) -> ScrapeRequest:
        if self.body is not None and self.json_body is not None:
            raise ValueError("body and json_body are mutually exclusive")
        read_methods = {"GET", "HEAD", "OPTIONS"}
        has_body = self.body is not None or self.json_body is not None
        if self.method in read_methods and has_body:
            raise ValueError(
                "request body is only supported for POST, PUT, "
                "PATCH, and DELETE",
            )
        return self


class ScrapeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    final_url: str
    status_code: int
    reason: str
    ok: bool
    elapsed_ms: float
    headers: dict[str, str]
    content_type: str | None
    text: str | None = None
    base64_body: str | None = None
    bytes_received: int


class ErrorResponse(BaseModel):
    detail: str


class HealthResponse(BaseModel):
    status: Literal["ok"]
