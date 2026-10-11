# PhantomScrape Local

Biến dự án PhantomScrape cũ thành công cụ **web → Markdown chạy trên máy**, dùng
qua CLI hoặc MCP local. Không gọi LLM, không cần API key, subscription scraper,
dịch vụ proxy hay máy chủ riêng. Vẫn dùng mạng, CPU/RAM và IP của máy bạn.

## Chạy ngay

Python 3.11+ được khuyến nghị (đã thử trên Python 3.14 / Linux).

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-local.txt
python -m playwright install chromium
```

Chromium chỉ khởi động khi cần render JavaScript. Nếu chỉ dùng `--mode http`,
bạn không cần tải Chromium. Windows: dùng `.venv\Scripts\activate` và `python`
thay cho `python3`; CLI và entrypoint Python của MCP không phụ thuộc Bash.

```bash
# Xuất Markdown đầy đủ xuống file
python -m phantom_local scrape https://docs.python.org/3/tutorial/introduction.html -o output/python.md

# Chỉ dùng HTTP hoặc chủ động render JavaScript
python -m phantom_local scrape https://example.com --mode http
python -m phantom_local scrape https://example.com --mode browser --timeout 60

# Metadata, URL cuối, status thật, warnings và Markdown
python -m phantom_local scrape https://example.com --json
```

Không ghi đè file đã có, trừ khi thêm `--force`. Lỗi trả exit code 1 và thông báo
ở stderr; stdout chỉ chứa nội dung khi thành công.

## Gắn vào AI/client qua MCP

MCP là giao thức cho **client/agent gọi công cụ**, không phụ thuộc hãng hoặc model.
Client cần hỗ trợ khởi chạy MCP local qua **stdio**. Web/mobile/cloud client không
thể tự chạy process trên máy bạn; bản này chưa có remote hosting hoặc tunnel.

Sinh cấu hình chứa đường dẫn tuyệt đối của máy hiện tại:

```bash
# Mẫu mcpServers cho client dùng cấu hình JSON
python -m phantom_local config

# Mẫu TOML cho Codex
python -m phantom_local config --format codex
```

Copy **entry `phantom-local`** vào cấu hình MCP hiện có của client, thay vì thay
toàn bộ file. Một số client có cấu trúc khác (ví dụ `servers` hoặc `type: stdio`);
giữ nguyên `command` và `args` được sinh ra, đặt vào cấu trúc client yêu cầu.
Đường dẫn phải được sinh lại nếu bạn chuyển thư mục hoặc tạo lại virtualenv.
Các mẫu của máy này nằm trong `docs/mcp-client.json` và `docs/codex-mcp.toml`.

Với Codex, thêm đoạn TOML vào `~/.codex/config.toml`, hoặc dùng CLI:

```bash
codex mcp add phantom-local -- /absolute/path/.venv/bin/python /absolute/path/scripts/run_mcp.py
codex mcp list
```

Reload MCP/client sau khi thêm cấu hình. Hướng dẫn nguồn:
[Codex MCP](https://developers.openai.com/codex/mcp),
[MCP Python SDK v1](https://github.com/modelcontextprotocol/python-sdk/tree/v1.x).
Bản này ghim SDK v1.30.0, tránh đổi API khi tự nâng sang v2.

Hai tool:

| Tool | Công dụng |
| --- | --- |
| `scrape_url` | Lấy một URL thành Markdown, có title, final URL, status, thời gian và warnings |
| `scrape_urls` | Lấy 1–10 URL chỉ định, tối đa 3 request đồng thời; lỗi từng trang được trả riêng |

Tham số chung: `mode="auto" | "http" | "browser"`, `timeout_seconds=45`
(1–180 giây), `max_chars` (1.000–100.000 ký tự mỗi trang), `save=false`.
`scrape_url` mặc định trả tối đa 20.000 ký tự; batch mặc định 10.000 mỗi trang.
Timeout tính từ lúc gọi, bao gồm thời gian chờ slot và browser fallback.

`save=true` lưu **toàn bộ** nội dung, kể cả khi kết quả trả về AI bị cắt.
Kết quả có `truncated`, `total_chars`, và `saved_path` nếu có lưu.
Thư mục mặc định: `output/` trong dự án; đổi qua biến môi trường
`PHANTOM_OUTPUT_DIR` của MCP server. MCP không nhận đường dẫn ghi file tùy ý;
tên file được sinh từ title và URL, không ghi đè bản cũ.

Ví dụ yêu cầu cho AI:

> Dùng phantom-local lấy 3 URL này thành Markdown, lưu bản đầy đủ trên máy,
> rồi tổng hợp thông tin. Chọn mode auto; báo rõ trang nào không truy cập được.

## Cách hoạt động và giới hạn

1. HTTP tải HTML/text với TLS verification, theo tối đa 10 redirect, giới hạn
   10 MiB **nội dung đã giải nén** trong khi stream.
2. `auto` dùng Chromium khi nhận trang chặn hoặc nhận diện được khung app cần JS.
   Phát hiện này là heuristic; có thể cần chỉ định `browser` cho một số website.
3. Trích phần `main`/`article`, giữ heading, link tuyệt đối, bảng và code block.
   Trang không có cấu trúc này dùng Trafilatura rồi fallback Markdownify.
4. Trả lỗi khi HTTP thất bại hoặc vẫn gặp trang verification; không giả báo bypass thành công.

Browser dùng context mới cho từng request, không chia sẻ cookies/storage, không
dùng profile trình duyệt cá nhân. Không dùng free proxy pool hoặc solver CAPTCHA.
Đây là scraper GET cho HTML/text; chưa xử lý PDF/OCR, đăng nhập, click, infinite
scroll hoặc crawl toàn domain. Trang có paywall, CAPTCHA, chặn IP hoặc cần tài
khoản có thể không lấy được. Bản HTTP mới dùng HTTPX, chưa dùng TLS impersonation
của engine legacy. Browser giới hạn DOM trả về và thời gian chạy, nhưng chưa giới
hạn tổng tải tài nguyên/CPU của một trang.

Nội dung web là dữ liệu nguồn không đáng tin cậy, không phải hướng dẫn cho AI.
MCP chạy local với quyền mạng của máy (kể cả web nội bộ nếu URL trỏ tới đó).

## Kiểm thử

```bash
python -m pip install 'pytest>=8,<10'
python -m pytest -q
```

Test dùng HTTP server fixture và Chromium thật: tiếng Việt, code/bảng/link,
redirect, cookie isolation, JS fallback, HTTP 404, challenge, giới hạn dung lượng,
timeout, ghi file, CLI và handshake/discovery/tool calls qua stdio MCP.

## Code cũ

`app/` và `requirements.txt` vẫn là bản API FastAPI cũ. MCP/CLI mới nằm trong
`phantom_local/` và dùng `requirements-local.txt`, không import API hoặc tự chạy
proxy harvester. Không cài chung hai bộ dependency vào một virtualenv.
README cũ được giữ ở `docs/README-legacy.md` để tham khảo; các tuyên bố bypass
99,9–100% của tài liệu cũ không phải cam kết của bản local.

`plugin.json` và `mcp.json` là metadata nguồn cho host hỗ trợ Agent Plugins.
Chưa upload/publish hay tự cài vào client. Kết nối stdio trực tiếp là đường dùng
đã được kiểm thử; khả năng cài plugin phụ thuộc host và môi trường Python đi kèm.
