"""Consistency of the agent's configuration: skills, personas, plugin manifest, docs."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

import build_personas

ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / ".agents" / "skills"
SKILLS = sorted(p.name for p in SKILLS_DIR.iterdir() if (p / "SKILL.md").is_file())
OURS = {"aqa-workflow", "aqa-cases", "aqa-generate", "aqa-verify", "python-test-automation"}

# Upstream skills that the vendored copies mention but this bundle does not ship.
# `aqa-workflow` tells the agent how to treat them; a name outside this list is a typo.
NOT_BUNDLED = {
    "accessibility-testing", "agentic-browser-testing", "ai-bug-triage", "ai-qa-review",
    "ai-system-testing", "ci-cd-integration", "contract-testing", "coverage-analysis",
    "cypress-automation", "qa-metrics", "qa-start", "release-readiness", "risk-based-testing",
    "selector-drift-recovery", "shift-left-testing", "test-data-management", "test-strategy",
    "visual-testing",
}


def front_matter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path} has no front matter"
    block = text.split("---\n", 2)[1]
    fields: dict[str, str] = {}
    key = ""
    for line in block.splitlines():
        match = re.match(r"^([A-Za-z_-]+):\s*(.*)$", line)
        if match:
            key = match.group(1)
            fields[key] = match.group(2)
        elif key:
            fields[key] += " " + line.strip()
    return fields


def related(description: str) -> set[str]:
    match = re.search(r"Related:\s*([^.]+)\.", description)
    return {name.strip() for name in match.group(1).split(",")} if match else set()


def test_expected_skills_are_present() -> None:
    assert set(SKILLS) >= OURS
    assert {"unit-testing", "test-reliability", "ai-test-generation"} <= set(SKILLS)


@pytest.mark.parametrize("skill", SKILLS)
def test_skill_front_matter(skill: str) -> None:
    fields = front_matter(SKILLS_DIR / skill / "SKILL.md")
    assert fields["name"] == skill
    assert len(fields["description"]) > 80
    assert "Use when" in fields["description"]


@pytest.mark.parametrize("skill", SKILLS)
def test_skill_reference_files_exist(skill: str) -> None:
    text = (SKILLS_DIR / skill / "SKILL.md").read_text(encoding="utf-8")
    for relative in set(re.findall(r"`((?:references|scripts)/[\w./-]+\.\w+)`", text)):
        assert (SKILLS_DIR / skill / relative).is_file(), f"{skill}: missing {relative}"


@pytest.mark.parametrize("skill", SKILLS)
def test_related_skills_resolve(skill: str) -> None:
    names = related(front_matter(SKILLS_DIR / skill / "SKILL.md")["description"])
    unknown = names - set(SKILLS) - (set() if skill in OURS else NOT_BUNDLED)
    assert not unknown, f"{skill}: Related names that are neither bundled nor known upstream"


def test_not_bundled_list_is_accurate() -> None:
    assert not NOT_BUNDLED & set(SKILLS), "a skill was vendored: drop it from NOT_BUNDLED"


def test_personas_are_generated_from_the_source() -> None:
    for path, expected in build_personas.build().items():
        assert path.read_text(encoding="utf-8") == expected, (
            f"{path.relative_to(ROOT)} is stale: run scripts/build_personas.py"
        )


def test_persona_names_every_skill() -> None:
    meta, body = build_personas.parse_source(build_personas.SOURCE.read_text(encoding="utf-8"))
    for skill in SKILLS:
        assert skill in body, f"persona/aqa.md does not mention {skill}"
    for skill in meta["preload_skills"].split(","):
        assert skill.strip() in SKILLS


@pytest.mark.parametrize("doc", ["README.md", ".agents/skills/aqa-workflow/SKILL.md"])
def test_docs_name_every_skill(doc: str) -> None:
    text = (ROOT / doc).read_text(encoding="utf-8")
    missing = [s for s in SKILLS if f"`{s}`" not in text and s != "aqa-workflow"]
    assert not missing, f"{doc} does not mention: {missing}"


def test_plugin_manifest_points_at_real_paths() -> None:
    manifest = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    for key in ("skills", "agents"):
        for relative in manifest[key]:
            assert relative.startswith("./")
            assert (ROOT / relative).exists(), f"plugin.json {key}: {relative}"
    marketplace = json.loads(
        (ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
    )
    assert [p["name"] for p in marketplace["plugins"]] == [manifest["name"]]
    project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert f'version = "{manifest["version"]}"' in project


def test_hook_command_points_at_the_linter() -> None:
    hooks = json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    command = hooks["hooks"]["PostToolUse"][0]["hooks"][0]["command"]
    match = re.search(r"\$\{CLAUDE_PLUGIN_ROOT\}/([\w./-]+)", command)
    assert match and (ROOT / match.group(1)).is_file()


def test_claude_skills_symlink() -> None:
    link = ROOT / ".claude" / "skills"
    assert link.is_symlink() and link.resolve() == SKILLS_DIR.resolve()
