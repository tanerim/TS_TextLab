#ifndef AppVersion
  #error AppVersion must be supplied by the packaging script
#endif

[Setup]
AppId={{A43106CB-C87D-4296-BCEB-7CBFA57D5639}
AppName=TS TextLab
AppVersion={#AppVersion}
AppPublisher=TS Corpus
DefaultDirName={localappdata}\Programs\TS TextLab
DefaultGroupName=TS TextLab
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename=TS-TextLab-{#AppVersion}-windows-x86_64-Setup
SetupIconFile={#ProjectDir}\app\theme\app-icon.ico
UninstallDisplayIcon={app}\TS TextLab.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#BundleDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\TS TextLab"; Filename: "{app}\TS TextLab.exe"; WorkingDir: "{app}"
Name: "{userdesktop}\TS TextLab"; Filename: "{app}\TS TextLab.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\TS TextLab.exe"; Description: "{cm:LaunchProgram,TS TextLab}"; Flags: nowait postinstall skipifsilent
