#define MyAppName "سيستم المخازن والمبيعات"
#define MyAppVersion "0.1.0"
#define MyAppExeName "Warehouse.exe"

[Setup]
AppId={{A6F149A3-9B22-47B0-AE63-3B1D93E64E01}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={autopf}\WarehouseDesktop
DefaultGroupName={#MyAppName}
OutputDir=Output
OutputBaseFilename=Warehouse-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "dist\\Warehouse.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\\{#MyAppName}"; Filename: "{app}\\{#MyAppExeName}"
Name: "{autodesktop}\\{#MyAppName}"; Filename: "{app}\\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: postinstall nowait skipifsilent
