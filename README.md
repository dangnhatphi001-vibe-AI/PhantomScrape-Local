# PhantomScrape Local

[![License: PolyForm Noncommercial 1.0.0](https://img.shields.io/badge/License-PolyForm_Noncommercial_1.0.0-blue.svg)](LICENSE)

Công cụ lấy web thành Markdown cho AI, chạy trên máy của bạn, không cần thuê scraping API.

## Cài bằng một lệnh

**macOS / Linux** — mở terminal Bash ở bất kỳ thư mục nào, dán:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/dangnhatphi001-vibe-AI/PhantomScrape-Local/main/install.sh)
```

**Windows** — mở PowerShell, dán:

```powershell
irm https://raw.githubusercontent.com/dangnhatphi001-vibe-AI/PhantomScrape-Local/main/install.ps1 | iex
```

Nhập số chọn nơi cài:

```text
1. Codex CLI / app / IDE
2. ChatGPT desktop (MCP local)
3. Claude Code
4. OpenCode
5. Cursor
6. VS Code / Copilot (profile mặc định)
7. Claude Desktop (adapter macOS / Windows)
8. Cài Codex / ChatGPT desktop + Claude Code + OpenCode
9. ChatGPT web — cần kết nối remote riêng
0. Thoát
```

Có thể chọn nhiều nơi: `1,3,4`. Trình cài tự tạo môi trường, tải thư viện và Chromium,
kiểm tra kết nối MCP, rồi thêm cấu hình. Terminal tương tác hiện vòng xoay `◐ ◓ ◑ ◒`
và thời gian chờ ở các bước cài. Nếu gặp lỗi, log được hiện đầy đủ.
Sau khi xong, mở lại app / restart MCP.
Nếu app yêu cầu xác nhận quyền dùng công cụ, bật `phantom-local`.

Nhắn cho AI:

> Dùng phantom-local lấy https://example.com thành Markdown và lưu lại.

Cần Python 3.11+ có hỗ trợ venv/pip và kết nối Internet khi cài lần đầu.
Windows tự tìm `py`, `python3`, `python`; nếu chưa có Python thì cần cài từ
[python.org](https://www.python.org/downloads/) rồi chạy lại. macOS dùng `python3`;
bản Python đi kèm hệ điều hành có thể quá cũ. Bản cài không cần quyền admin.
Trình cài thêm công cụ vào app đã có; không cài thay Codex/Claude/OpenCode.

## Cài thẳng, không hiện menu

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/dangnhatphi001-vibe-AI/PhantomScrape-Local/main/install.sh) --targets codex,claude,opencode
```

macOS/Linux: lệnh GitHub ở trên tự tải source, không cần clone repo trước.
Nếu đã tải source: `bash install.sh`.
Windows, nếu đã tải source: `.\install.ps1` hoặc `python scripts/install.py`.

Công cụ được copy vào thư mục riêng, độc lập với source:

| Hệ điều hành | Thư mục cài mặc định |
| --- | --- |
| Windows | `%LOCALAPPDATA%\phantom-local` |
| macOS | `~/Library/Application Support/phantom-local` |
| Linux | `~/.local/share/phantom-local` (hoặc theo `XDG_DATA_HOME`) |

Cấu hình cũ có bản sao lưu cạnh file trước khi sửa;
TOML giữ comment, JSON/JSONC giữ các giá trị khác và được chuẩn hóa thành JSON.
Chạy lại installer để cập nhật bản local. File Markdown được lưu vào `output/`
bên trong thư mục cài.

Codex và ChatGPT desktop trên cùng host dùng chung cấu hình MCP. ChatGPT web
không tự đọc cấu hình local; lựa chọn 9 chỉ giải thích giới hạn, không giả báo cài thành công.
Nguồn: [OpenAI MCP](https://learn.chatgpt.com/docs/extend/mcp?surface=cli).

Có adapter cấu hình cho các client trên. Đã kiểm thử cài trong môi trường cô lập,
handshake MCP, bảo toàn cấu hình cũ và runtime trên Linux; chưa thử UI của từng app
hay chạy installer trên macOS/Windows. PowerShell được kiểm tra riêng trên Linux;
các đường dẫn cấu hình Windows/macOS được kiểm thử bằng fixture.

## License

**PolyForm Noncommercial License 1.0.0** — Copyright 2026 Dang Nhat Phi.

Toàn văn license riêng của dự án nằm trong [LICENSE](LICENSE), gồm Required Notice
của tác giả. Trình cài cũng giữ một bản LICENSE trong thư mục công cụ đã cài.

Tài liệu kỹ thuật/CLI: [LOCAL-advanced.md](docs/LOCAL-advanced.md).
README API cũ: [README-legacy.md](docs/README-legacy.md).
Nguồn cấu hình: [Claude Code](https://code.claude.com/docs/en/mcp),
[OpenCode](https://opencode.ai/docs/mcp-servers/),
[Cursor](https://cursor.com/docs/mcp),
[VS Code](https://code.visualstudio.com/docs/agent-customization/mcp-servers).

## Kiểm thử

```bash
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
python -m pytest -q
```
