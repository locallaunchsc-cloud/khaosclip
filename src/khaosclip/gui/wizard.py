"""First-run setup wizard.

Opens once, the first time the desktop app launches (no .env yet):

  1. Auto-detects the OBS recording folder + websocket settings by reading
     OBS's own config files. One [Looks right] click. Browse button as backup.
  2. Mic check: shows a live level bar; they talk, it goes green.
  3. Writes .env and hands off to the tray app.

Everything has a keyboard-free path. The only typing is optional.
"""

from __future__ import annotations

from pathlib import Path

from khaosclip.config import app_data_dir, env_file_path
from khaosclip.obs_detect import detect


def build_env_text(replay_dir: str, ws_port: int | None, ws_password: str | None) -> str:
    """The .env the wizard writes — manual mode, GUI mode, sane defaults."""
    lines = [
        "# NameiT — created by the setup wizard. Edit anytime via tray > Settings.",
        f"OBS_REPLAY_DIR={replay_dir}",
        "POST_MODE=manual",
        "GUI_MODE=true",
        "VOICE_ENGINE=vosk",
        "BRAND_TAG=🎬 clipped live by voice with NameiT",
    ]
    if ws_port:
        lines.append(f"OBS_WS_PORT={ws_port}")
    if ws_password:
        lines.append(f"OBS_WS_PASSWORD={ws_password}")
    return "\n".join(lines) + "\n"


def write_env(replay_dir: str, ws_port: int | None, ws_password: str | None) -> Path:
    path = env_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_env_text(replay_dir, ws_port, ws_password), encoding="utf-8")
    return path


def needs_setup() -> bool:
    return not env_file_path().exists()


def run_wizard() -> bool:
    """Show the wizard window. Returns True if setup completed."""
    import tkinter as tk
    from tkinter import filedialog

    info = detect()
    detected = str(info.replay_dir) if info.replay_dir else ""

    root = tk.Tk()
    root.title("NameiT — setup (30 seconds)")
    root.configure(bg="#111111", padx=24, pady=20)
    root.resizable(False, False)
    root.attributes("-topmost", True)

    state = {"done": False}

    tk.Label(root, text="NameiT", bg="#111111", fg="#ffffff",
             font=("Segoe UI", 18, "bold")).pack(anchor="w")
    tk.Label(root, text="say \u201caye clip that\u201d mid-stream — the clip posts itself",
             bg="#111111", fg="#888888", font=("Segoe UI", 10)).pack(anchor="w", pady=(0, 16))

    # ---- Step 1: OBS folder
    tk.Label(root, text="1 · Where OBS saves your recordings", bg="#111111",
             fg="#ffffff", font=("Segoe UI", 11, "bold")).pack(anchor="w")

    status = "detected automatically ✓" if detected else "couldn't auto-detect — click Browse"
    tk.Label(root, text=status, bg="#111111",
             fg="#4caf50" if detected else "#ff9800",
             font=("Segoe UI", 9)).pack(anchor="w")

    dir_var = tk.StringVar(value=detected)
    row = tk.Frame(root, bg="#111111")
    row.pack(fill="x", pady=(4, 4))
    tk.Entry(row, textvariable=dir_var, width=46, bg="#1e1e1e", fg="#ffffff",
             insertbackground="#ffffff", relief="flat").pack(side="left", ipady=5)

    def browse():
        chosen = filedialog.askdirectory(title="Pick your OBS recording folder")
        if chosen:
            dir_var.set(chosen)

    tk.Button(row, text="Browse…", command=browse, bg="#1e1e1e", fg="#ffffff",
              relief="flat", padx=10).pack(side="left", padx=(8, 0))

    for problem in info.problems:
        tk.Label(root, text=f"⚠ {problem}", bg="#111111", fg="#ff9800",
                 font=("Segoe UI", 8), wraplength=430, justify="left").pack(anchor="w")

    # ---- Step 2: mic check
    tk.Label(root, text="2 · Mic check — say something", bg="#111111",
             fg="#ffffff", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(14, 2))
    level_canvas = tk.Canvas(root, width=430, height=14, bg="#1e1e1e",
                             highlightthickness=0)
    level_canvas.pack(anchor="w")
    level_bar = level_canvas.create_rectangle(0, 0, 0, 14, fill="#4caf50", width=0)
    mic_label = tk.Label(root, text="listening…", bg="#111111", fg="#888888",
                         font=("Segoe UI", 8))
    mic_label.pack(anchor="w")

    mic = {"stream": None, "peak": 0.0}
    try:
        import numpy as np
        import sounddevice as sd

        def audio_cb(indata, frames, t, s2):
            level = float(np.abs(indata).mean()) / 32768.0
            mic["peak"] = max(mic["peak"] * 0.9, level)

        mic["stream"] = sd.InputStream(samplerate=16000, channels=1,
                                       dtype="int16", callback=audio_cb)
        mic["stream"].start()

        def poll_level():
            if state["done"]:
                return
            width = min(430, int(mic["peak"] * 4300))
            level_canvas.coords(level_bar, 0, 0, width, 14)
            if mic["peak"] > 0.02:
                mic_label.config(text="mic works ✓", fg="#4caf50")
            root.after(80, poll_level)

        poll_level()
    except Exception:
        mic_label.config(text="couldn't open mic — you can still finish setup", fg="#ff9800")

    # ---- Finish
    def finish():
        replay = dir_var.get().strip()
        if not replay:
            mic_label.config(text="pick your OBS folder first", fg="#f44336")
            return
        write_env(replay, info.ws_port, info.ws_password)
        state["done"] = True
        if mic["stream"]:
            try:
                mic["stream"].stop()
            except Exception:
                pass
        root.destroy()

    tk.Button(root, text="Done — start clipping", command=finish,
              bg="#4caf50", fg="#ffffff", activebackground="#43a047",
              relief="flat", font=("Segoe UI", 11, "bold"),
              padx=16, pady=8).pack(anchor="w", pady=(18, 0))

    tk.Label(root, text=f"settings saved to {app_data_dir()}", bg="#111111",
             fg="#555555", font=("Segoe UI", 7)).pack(anchor="w", pady=(10, 0))

    root.mainloop()
    return state["done"]
