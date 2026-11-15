#ifndef AppVersion
#define AppVersion "1.3.0"
#endif
[Setup]
AppName=Mid's Den Companion
AppVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\MidsDenCompanion
DefaultGroupName=Mid's Den Companion
PrivilegesRequired=lowest
CloseApplications=force
RestartApplications=no
OutputDir=..\public\downloads
OutputBaseFilename=mids-den-companion-windows-setup
Compression=lzma2
SolidCompression=yes
SetupIconFile=..\public\downloads\app-icon.ico
UninstallDisplayIcon={app}\MidsDenCompanion.exe
[Files]
Source: "..\public\downloads\MidsDenCompanion\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
[Icons]
Name: "{group}\Mid's Den Companion"; Filename: "{app}\MidsDenCompanion.exe"
Name: "{autodesktop}\Mid's Den Companion"; Filename: "{app}\MidsDenCompanion.exe"
[Run]
Filename: "{app}\MidsDenCompanion.exe"; Description: "Open companion"; Flags: nowait postinstall skipifsilent
