#!/usr/bin/env python3
"""Build the skills-only archive uploaded to the OpenAI plugin portal."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "samsin-saju"
OUTPUT = Path(__file__).resolve().parent / "samsin-saju-openai.zip"
ARCHIVE_ROOT = "samsin-saju"

EXCLUDED_PARTS = {"__pycache__", ".pytest_cache", "tests"}
EXCLUDED_TOP_LEVEL = {"docs", "agents"}
EXCLUDED_FILES = {
    "quality_contract.py",
    "test_mbti_engine.py",
}


def should_include(path: Path) -> bool:
    rel = path.relative_to(PLUGIN_ROOT)
    if rel.parts and rel.parts[0] in EXCLUDED_TOP_LEVEL:
        return False
    if any(part in EXCLUDED_PARTS for part in rel.parts):
        return False
    if path.name in EXCLUDED_FILES or path.suffix in {".pyc", ".pyo"}:
        return False
    return True


def validate_source() -> None:
    required = [
        PLUGIN_ROOT / ".claude-plugin" / "plugin.json",
        PLUGIN_ROOT / ".codex-plugin" / "plugin.json",
        PLUGIN_ROOT / "skills" / "saju-reading" / "SKILL.md",
        PLUGIN_ROOT / "skills" / "saju-reading" / "scripts" / "saju_engine.py",
        PLUGIN_ROOT / "assets" / "icon.png",
        PLUGIN_ROOT / "assets" / "logo.png",
        PLUGIN_ROOT / "LICENSE",
        PLUGIN_ROOT / "THIRD_PARTY_NOTICES.md",
    ]
    missing = [
        str(path.relative_to(REPO_ROOT)) for path in required if not path.is_file()
    ]
    if missing:
        raise SystemExit("Missing required package files:\n- " + "\n- ".join(missing))

    for manifest_path in required[:2]:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not data.get("description"):
            raise SystemExit(f"Manifest description is empty: {manifest_path}")


def build() -> None:
    validate_source()
    OUTPUT.unlink(missing_ok=True)
    files = sorted(
        path
        for path in PLUGIN_ROOT.rglob("*")
        if path.is_file() and should_include(path)
    )
    with zipfile.ZipFile(OUTPUT, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            relative = path.relative_to(PLUGIN_ROOT)
            archive.write(path, f"{ARCHIVE_ROOT}/{relative.as_posix()}")

    digest = hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
    size_kb = OUTPUT.stat().st_size / 1024
    print(f"Built {OUTPUT.relative_to(REPO_ROOT)}")
    print(f"Files: {len(files)} | Size: {size_kb:.1f} KiB")
    print(f"SHA256: {digest}")


if __name__ == "__main__":
    build()
