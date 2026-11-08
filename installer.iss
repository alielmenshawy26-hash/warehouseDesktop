; برنامج تسطيب «سيستم المخازن والمبيعات» — النسخة الأوفلاين (نفس كود زلط، بداتا ومجلد منفصلين)
[Setup]
AppId={{A6F149A3-9B22-47B0-AE63-3B1D93E64E01}
AppName=Warehouse
AppVersion=1.0
AppPublisher=Ali ElMenshawy
DefaultDirName={autopf}\WarehouseDesktop
DefaultGroupName=Warehouse
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=Warehouse-Setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=force
RestartApplications=no

[Tasks]
Name: "desktopicon"; Description: "Desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "dist\Warehouse.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "server_setup.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "server_setup.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "tools\SumatraPDF.exe"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
Name: "{group}\Warehouse"; Filename: "{app}\Warehouse.exe"
Name: "{group}\Server setup (main PC only)"; Filename: "{app}\server_setup.bat"
Name: "{autodesktop}\Warehouse"; Filename: "{app}\Warehouse.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Warehouse.exe"; Description: "Run Warehouse"; Flags: nowait postinstall skipifsilent

[Code]
// قبل التسطيب: يقفل أي نسخة شغالة من البرنامج علشان الملف يتبدل
function PrepareToInstall(var NeedsRestart: Boolean): String;
var Code: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /T /IM Warehouse.exe', '', SW_HIDE, ewWaitUntilTerminated, Code);
  Sleep(1500);
  Result := '';
end;
