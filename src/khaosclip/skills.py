"""Skills — clip caption style templates.

A skill is a JSON file in skills/ that shapes how Claude writes captions:
the Yoxic Jack expert-quote style, crypto trade-call receipts, comedy
reactions, narrative arcs. Streamers pick their vibe once in .env
(CAPTION_SKILL=yoxic_jack) or per-run (khaosclip run --skill comedy),
and every clip caption follows that pattern.

Skill file format:
{
  "name": "Display Name",
  "description": "What this style is for",
  "example_caption": "a caption in this style",
  "system_prompt_addon": "Instructions appended to Claude's system prompt"
}

Custom skills: drop your own .json in skills/ and it just works.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from khaosclip.log import get_logger

log = get_logger("skills")

# skills/ lives at the repo root, next to src/
_SKILLS_DIRS = [
    Path("skills"),                                  # running from repo root
    Path(__file__).parent.parent.parent / "skills",  # installed package
]


@dataclass
class Skill:
    key: str
    name: str
    description: str
    example_caption: str
    system_prompt_addon: str


def _skills_dir() -> Path | None:
    for d in _SKILLS_DIRS:
        if d.is_dir():
            return d
    return None


def list_skills() -> list[Skill]:
    d = _skills_dir()
    if not d:
        return []
    out = []
    for f in sorted(d.glob("*.json")):
        try:
            out.append(load_skill(f.stem))
        except Exception as e:
            log.warning(f"Skipping bad skill file {f.name}: {e}")
    return out


def load_skill(key: str) -> Skill:
    """Load a skill by its file stem (e.g. 'yoxic_jack')."""
    d = _skills_dir()
    if not d:
        raise FileNotFoundError("skills/ directory not found")
    path = d / f"{key}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"Skill '{key}' not found. Available: "
            + ", ".join(f.stem for f in d.glob("*.json"))
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    return Skill(
        key=key,
        name=data.get("name", key),
        description=data.get("description", ""),
        example_caption=data.get("example_caption", ""),
        system_prompt_addon=data.get("system_prompt_addon", ""),
    )


def get_active_skill(key: str) -> Skill | None:
    """Load the configured skill; None (with a warning) if unavailable."""
    if not key or key == "none":
        return None
    try:
        return load_skill(key)
    except Exception as e:
        log.warning(f"Caption skill '{key}' unavailable ({e}) — using default style.")
        return None
