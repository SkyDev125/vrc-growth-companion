[Setup]
AppName=Mid's Den Companion
AppVersion=1.2.0
DefaultDirName={localappdata}\Programs\MidsDenCompanion
DefaultGroupName=Mid's Den Companion
PrivilegesRequired=lowest
OutputDir=..\public\downloads
OutputBaseFilename=mids-den-companion-windows-setup
Compression=lzma2
SolidCompression=yes
SetupIconFile=..\public\downloads\app-icon.ico
UninstallDisplayIcon={app}\MidsDenCompanion.exe
[Files]
Source: "..\public\downloads\MidsDenCompanion.exe"; DestDir: "{app}"
[Icons]
Name: "{group}\Mid's Den Companion"; Filename: "{app}\MidsDenCompanion.exe"
Name: "{autodesktop}\Mid's Den Companion"; Filename: "{app}\MidsDenCompanion.exe"
[Run]
Filename: "{app}\MidsDenCompanion.exe"; Description: "Open companion"; Flags: nowait postinstall skipifsilent
