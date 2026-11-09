; =====================================================================
; Script Inno Setup - CorteAC (JobManager 2000 Reborn)
; Gera o instalador Windows oficial com assistente de configuração de rede
; =====================================================================

#define MyAppName "CorteAC"
#ifndef MyAppVersion
  #define MyAppVersion "1.7.0"
#endif
#define MyAppPublisher "ATOM / CorteAC Industrial"
#define MyAppURL "https://github.com/Doletabgi/Projeto-CorteAC"
#define MyAppExeName "CorteAC.exe"

[Setup]
AppId={{8B84F01A-417A-4D46-9D3E-94A57F083F30}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName=C:\CorteAC
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=..\dist
OutputBaseFilename=CorteAC-Setup-{#MyAppVersion}
SetupIconFile=..\assets\app_icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=commandline
UninstallDisplayIcon={app}\{#MyAppExeName}
CloseApplications=force
DisableProgramGroupPage=yes

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README_WINDOWS.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\db.example.ini"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\assets\app_icon.ico"; DestDir: "{app}\assets"; Flags: ignoreversion
Source: "..\assets\app_icon.png"; DestDir: "{app}\assets"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\assets\app_icon.ico"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; IconFilename: "{app}\assets\app_icon.ico"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
var
  NetworkConfigPage: TInputQueryWizardPage;
  EditShapesDirIndex: Integer;
  EditSessionsDirIndex: Integer;
  EditMySqlHostIndex: Integer;

procedure InitializeWizard;
begin
  NetworkConfigPage := CreateInputQueryPage(
    wpSelectDir,
    'Configurações de Rede da Fábrica',
    'Pastas Compartilhadas e Conexão de Banco de Dados',
    'Informe os caminhos compartilhados de Moldes e Sessões na rede local da fábrica.' + #13#10 +
    'Deixe em branco para usar pastas locais ou para configurar manualmente depois no db.ini.'
  );

  EditShapesDirIndex := NetworkConfigPage.Add(
    'Pasta de Moldes na Rede (ex: \\SERVIDOR\Fabrica\Moldes ou Z:\Moldes):',
    False
  );
  EditSessionsDirIndex := NetworkConfigPage.Add(
    'Pasta de Sessões/Máquinas (ex: \\SERVIDOR\Fabrica\Sessoes ou Z:\Sessoes):',
    False
  );
  EditMySqlHostIndex := NetworkConfigPage.Add(
    'Endereço IP do Servidor MySQL Central (deixe vazio para SQLite local):',
    False
  );
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  IniPath: String;
begin
  Result := True;
  if CurPageID = wpSelectDir then
  begin
    IniPath := ExpandConstant('{app}\db.ini');
    if FileExists(IniPath) then
    begin
      if NetworkConfigPage.Values[EditShapesDirIndex] = '' then
        NetworkConfigPage.Values[EditShapesDirIndex] := GetIniString('paths', 'shapes_dir', '', IniPath);
      if NetworkConfigPage.Values[EditSessionsDirIndex] = '' then
        NetworkConfigPage.Values[EditSessionsDirIndex] := GetIniString('paths', 'sessions_dir', '', IniPath);
      if NetworkConfigPage.Values[EditMySqlHostIndex] = '' then
        NetworkConfigPage.Values[EditMySqlHostIndex] := GetIniString('database', 'host', '', IniPath);
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  IniPath: String;
  ShapesDir: String;
  SessionsDir: String;
  MySqlHost: String;
  Backend: String;
begin
  if CurStep = ssPostInstall then
  begin
    IniPath := ExpandConstant('{app}\db.ini');
    ShapesDir := Trim(NetworkConfigPage.Values[EditShapesDirIndex]);
    SessionsDir := Trim(NetworkConfigPage.Values[EditSessionsDirIndex]);
    MySqlHost := Trim(NetworkConfigPage.Values[EditMySqlHostIndex]);

    if MySqlHost <> '' then
      Backend := 'mysql'
    else
      Backend := 'sqlite';

    // Grava no arquivo db.ini
    SetIniString('database', 'backend', Backend, IniPath);
    if MySqlHost <> '' then
    begin
      SetIniString('database', 'host', MySqlHost, IniPath);
      SetIniString('database', 'port', '3306', IniPath);
      SetIniString('database', 'user', 'jm_app', IniPath);
      SetIniString('database', 'password', 'jm_factory_2026', IniPath);
      SetIniString('database', 'database', 'jobmanager', IniPath);
    end;

    if ShapesDir <> '' then
      SetIniString('paths', 'shapes_dir', ShapesDir, IniPath);

    if SessionsDir <> '' then
      SetIniString('paths', 'sessions_dir', SessionsDir, IniPath);
  end;
end;
