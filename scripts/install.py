#!/usr/bin/env python3
"""One-command interactive installer. Bootstrap uses only Python's stdlib."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone

SOURCE = Path(__file__).resolve().parents[1]
NAME = "phantom-local"
TARGETS = {
    "codex": "Codex CLI / app / IDE",
    "chatgpt": "ChatGPT desktop (MCP local, cùng cấu hình Codex)",
    "claude": "Claude Code",
    "opencode": "OpenCode",
    "cursor": "Cursor",
    "vscode": "VS Code / Copilot",
    "claude-desktop": "Claude Desktop (adapter macOS / Windows)",
}


def choose_targets() -> list[str]:
    print("\n👻 PhantomScrape — Cài web → Markdown cho AI\n", flush=True)
    keys = list(TARGETS)
    for number, key in enumerate(keys, 1):
        extra = " (trình cài chưa hỗ trợ Linux)" if key == "claude-desktop" and sys.platform.startswith("linux") else ""
        print(f"  {number}. {TARGETS[key]}{extra}")
    print("  8. Cài Codex / ChatGPT desktop + Claude Code + OpenCode")
    print("  9. ChatGPT web (cần MCP remote; bản local chưa tự kết nối được)")
    print("  0. Thoát\n")
    while True:
        try:
            answer = input("Chọn nơi cài (ví dụ: 1 hoặc 1,3,4): ").strip()
        except EOFError:
            raise ValueError("Cần terminal tương tác, hoặc dùng --targets codex,claude,opencode.")
        if answer == "0":
            return []
        if answer == "9":
            print("ChatGPT web không đọc cấu hình MCP trên máy. Chọn 2 để dùng ChatGPT desktop local.")
            continue
        if answer == "8":
            return ["codex", "claude", "opencode"]
        try:
            numbers = [int(part.strip()) for part in answer.split(",")]
            if not numbers or any(n < 1 or n > len(keys) for n in numbers):
                raise ValueError
            return list(dict.fromkeys(keys[n - 1] for n in numbers))
        except ValueError:
            print("Nhập số trong menu; chọn nhiều nơi bằng dấu phẩy.")


def run(command: list[str], label: str | None = None, **kwargs):
    if label is None:
        subprocess.run(command, check=True, **kwargs)
        return
    animated = sys.stdout.isatty()
    frames = "◐◓◑◒"
    try:
        frames.encode(sys.stdout.encoding or "utf-8")
    except UnicodeEncodeError:
        frames = "|/-\\"
    if not animated:
        print(label, flush=True)
    timeout = kwargs.pop("timeout", None)
    started = time.monotonic()
    # Keep command output away from the spinner; show it in full on failure.
    with tempfile.TemporaryFile() as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, **kwargs)
        try:
            tick = 0
            while process.poll() is None:
                if timeout is not None and time.monotonic() - started > timeout:
                    raise subprocess.TimeoutExpired(command, timeout)
                if animated:
                    print(f"\r{frames[tick % len(frames)]} {label}  {int(time.monotonic() - started)}s", end="", flush=True)
                    tick += 1
                time.sleep(0.1)
        except BaseException:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            if animated:
                print("\r" + " " * (len(label) + 25) + "\r", end="", flush=True)
            log.seek(0)
            print(log.read().decode("utf-8", errors="replace"), file=sys.stderr, end="")
            raise
        if animated:
            print("\r" + " " * (len(label) + 25) + "\r", end="", flush=True)
        if process.returncode:
            log.seek(0)
            print(log.read().decode("utf-8", errors="replace"), file=sys.stderr, end="")
            raise subprocess.CalledProcessError(process.returncode, command)
        print(f"✓ {label}", flush=True)


def default_install_dir(home: Path, platform: str | None = None, environment=None) -> Path:
    platform = platform or sys.platform
    environment = os.environ if environment is None else environment
    if platform == "win32":
        return Path(environment.get("LOCALAPPDATA", str(home / "AppData/Local"))) / NAME
    if platform == "darwin":
        return home / "Library/Application Support" / NAME
    return Path(environment.get("XDG_DATA_HOME", str(home / ".local/share"))) / NAME


def runtime_python(directory: Path, platform: str | None = None) -> Path:
    return directory / ".venv" / ("Scripts/python.exe" if (platform or sys.platform) == "win32" else "bin/python")


def setup_runtime(directory: Path, browser: bool) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    # Copy only runtime sources; no old API, secrets, output, or source .venv.
    if directory.resolve() != SOURCE.resolve():
        shutil.copytree(SOURCE / "phantom_local", directory / "phantom_local", dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        (directory / "scripts").mkdir(exist_ok=True)
        shutil.copy2(SOURCE / "scripts/run_mcp.py", directory / "scripts/run_mcp.py")
        shutil.copy2(SOURCE / "requirements-local.txt", directory / "requirements-local.txt")
        if (SOURCE / "LICENSE").is_file():
            shutil.copy2(SOURCE / "LICENSE", directory / "LICENSE")
    python = runtime_python(directory)
    if not python.is_file():
        run([sys.executable, "-m", "venv", str(directory / ".venv")], label="[1/4] Tạo môi trường Python riêng…")
    run([str(python), "-m", "pip", "install", "--disable-pip-version-check", "-q",
         "-r", str(directory / "requirements-local.txt"), "tomlkit>=0.13,<1", "json5>=0.12,<1"],
        label="[2/4] Tải và cài thư viện…")
    if browser:
        run([str(python), "-m", "playwright", "install", "chromium"], label="[3/4] Tải Chromium cho trang JavaScript…")
    else:
        print("[3/4] Bỏ tải Chromium (--no-browser); dùng mode http.", flush=True)
    # Verify handshake and discovery with the installed runtime, not source imports.
    probe = '''import asyncio, sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
async def main():
    params = StdioServerParameters(command=sys.executable, args=[sys.argv[1]])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as client:
            await client.initialize()
            names = {tool.name for tool in (await client.list_tools()).tools}
            assert {"scrape_url", "scrape_urls"} <= names
asyncio.run(main())
'''
    run([str(python), "-c", probe, str(directory / "scripts/run_mcp.py")],
        label="[4/4] Kiểm tra kết nối MCP…", timeout=30)
    return python


def write_config(path: Path, text: str) -> Path | None:
    """Back up exact bytes, preserve permissions, then atomically replace config."""
    path = path.expanduser()
    if path.is_symlink():
        path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    old = path.read_bytes() if path.exists() else None
    data = text.encode("utf-8")
    if old == data:
        return None
    backup = None
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600
    if old is not None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup = path.with_name(f"{path.name}.phantom-backup-{stamp}")
        with backup.open("xb") as handle:
            handle.write(old)
        backup.chmod(mode)
    fd, temporary = tempfile.mkstemp(prefix=".phantom-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return backup


def object_value(document, key):
    value = document.setdefault(key, {})
    if not isinstance(value, dict):
        raise ValueError(f"Mục {key!r} trong cấu hình phải là object; chưa sửa file này.")
    return value


def configure(target: str, python: Path, directory: Path, home: Path, use_environment: bool = True, platform: str | None = None):
    import json5
    import tomlkit

    script = str(directory / "scripts/run_mcp.py")
    command = str(python)
    platform = platform or sys.platform
    if target in {"codex", "chatgpt"}:
        config_dir = Path(os.environ.get("CODEX_HOME", str(home / ".codex"))) if use_environment else home / ".codex"
        path = config_dir / "config.toml"
        doc = tomlkit.parse(path.read_text(encoding="utf-8")) if path.exists() else tomlkit.document()
        if "mcp_servers" not in doc:
            doc["mcp_servers"] = tomlkit.table()
        # Preserve tool policies and per-server fields on reinstall.
        if NAME not in doc["mcp_servers"]:
            doc["mcp_servers"][NAME] = tomlkit.table()
        entry = doc["mcp_servers"][NAME]
        for field in ("url", "bearer_token_env_var", "http_headers", "oauth"):
            entry.pop(field, None)
        entry.update({"command": command, "args": [script], "enabled": True,
                      "startup_timeout_sec": 20, "tool_timeout_sec": 180})
        text = tomlkit.dumps(doc)
    else:
        if target == "claude":
            claude_dir = os.environ.get("CLAUDE_CONFIG_DIR") if use_environment else None
            path = Path(claude_dir) / ".claude.json" if claude_dir else home / ".claude.json"
            key = "mcpServers"
        elif target == "opencode":
            config_dir = Path(os.environ.get("XDG_CONFIG_HOME", str(home / ".config"))) if use_environment else home / ".config"
            config_dir /= "opencode"
            # OpenCode reads both; patch both if present so one cannot shadow the entry.
            paths = [p for p in (config_dir / "opencode.json", config_dir / "opencode.jsonc") if p.exists()]
            if not paths:
                paths = [config_dir / "opencode.json"]
            results = []
            for path in paths:
                doc = json5.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
                object_value(doc, "mcp")[NAME] = {"type": "local", "command": [command, script],
                                                  "enabled": True, "timeout": 20000}
                doc.setdefault("$schema", "https://opencode.ai/config.json")
                results.append((path, json.dumps(doc, ensure_ascii=False, indent=2) + "\n"))
            # Parse every file before writing any, so invalid JSONC doesn't partly register.
            return [(path, write_config(path, text)) for path, text in results]
        elif target == "cursor":
            path, key = home / ".cursor/mcp.json", "mcpServers"
        elif target == "vscode":
            if platform == "darwin":
                path = home / "Library/Application Support/Code/User/mcp.json"
            elif platform == "win32":
                roaming = os.environ.get("APPDATA") if use_environment else None
                path = Path(roaming or str(home / "AppData/Roaming")) / "Code/User/mcp.json"
            else:
                config_dir = Path(os.environ.get("XDG_CONFIG_HOME", str(home / ".config"))) if use_environment else home / ".config"
                path = config_dir / "Code/User/mcp.json"
            key = "servers"
        elif target == "claude-desktop":
            if platform == "darwin":
                path = home / "Library/Application Support/Claude/claude_desktop_config.json"
            elif platform == "win32":
                roaming = os.environ.get("APPDATA") if use_environment else None
                path = Path(roaming or str(home / "AppData/Roaming")) / "Claude/claude_desktop_config.json"
            else:
                raise ValueError("Adapter Claude Desktop của trình cài chỉ hỗ trợ macOS/Windows. Linux hãy chọn Claude Code.")
            key = "mcpServers"
        else:
            raise ValueError(f"Client chưa hỗ trợ: {target}")
        doc = json5.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        entry = {"command": command, "args": [script]}
        if target in {"claude", "vscode", "cursor"}:
            entry["type"] = "stdio"
        object_value(doc, key)[NAME] = entry
        text = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
    return [(path, write_config(path, text))]


def finish_install(args, targets, python, directory):
    failures = []
    print("\nĐang thêm PhantomScrape vào nơi mày chọn…", flush=True)
    configured_codex = False
    for target in targets:
        try:
            if target in {"codex", "chatgpt"} and configured_codex:
                print(f"✓ {TARGETS[target]} — dùng chung cấu hình vừa cài.")
                continue
            changes = configure(target, python, directory, args.config_home, not args.isolated_config)
            for path, backup in changes:
                print(f"✓ {TARGETS[target]}\n  {path}")
                if backup:
                    print(f"  Backup: {backup}")
            if target in {"codex", "chatgpt"}:
                configured_codex = True
        except Exception as exc:
            failures.append(target)
            print(f"✗ {TARGETS[target]}: {exc}", file=sys.stderr)
    print(f"\nCông cụ đã cài ở: {directory}")
    if failures:
        print("Chưa cài được vào: " + ", ".join(failures), file=sys.stderr)
        return 1
    print("\nXong! Mở lại / restart MCP trong app đã chọn, rồi nhắn:")
    print('  "Dùng phantom-local lấy https://example.com thành Markdown và lưu lại."')
    print("Nếu client hỏi quyền dùng MCP, bật/cho phép phantom-local.")
    return 0


def main():
    if sys.version_info < (3, 11):
        print("Cần Python 3.11 trở lên.", file=sys.stderr)
        return 1
    parser = argparse.ArgumentParser(description="Cài PhantomScrape vào AI bằng menu, không sửa config bằng tay.")
    parser.add_argument("--targets", help="Bỏ menu, ví dụ codex,chatgpt,claude,opencode hoặc all")
    parser.add_argument("--no-browser", action="store_true", help="Không tải Chromium")
    parser.add_argument("--install-dir", type=Path, default=default_install_dir(Path.home()))
    parser.add_argument("--config-home", type=Path, default=Path.home(), help="Thư mục config home khác (dùng cho kiểm thử)")
    args = parser.parse_args()
    args.isolated_config = args.config_home.resolve() != Path.home().resolve()
    try:
        if args.targets:
            targets = ["codex", "claude", "opencode"] if args.targets == "all" else list(dict.fromkeys(args.targets.split(",")))
            unknown = set(targets) - TARGETS.keys()
            if unknown:
                raise ValueError("Client không hỗ trợ: " + ", ".join(sorted(unknown)))
        else:
            targets = choose_targets()
        if not targets:
            print("Đã thoát, chưa cài gì.")
            return 0
        if targets == ["claude-desktop"] and sys.platform.startswith("linux"):
            raise ValueError("Adapter Claude Desktop hiện chỉ hỗ trợ macOS/Windows. Linux chọn Claude Code (3).")
        directory = args.install_dir.expanduser().resolve()
        python = setup_runtime(directory, browser=not args.no_browser)
        # Config parsers live inside the isolated runtime; rerun only registration there.
        if Path(sys.executable).absolute() != python.absolute():
            return subprocess.call([str(python), str(Path(__file__).resolve()), "--register",
                                    str(directory), str(args.config_home), ",".join(targets), str(args.isolated_config)])
        return finish_install(args, targets, python, directory)
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print(f"\nCài chưa hoàn tất: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nĐã hủy cài đặt.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--register":
        directory, home, targets, isolated = sys.argv[2:]
        args = argparse.Namespace(config_home=Path(home), isolated_config=isolated == "True")
        raise SystemExit(finish_install(args, targets.split(","), runtime_python(Path(directory)), Path(directory)))
    raise SystemExit(main())
