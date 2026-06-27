"""Discovery and progressive-disclosure access for Sentinel skills.

A skill is a folder under ``skills/`` containing a ``SKILL.md`` file with YAML
frontmatter (id, name, when_to_use, optional datasets) plus an optional
``data/`` directory of CSV seed files. This module reads that structure and
builds the catalog string injected into the agent's system prompt.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import yaml

logger = logging.getLogger(__name__)

# agent/skills_registry.py -> repo root is two levels up
SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"

_FRONTMATTER_DELIM = "---"


@dataclass
class SkillMeta:
    id: str
    name: str
    when_to_use: str
    datasets: List[str] = field(default_factory=list)
    path: Path = None  # path to the skill directory


def _split_frontmatter(text: str) -> tuple[dict, str]:
    """Split a SKILL.md into (frontmatter dict, markdown body).

    Expects the file to start with a ``---`` delimited YAML block.
    """
    stripped = text.lstrip()
    if not stripped.startswith(_FRONTMATTER_DELIM):
        return {}, text
    # Drop the leading delimiter, then split on the next one.
    after_first = stripped[len(_FRONTMATTER_DELIM):]
    end = after_first.find("\n" + _FRONTMATTER_DELIM)
    if end == -1:
        return {}, text
    fm_text = after_first[:end]
    body = after_first[end + len("\n" + _FRONTMATTER_DELIM):]
    data = yaml.safe_load(fm_text) or {}
    return data, body.lstrip("\n")


def discover_skills(skills_dir: Path = SKILLS_DIR) -> List[SkillMeta]:
    """Scan ``skills_dir`` for skill folders and parse their frontmatter."""
    skills: List[SkillMeta] = []
    if not skills_dir.exists():
        logger.warning("Skills dir not found: %s", skills_dir)
        return skills

    for child in sorted(skills_dir.iterdir()):
        skill_md = child / "SKILL.md"
        if not child.is_dir() or not skill_md.exists():
            continue
        try:
            fm, _ = _split_frontmatter(skill_md.read_text(encoding="utf-8"))
            skills.append(
                SkillMeta(
                    id=fm.get("id", child.name),
                    name=fm.get("name", child.name),
                    when_to_use=(fm.get("when_to_use") or "").strip(),
                    datasets=list(fm.get("datasets") or []),
                    path=child,
                )
            )
        except Exception as exc:  # noqa: BLE001 - one bad skill must not break discovery
            logger.error("Failed to parse skill %s: %s", child, exc)
    return skills


def build_catalog(skills: List[SkillMeta]) -> str:
    """Render the skills catalog injected into the system prompt."""
    if not skills:
        return "No skills are currently available."
    lines = ["Available skills (use `read_skill` to load full instructions):"]
    for s in skills:
        lines.append(f"\n- id: {s.id}\n  name: {s.name}\n  when_to_use: {s.when_to_use}")
        if s.datasets:
            lines.append(f"  datasets: {', '.join(s.datasets)}")
    return "\n".join(lines)


def get_skill(skill_id: str, skills_dir: Path = SKILLS_DIR) -> Optional[SkillMeta]:
    for s in discover_skills(skills_dir):
        if s.id == skill_id:
            return s
    return None


def read_skill_body(skill_id: str, skills_dir: Path = SKILLS_DIR) -> str:
    """Return the markdown body (instructions) of a skill's SKILL.md."""
    skill = get_skill(skill_id, skills_dir)
    if skill is None:
        return f"Error: no skill with id '{skill_id}'."
    _, body = _split_frontmatter((skill.path / "SKILL.md").read_text(encoding="utf-8"))
    return body


def read_skill_data_file(skill_id: str, filename: str, skills_dir: Path = SKILLS_DIR) -> str:
    """Return the raw text of a file inside a skill's ``data/`` directory."""
    skill = get_skill(skill_id, skills_dir)
    if skill is None:
        return f"Error: no skill with id '{skill_id}'."
    # Guard against path traversal — only a bare filename is allowed.
    safe = Path(filename).name
    target = skill.path / "data" / safe
    if not target.exists():
        return f"Error: file '{safe}' not found in skill '{skill_id}'."
    return target.read_text(encoding="utf-8")
