#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif

[Setup]
AppId={{18DE9342-B3DC-48BF-AC27-C7916E0B2396}
AppName=BSC Radio Studio
AppVersion={#AppVersion}
AppPublisher=Brewers Social Club
AppPublisherURL=https://github.com/colonelchaboumm/BSC-radio
AppSupportURL=https://github.com/colonelchaboumm/BSC-radio/issues
AppUpdatesURL=https://github.com/colonelchaboumm/BSC-radio/releases
DefaultDirName={localappdata}\Programs\BSC Radio Studio
DefaultGroupName=BSC Radio Studio
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
OutputDir=..\release
OutputBaseFilename=BSC-Radio-Studio-Setup-x64
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\assets\studio.ico
UninstallDisplayIcon={app}\BSC-Radio-Studio.exe
CloseApplications=yes
CloseApplicationsFilter=BSC-Radio-Studio.exe
RestartApplications=no
LicenseFile=..\LICENSE
VersionInfoVersion={#AppVersion}.0

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "Créer un raccourci sur le Bureau"; Flags: unchecked

[Files]
Source: "..\dist\BSC-Radio-Studio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{userprograms}\BSC Radio Studio"; Filename: "{app}\BSC-Radio-Studio.exe"
Name: "{userdesktop}\BSC Radio Studio"; Filename: "{app}\BSC-Radio-Studio.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\BSC-Radio-Studio.exe"; Description: "Ouvrir BSC Radio Studio"; Flags: nowait postinstall skipifsilent
