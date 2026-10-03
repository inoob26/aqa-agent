#!/usr/bin/env python3
"""Generate the runtime personas from the single source `persona/aqa.md`.

    python3 scripts/build_personas.py           write .claude/agents/aqa.md, .codex/agents/aqa.toml
    python3 scripts/build_personas.py --check   exit 1 if the generated files are out of date
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "persona" / "aqa.md"
CLAUDE_OUT = ROOT / ".claude" / "agents" / "aqa.md"
CODEX_OUT = ROOT / ".codex" / "agents" / "aqa.toml"
NOTE = "Generated from persona/aqa.md by scripts/build_personas.py — edit the source."


def parse_source(text: str) -> tuple[dict[str, str], str]:
    _, front, body = text.split("---\n", 2)
    meta: dict[str, str] = {}
    for line in front.splitlines():
        key, sep, value = line.partition(":")
        if sep:
            value = value.strip()
            meta[key.strip()] = json.loads(value) if value.startswith('"') else value
    return meta, body.strip() + "\n"


def render_claude(meta: dict[str, str], body: str) -> str:
    skills = "".join(f"  - {name.strip()}\n" for name in meta["preload_skills"].split(","))
    return (
        "---\n"
        f"name: {meta['name']}\n"
        f"description: {json.dumps(meta['description'], ensure_ascii=False)}\n"
        f"model: {meta['claude_model']}\n"
        f"skills:\n{skills}"
        "---\n"
        f"<!-- {NOTE} -->\n\n"
        f"{body}"
    )


def render_codex(meta: dict[str, str], body: str) -> str:
    if '"""' in body or "\\" in body:
        raise ValueError("persona body must not contain triple quotes or backslashes")
    return (
        f"# {NOTE}\n"
        f"name = {json.dumps(meta['name'])}\n"
        f"description = {json.dumps(meta['description'], ensure_ascii=False)}\n"
        "# No `model` pin: the agent uses the model configured in the user's Codex profile.\n"
        f"model_reasoning_effort = {json.dumps(meta['codex_reasoning_effort'])}\n"
        "\n"
        f'developer_instructions = """\n{body}"""\n'
    )


def build() -> dict[Path, str]:
    meta, body = parse_source(SOURCE.read_text(encoding="utf-8"))
    return {CLAUDE_OUT: render_claude(meta, body), CODEX_OUT: render_codex(meta, body)}


def main(argv: list[str]) -> int:
    outputs = build()
    if "--check" in argv:
        stale = [p for p, text in outputs.items()
                 if not p.exists() or p.read_text(encoding="utf-8") != text]
        for path in stale:
            print(f"out of date: {path.relative_to(ROOT)} (run scripts/build_personas.py)")
        return 1 if stale else 0
    for path, text in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
