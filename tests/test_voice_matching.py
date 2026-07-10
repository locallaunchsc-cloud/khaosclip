"""Command matching tests — pure functions, no audio hardware needed."""

from khaosclip.triggers.voice import match_command, normalize

START = ["aye clip this"]
RETRO = ["aye clip that"]
END = ["aye end clip", "aye stop clip"]


def m(text):
    return match_command(text, START, RETRO, END)


def test_retro_command():
    assert m("aye clip that") == ("retro", "aye clip that")


def test_start_command():
    assert m("aye clip this") == ("start", "aye clip this")


def test_end_command():
    assert m("aye end clip") == ("end", "aye end clip")


def test_commands_match_mid_sentence():
    assert m("yo chat that was insane aye clip that lets go")[0] == "retro"


def test_aye_mishearings_normalize():
    # Small models hear "aye" as i / a / hey / eye — all must still fire
    assert normalize("i clip that") == "aye clip that"
    assert m("i clip that")[0] == "retro"
    assert m("hey clip this")[0] == "start"
    assert m("a clip that")[0] == "retro"
    assert m("eye end clip")[0] == "end"


def test_plain_clip_words_do_not_fire():
    # Without the "aye" prefix, casual conversation can't trigger clips
    assert m("that clip was crazy") is None
    assert m("check the clip this weekend") is None
    assert m("clip that") is None


def test_end_beats_retro_specificity():
    assert m("aye stop clip aye clip that")[0] == "end"
