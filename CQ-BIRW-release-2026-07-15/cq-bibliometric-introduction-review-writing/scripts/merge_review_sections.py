#!/usr/bin/env python3
"""Deterministically merge approved review section drafts in section-id order."""
from __future__ import annotations

import argparse
import re
from pathlib import Path


def merge(root: Path) -> Path:
    section_dir = root / "06_review/sections"
    sections = sorted(section_dir.glob("SEC-*.md"), key=lambda path: path.name.casefold())
    if not sections:
        raise RuntimeError(f"no section drafts found in {section_dir}")
    seen: set[str] = set()
    parts = ["# LARP融入旅游景点对游客再访意愿的影响：系统性文献综述\n"]
    for path in sections:
        text = path.read_text(encoding="utf-8").strip()
        match = re.search(r"<!--\s*section:([^\s>]+)\s*-->", text)
        if not match:
            raise RuntimeError(f"section marker missing: {path}")
        section_id = match.group(1)
        if section_id in seen:
            raise RuntimeError(f"duplicate section id: {section_id}")
        seen.add(section_id)
        parts.append(text)
    output = root / "06_review/review_draft.md"
    output.write_text("\n\n".join(parts).rstrip() + "\n", encoding="utf-8")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    args = parser.parse_args()
    print(merge(Path(args.task).expanduser().resolve()))
