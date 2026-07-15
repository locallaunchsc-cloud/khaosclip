"""Popup caption picker — three big buttons, a countdown, zero terminal.

Shown for a few seconds after each clip. Always-on-top, bottom-right of the
primary screen (out of the way of the stream), auto-picks option 1 when the
countdown hits zero so a streamer who ignores it entirely still gets a caption.

Pure-logic pieces (countdown math, result plumbing) are separated from tkinter
so they're testable headless.
"""

from __future__ import annotations

import queue
import threading

PICK_TIMEOUT_DEFAULT = 10


def resolve_choice(choice: str | None, captions: list[str], default: str) -> str:
    """Map a picker outcome to the final caption text.

    choice is '1'/'2'/'3', 'skip', a custom edited string, or None (timeout).
    """
    if choice is None:
        return captions[0] if captions else default
    if choice == "skip":
        return default
    if choice in ("1", "2", "3"):
        idx = int(choice) - 1
        if idx < len(captions):
            return captions[idx]
        return captions[0] if captions else default
    return choice  # edited custom text


def pick_caption_gui(captions: list[str], default: str,
                     timeout: int = PICK_TIMEOUT_DEFAULT) -> str:
    """Show the popup; return the chosen caption. Falls back to option 1.

    Runs tkinter in a dedicated thread with its own mainloop, so it can be
    called from the worker thread without fighting over the GUI main thread.
    """
    result_q: queue.Queue[str | None] = queue.Queue()

    def _window():
        try:
            import tkinter as tk
        except ImportError:
            result_q.put(None)
            return

        root = tk.Tk()
        root.title("NameiT — pick a caption")
        root.attributes("-topmost", True)
        root.configure(bg="#111111", padx=14, pady=12)
        root.resizable(False, False)

        done = {"sent": False}

        def send(v: str | None):
            if not done["sent"]:
                done["sent"] = True
                result_q.put(v)
            root.destroy()

        tk.Label(
            root, text="Clip ready — pick a caption", bg="#111111", fg="#ffffff",
            font=("Segoe UI", 12, "bold"),
        ).pack(anchor="w")

        countdown = tk.Label(root, bg="#111111", fg="#888888", font=("Segoe UI", 9))
        countdown.pack(anchor="w", pady=(0, 8))

        for i, cap in enumerate(captions[:3], start=1):
            text = cap if len(cap) <= 90 else cap[:87] + "…"
            tk.Button(
                root, text=f"{i}.  {text}", anchor="w", justify="left",
                wraplength=420, bg="#1e1e1e", fg="#ffffff",
                activebackground="#333333", activeforeground="#ffffff",
                relief="flat", padx=10, pady=8, font=("Segoe UI", 10),
                command=lambda n=i: send(str(n)),
            ).pack(fill="x", pady=3)

        bottom = tk.Frame(root, bg="#111111")
        bottom.pack(fill="x", pady=(8, 0))
        tk.Button(
            bottom, text="Skip (use default)", bg="#111111", fg="#888888",
            relief="flat", command=lambda: send("skip"),
        ).pack(side="left")

        # position bottom-right
        root.update_idletasks()
        w, h = root.winfo_width(), root.winfo_height()
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        root.geometry(f"+{sw - w - 24}+{sh - h - 80}")

        remaining = {"t": timeout}

        def tick():
            if done["sent"]:
                return
            remaining["t"] -= 1
            if remaining["t"] <= 0:
                send(None)  # timeout -> auto option 1
                return
            countdown.config(text=f"auto-posting option 1 in {remaining['t']}s")
            root.after(1000, tick)

        countdown.config(text=f"auto-posting option 1 in {timeout}s")
        root.after(1000, tick)
        root.protocol("WM_DELETE_WINDOW", lambda: send(None))
        root.mainloop()

    t = threading.Thread(target=_window, daemon=True)
    t.start()
    try:
        choice = result_q.get(timeout=timeout + 5)
    except queue.Empty:
        choice = None
    return resolve_choice(choice, captions, default)
