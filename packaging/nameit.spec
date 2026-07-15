# PyInstaller spec for the NameiT desktop app.
# Build on Windows:  packaging\build.ps1   (does everything)
# Manual:            pyinstaller packaging/nameit.spec --noconfirm
#
# Bundles: the app, the Vosk model, skills, and ffmpeg.exe (drop it in
# packaging/bin/ first — see packaging/README.md). Output: dist/NameiT/

from pathlib import Path

ROOT = Path(SPECPATH).parent

datas = [
    (str(ROOT / "skills"), "skills"),
    (str(ROOT / ".env.example"), "."),
]

# Vosk model — required for voice out of the box
vosk_model = ROOT / "models" / "vosk-model-small-en-us-0.15"
if vosk_model.exists():
    datas.append((str(vosk_model), "models/vosk-model-small-en-us-0.15"))
else:
    print("WARNING: Vosk model not found — run scripts/setup.ps1 once first, "
          "or the packaged app will have no voice trigger.")

binaries = []
ffmpeg = ROOT / "packaging" / "bin" / "ffmpeg.exe"
if ffmpeg.exists():
    binaries.append((str(ffmpeg), "."))
else:
    print("WARNING: packaging/bin/ffmpeg.exe not found — download the essentials "
          "build from https://www.gyan.dev/ffmpeg/builds/ and drop ffmpeg.exe there.")

a = Analysis(
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(ROOT / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        "pystray._win32",
        "PIL._tkinter_finder",
        "sounddevice",
        "vosk",
        "khaosclip.gui.app",
        "khaosclip.gui.tray",
        "khaosclip.gui.wizard",
        "khaosclip.gui.picker",
    ],
    excludes=["torch", "matplotlib", "IPython"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name="NameiT",
    console=False,            # no terminal window — this is the whole point
    icon=str(ROOT / "packaging" / "nameit.ico") if (ROOT / "packaging" / "nameit.ico").exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name="NameiT",
)
