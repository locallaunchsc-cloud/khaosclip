; NameiT installer — Inno Setup script
; Build: packaging\build.ps1 runs this automatically after PyInstaller.
; Manual: "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" packaging\installer.iss
; Output: packaging\out\NameiT-Setup.exe

#define AppName "NameiT"
#define AppVersion "0.1.0"
#define AppPublisher "NameiT"
#define AppURL "https://nameit.vercel.app"

[Setup]
AppId={{8F6B1F2A-NAMEIT-CLIP-TOOL-000000000001}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=out
OutputBaseFilename=NameiT-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\NameiT.exe

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"
Name: "startup"; Description: "Start NameiT when Windows starts (recommended for streamers)"; GroupDescription: "Options:"; Flags: unchecked

[Files]
Source: "..\dist\NameiT\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\NameiT.exe"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\NameiT.exe"; Tasks: desktopicon
Name: "{userstartup}\{#AppName}"; Filename: "{app}\NameiT.exe"; Tasks: startup

[Run]
Filename: "{app}\NameiT.exe"; Description: "Launch {#AppName} now"; Flags: nowait postinstall skipifsilent
