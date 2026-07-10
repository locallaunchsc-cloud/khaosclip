"""OBS capture via obs-websocket v5 (built into OBS 28+).

Strategy: we do NOT ship an OBS plugin. OBS already has a Replay Buffer that
holds the last N seconds in RAM; we just tell it to flush to disk and pick up
the file. Zero install inside OBS, works with every scene setup, survives
OBS updates.
"""

from __future__ import annotations

import time
from pathlib import Path

from khaosclip.config import get_settings
from khaosclip.log import get_logger

log = get_logger("obs")

VIDEO_EXTS = (".mp4", ".mkv", ".mov", ".flv", ".ts")


class OBSError(RuntimeError):
    pass


class OBSCapture:
    def __init__(self):
        self._cl = None

    # ------------------------------------------------------------ connection
    def connect(self) -> None:
        import obsws_python as obs

        s = get_settings()
        try:
            self._cl = obs.ReqClient(
                host=s.obs_ws_host, port=s.obs_ws_port, password=s.obs_ws_password, timeout=5
            )
        except Exception as e:
            raise OBSError(
                f"Can't reach OBS websocket at {s.obs_ws_host}:{s.obs_ws_port} — "
                f"enable it in OBS: Tools > WebSocket Server Settings. ({e})"
            ) from e

    def ensure_replay_buffer(self) -> None:
        try:
            status = self._cl.get_replay_buffer_status()
        except Exception as e:
            raise OBSError(
                "Replay Buffer unavailable. Enable it: OBS Settings > Output > Replay Buffer."
            ) from e
        if not status.output_active:
            log.info("Replay buffer was off — starting it.")
            self._cl.start_replay_buffer()
            time.sleep(0.5)

    # ------------------------------------------------------------ capture
    def save_replay(self) -> Path:
        """Flush the buffer, return the saved file path, verified stable on disk."""
        triggered_at = time.time()
        self._cl.save_replay_buffer()

        path = self._path_from_obs(deadline=triggered_at + 15)
        if path is None:
            path = self._path_from_scan(after_ts=triggered_at, deadline=triggered_at + 20)
        if path is None:
            s = get_settings()
            raise OBSError(
                f"Replay saved but no file found. Check OBS_REPLAY_DIR "
                f"({s.obs_replay_dir}) matches OBS Settings > Output > Recording path."
            )
        if not self._wait_stable(path):
            raise OBSError(f"Replay file {path.name} never finished writing.")
        return path

    def _path_from_obs(self, deadline: float) -> Path | None:
        """OBS 29+ reports the exact saved path. Poll briefly for it."""
        while time.time() < deadline:
            try:
                resp = self._cl.get_last_replay_buffer_replay()
                p = getattr(resp, "saved_replay_path", None)
                if p and Path(p).exists():
                    return Path(p)
            except Exception:
                return None  # older OBS — caller falls back to directory scan
            time.sleep(0.5)
        return None

    def _path_from_scan(self, after_ts: float, deadline: float) -> Path | None:
        folder = Path(get_settings().obs_replay_dir)
        while time.time() < deadline:
            try:
                candidates = [
                    p for p in folder.iterdir()
                    if p.suffix.lower() in VIDEO_EXTS and p.stat().st_mtime >= after_ts - 2
                ]
            except FileNotFoundError:
                return None
            if candidates:
                return max(candidates, key=lambda p: p.stat().st_mtime)
            time.sleep(1.0)
        return None

    @staticmethod
    def _wait_stable(path: Path, timeout: float = 30.0) -> bool:
        last, stable_since = -1, None
        deadline = time.time() + timeout
        while time.time() < deadline:
            size = path.stat().st_size
            if size == last and size > 0:
                stable_since = stable_since or time.time()
                if time.time() - stable_since > 1.5:
                    return True
            else:
                stable_since = None
            last = size
            time.sleep(0.5)
        return False
