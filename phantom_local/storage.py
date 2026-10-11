from __future__ import annotations

import hashlib
import re
from pathlib import Path

from .engine import Document


def format_document(document: Document) -> str:
    heading = f"# {document.title}\n\n" if document.title and not document.markdown.startswith("# ") else ""
    return f"{heading}Source: <{document.final_url}>\n\n{document.markdown}\n"


def save_document(document: Document, directory: Path) -> Path:
    directory = directory.expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^\w-]+", "-", document.title or "page").strip("-")[:70] or "page"
    digest = hashlib.sha256(document.final_url.encode()).hexdigest()[:10]
    # Exclusive creation avoids overwriting existing notes or following file symlinks.
    for version in range(10000):
        suffix = f"-{version}" if version else ""
        path = directory / f"{slug}-{digest}{suffix}.md"
        try:
            with path.open("x", encoding="utf-8") as handle:
                handle.write(format_document(document))
            return path
        except FileExistsError:
            continue
    raise ValueError("Too many saved copies of this document.")
