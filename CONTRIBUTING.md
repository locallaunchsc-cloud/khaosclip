# Contributing

KhaosClip is being built live, in public. PRs welcome.

## Dev setup

```bash
git clone https://github.com/locallaunchsc-cloud/khaosclip
cd khaosclip
python -m venv .venv && .venv\Scripts\activate   # Windows
pip install -e ".[all,dev]"
```

## Before you PR

```bash
ruff check src tests
pytest
```

Tests must pass. New pipeline behavior needs a test. If it touches posting,
mock the network — no test should ever hit the real X API.

## Ground rules

- The agent must never crash mid-stream. Any failure logs, records to
  history, and keeps listening.
- A clip is never lost. If posting fails, the file stays on disk.
- The trigger path must stay light — nothing heavy on the audio thread.
