; Inno Setup script: builds ImageSizer-<version>-Windows-Setup.exe from the PyInstaller output.
; iscc /DAppVersion=0.1.0 packaging\windows\imagesizer.iss
; Installs per user (no admin prompt) to %LOCALAPPDATA%\Programs\ImageSizer.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6F1C2B9E-6C1D-4E8A-9B3E-5D2A7C4F8E11}
AppName=ImageSizer
AppVersion={#AppVersion}
AppPublisher=hembone
AppPublisherURL=https://github.com/hembone/imagesizer
AppSupportURL=https://github.com/hembone/imagesizer/issues
DefaultDirName={localappdata}\Programs\ImageSizer
DefaultGroupName=ImageSizer
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\..\dist
OutputBaseFilename=ImageSizer-{#AppVersion}-Windows-Setup
SetupIconFile=..\icon.ico
UninstallDisplayIcon={app}\ImageSizer.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\..\dist\ImageSizer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\ImageSizer"; Filename: "{app}\ImageSizer.exe"
Name: "{autodesktop}\ImageSizer"; Filename: "{app}\ImageSizer.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\ImageSizer.exe"; Description: "{cm:LaunchProgram,ImageSizer}"; Flags: nowait postinstall skipifsilent

; Settings, presets and the downloaded engine live in %LOCALAPPDATA%\imagesizer and are kept on uninstall/upgrade.
