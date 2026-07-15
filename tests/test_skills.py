"""Skill system tests — real skill files from the repo's skills/ dir."""

import json

import pytest

from khaosclip.skills import Skill, get_active_skill, list_skills, load_skill


@pytest.fixture
def skills_dir(tmp_path, monkeypatch):
    d = tmp_path / "skills"
    d.mkdir()
    (d / "test_style.json").write_text(json.dumps({
        "name": "Test Style",
        "description": "for testing",
        "example_caption": "example cap",
        "system_prompt_addon": "Write like a test.",
    }))
    (d / "broken.json").write_text("{not valid json")
    monkeypatch.setattr("khaosclip.skills._SKILLS_DIRS", [d])
    return d


def test_load_skill(skills_dir):
    sk = load_skill("test_style")
    assert sk.name == "Test Style"
    assert sk.system_prompt_addon == "Write like a test."


def test_load_missing_skill_names_available(skills_dir):
    with pytest.raises(FileNotFoundError, match="test_style"):
        load_skill("nope")


def test_list_skills_skips_broken_files(skills_dir):
    found = list_skills()
    assert [s.key for s in found] == ["test_style"]  # broken.json skipped


def test_get_active_skill_none_key(skills_dir):
    assert get_active_skill("") is None
    assert get_active_skill("none") is None


def test_get_active_skill_bad_key_falls_back(skills_dir):
    assert get_active_skill("missing") is None


def test_repo_skills_are_valid():
    """Every skill shipped in the repo must parse."""
    found = list_skills()
    keys = {s.key for s in found}
    assert {"yoxic_jack", "crypto_alpha", "comedy", "narrative", "default"} <= keys
    for s in found:
        assert isinstance(s, Skill)
        assert s.system_prompt_addon


def test_skill_addon_reaches_claude_prompt(skills_dir, monkeypatch):
    """The skill's style instructions must land in the API payload."""
    import khaosclip.caption_ai as ca
    from khaosclip.config import reset_settings

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("CAPTION_SKILL", "test_style")
    reset_settings()

    captured = {}

    class FakeResp:
        def read(self):
            return json.dumps({"content": [{"text": json.dumps({"captions": ["a", "b", "c"]})}]}).encode()
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def fake_urlopen(req, timeout=0):
        captured["body"] = req.data.decode()
        return FakeResp()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    result = ca.generate_captions("some transcript")
    assert result == ["a", "b", "c"]
    assert "Write like a test." in captured["body"]
    assert "example cap" in captured["body"]
