; ============================================================
;  Strata — Inno Setup 6 installer script
;  Produces: dist\Strata_Setup.exe
;
;  Run after build.bat, or compile manually:
;    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
; ============================================================

#define AppName      "Strata"
#define AppVersion   "1.0"
#define AppPublisher "Your Firm Name"
#define AppURL       ""
#define AppExeName   "Strata.exe"
#define SourceDir    "dist\Strata"

[Setup]
AppId={{B3E1D4F2-5A9C-4E8B-C3D4-7F8A9B0C2D3E}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
OutputDir=dist
OutputBaseFilename=Strata_Setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=commandline
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=strata.ico
UninstallDisplayIcon={app}\Strata.exe

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"
Name: "startmenuicon"; Description: "Create a Start &Menu shortcut"; GroupDescription: "Additional icons:"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon; Comment: "Open Strata"; IconFilename: "{app}\strata.ico"
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: startmenuicon
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName} now"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\__pycache__"

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
var
  DataPath: String;
begin
  if CurStep = ssDone then
  begin
    DataPath := ExpandConstant('{userdocs}') + '\Strata';
    MsgBox(
      'Installation complete!' + #13#10 + #13#10 +
      'Your productions and exports will be saved to:' + #13#10 +
      '  ' + DataPath + #13#10 + #13#10 +
      'This folder is preserved if you update or reinstall.',
      mbInformation, MB_OK
    );
  end;
end;
