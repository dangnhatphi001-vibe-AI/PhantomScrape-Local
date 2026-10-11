from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from .engine import LocalScraper
from .storage import format_document


async def run(args):
    scraper = LocalScraper()
    try:
        document = await scraper.scrape(args.url, args.mode, args.timeout)
        if args.json:
            from dataclasses import asdict
            content = json.dumps(asdict(document), ensure_ascii=False, indent=2) + "\n"
        else:
            content = format_document(document)
        if args.output:
            path = Path(args.output).expanduser()
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w" if args.force else "x", encoding="utf-8") as handle:
                handle.write(content)
            print(f"Saved: {path.resolve()}", file=sys.stderr)
        else:
            sys.stdout.write(content)
        for warning in document.warnings:
            print(f"Warning: {warning}", file=sys.stderr)
    finally:
        await scraper.close()


def main():
    parser = argparse.ArgumentParser(description="PhantomScrape Local: web → Markdown, no paid API.")
    commands = parser.add_subparsers(dest="command", required=True)
    scrape = commands.add_parser("scrape", help="Extract one URL")
    scrape.add_argument("url")
    scrape.add_argument("--mode", choices=["auto", "http", "browser"], default="auto")
    scrape.add_argument("--timeout", type=float, default=45)
    scrape.add_argument("-o", "--output", help="Save to a file (refuses overwrite unless --force)")
    scrape.add_argument("--force", action="store_true")
    scrape.add_argument("--json", action="store_true", help="Output metadata and Markdown as JSON")
    commands.add_parser("mcp", help="Run stdio MCP server")
    config = commands.add_parser("config", help="Print client configuration with real absolute paths")
    config.add_argument("--format", choices=["json", "codex"], default="json")
    args = parser.parse_args()
    if args.command == "config":
        script = str(Path(__file__).resolve().parents[1] / "scripts" / "run_mcp.py")
        if args.format == "json":
            print(json.dumps({"mcpServers": {"phantom-local": {
                "command": sys.executable, "args": [script],
            }}}, ensure_ascii=False, indent=2))
        else:
            print('[mcp_servers.phantom-local]')
            print(f'command = {json.dumps(sys.executable)}')
            print(f'args = {json.dumps([script])}')
            print('startup_timeout_sec = 20\ntool_timeout_sec = 180')
        return
    if args.command == "mcp":
        from .server import main as serve
        serve()
        return
    try:
        asyncio.run(run(args))
    except (ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
