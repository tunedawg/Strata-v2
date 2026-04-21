; Strata — Inno Setup for Nuitka build
; Nuitka onefile produces a single Strata.exe in dist\

#define AppName      "Strata"
#define AppVersion   "1.0"
#define AppPublisher "Noah Tunis"
#define AppExeName   "Strata.exe"

[Setup]
AppId={{B3E1D4F2-5A9C-4E8B-C3D4-7F8A9B0C2D3E}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
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

[Files]
; Nuitka onefile — single exe
Source: "dist\Strata.exe"; DestDir: "{app}"; Flags: ignoreversion
; Bundle Tesseract if present
Source: "tesseract\*"; DestDir: "{app}\tesseract"; Flags: ignoreversion recursesubdirs createallsubdirs; Check: DirExists(ExpandConstant('{src}\tesseract'))
; Bundle Poppler if present  
Source: "poppler\*"; DestDir: "{app}\poppler"; Flags: ignoreversion recursesubdirs createallsubdirs; Check: DirExists(ExpandConstant('{src}\poppler'))

[Icons]
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
var DataPath: String;
begin
  if CurStep = ssDone then
  begin
    DataPath := ExpandConstant('{userdocs}') + '\Strata';
    MsgBox('Installation complete!' + #13#10 + #13#10 +
      'Your productions and exports will be saved to:' + #13#10 +
      '  ' + DataPath, mbInformation, MB_OK);
  end;
end;
