; =====================================================================
; Script Inno Setup - CorteAC (JobManager 2000 Reborn)
; Gera o instalador Windows oficial com assistente de configuração de rede
; =====================================================================

#define MyAppName "OpenCorte"
#ifndef MyAppVersion
  #define MyAppVersion "1.8.15"
#endif
#define MyAppPublisher "ATOM / OpenCorte Industrial"
#define MyAppURL "https://github.com/Doletabgi/Projeto-CorteAC"
#define MyAppExeName "OpenCorte.exe"

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
OutputBaseFilename=OpenCorte-Setup-{#MyAppVersion}
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

[InstallDelete]
Type: files; Name: "{autodesktop}\CorteAC*.lnk"
Type: files; Name: "{autodesktop}\OpenCorte-*.lnk"
Type: files; Name: "{group}\CorteAC*.lnk"

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\assets\app_icon.ico"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; IconFilename: "{app}\assets\app_icon.ico"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
var
  InstallModePage: TInputOptionWizardPage;
  ServerPage: TInputQueryWizardPage;
  LoadedIniPath: String;
  OriginalMode: Integer;
  OriginalAddress: String;

procedure InitializeWizard;
begin
  InstallModePage := CreateInputOptionPage(
    wpSelectDir,
    'Onde o OpenCorte vai guardar os dados?',
    'Escolha como este computador vai trabalhar',
    'Local: os dados ficam neste computador.' + #13#10 +
    'Rede: moldes, sessoes e banco usam um unico servidor.' + #13#10 + #13#10 +
    'Ao atualizar, a configuracao existente sera mantida se voce nao alterar esta escolha ou o endereco.',
    True, False
  );
  InstallModePage.Add('Instalar localmente (neste computador)');
  InstallModePage.Add('Usar um servidor na rede');
  InstallModePage.SelectedValueIndex := 0;

  ServerPage := CreateInputQueryPage(
    InstallModePage.ID,
    'Servidor da rede',
    'Um unico endereco para moldes, sessoes e banco',
    'Informe o nome/IP do servidor ou a pasta compartilhada.' + #13#10 +
    'Exemplos: SERVIDOR, 192.168.1.100 ou \\SERVIDOR\Fabrica.' + #13#10 + #13#10 +
    'O OpenCorte usa as subpastas Moldes e Sessoes e conecta ao banco nesse mesmo servidor.' + #13#10 +
    'Ao informar somente nome/IP, a pasta compartilhada usada e Fabrica.'
  );
  ServerPage.Add('Endereco do servidor ou da pasta compartilhada:', False);
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := (PageID = ServerPage.ID) and (InstallModePage.SelectedValueIndex = 0);
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  IniPath, ShapesDir, SessionsDir, Address, Host: String;
  I: Integer;
begin
  Result := True;
  if CurPageID = wpSelectDir then
  begin
    IniPath := ExpandConstant('{app}\db.ini');
    // Voltar/avancar nao descarta o que o operador acabou de escolher.
    if LoadedIniPath <> IniPath then
    begin
      LoadedIniPath := IniPath;
      OriginalMode := 0;
      OriginalAddress := '';
      if FileExists(IniPath) then
      begin
        ShapesDir := GetIniString('paths', 'shapes_dir', '', IniPath);
        SessionsDir := GetIniString('paths', 'sessions_dir', '', IniPath);
        if (GetIniString('database', 'backend', 'mysql', IniPath) = 'mysql') or
           (ShapesDir <> '') or (SessionsDir <> '') then
          OriginalMode := 1;
        OriginalAddress := GetIniString('installation', 'server_address', '', IniPath);
        if (OriginalAddress = '') and (Copy(ShapesDir, 1, 2) = '\\') and
           (CompareText(ExtractFileName(ShapesDir), 'Moldes') = 0) and
           (CompareText(ExtractFileName(SessionsDir), 'Sessoes') = 0) and
           (CompareText(ExtractFileDir(ShapesDir), ExtractFileDir(SessionsDir)) = 0) then
          OriginalAddress := ExtractFileDir(ShapesDir);
        if OriginalAddress = '' then
          OriginalAddress := GetIniString('database', 'host', '', IniPath);
      end;
      InstallModePage.SelectedValueIndex := OriginalMode;
      ServerPage.Values[0] := OriginalAddress;
    end;
  end;
  if CurPageID = ServerPage.ID then
  begin
    Address := Trim(ServerPage.Values[0]);
    while (Length(Address) > 2) and (Copy(Address, Length(Address), 1) = '\') do
      Delete(Address, Length(Address), 1);
    ServerPage.Values[0] := Address;
    // Sem alteracoes, preserva inclusive configuracoes antigas personalizadas.
    if FileExists(LoadedIniPath) and (OriginalMode = InstallModePage.SelectedValueIndex) and
       (Address = OriginalAddress) then
      Exit;
    Result := Address <> '';
    if (Copy(Address, 1, 2) <> '\\') and (Pos('\', Address) > 0) then
      Result := False;
    for I := 1 to Length(Address) do
      if (Ord(Address[I]) < 32) or (Pos(Address[I], '/:*?"<>|') > 0) then
        Result := False;
    Host := Address;
    if Copy(Host, 1, 2) = '\\' then
      Delete(Host, 1, 2);
    I := Pos('\', Host);
    if I > 0 then
      Host := Copy(Host, 1, I - 1);
    if Host = '' then Result := False;
    for I := 1 to Length(Host) do
      if Pos(Lowercase(Host[I]), 'abcdefghijklmnopqrstuvwxyz0123456789_-.') = 0 then
        Result := False;
    if not Result then
      MsgBox('Informe o nome/IP do servidor ou um caminho como \\SERVIDOR\Fabrica.', mbError, MB_OK);
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  IniPath, Mode, Address, Parameters, ErrorPath, ErrorText: String;
  ErrorContents: AnsiString;
  ResultCode: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    IniPath := ExpandConstant('{app}\db.ini');
    Address := Trim(ServerPage.Values[0]);
    if FileExists(IniPath) and (OriginalMode = InstallModePage.SelectedValueIndex) and
       (Address = OriginalAddress) then
    begin
      Log('Configuracao existente preservada.');
      Exit;
    end;
    if InstallModePage.SelectedValueIndex = 1 then Mode := 'rede' else Mode := 'local';
    ErrorPath := ExpandConstant('{tmp}\opencorte-config-error.txt');
    Parameters := '--configurar-instalacao --modo ' + Mode + ' --erro-arquivo "' + ErrorPath + '"';
    if Mode = 'rede' then
      Parameters := Parameters + ' --servidor "' + Address + '"';
    if not Exec(ExpandConstant('{app}\{#MyAppExeName}'), Parameters,
                ExpandConstant('{app}'), SW_HIDE, ewWaitUntilTerminated, ResultCode) or
       (ResultCode <> 0) then
    begin
      ErrorText := 'Nao foi possivel salvar a configuracao do OpenCorte. Verifique o endereco e a permissao da pasta de instalacao.';
      if LoadStringFromFile(ErrorPath, ErrorContents) then
        ErrorText := String(ErrorContents);
      RaiseException(ErrorText);
    end;
  end;
end;
