#ifndef MyAppVersion
  #define MyAppVersion "1.1.1"
#endif

[Setup]
AppId=INformigados.PixelForge
AppName=Pixel Forge
AppVersion={#MyAppVersion}
AppPublisher=INformigados
AppPublisherURL=https://github.com/informigados/pixel-forge
AppSupportURL=https://github.com/informigados/pixel-forge/issues
DefaultDirName={localappdata}\Programs\Pixel Forge
DefaultGroupName=Pixel Forge
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
OutputDir={#OutputDirectory}
OutputBaseFilename=PixelForge-{#MyAppVersion}-setup-windows-x64
SetupIconFile={#IconFile}
UninstallDisplayIcon={app}\app-icon.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
VersionInfoVersion={#MyAppVersion}.0

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar um atalho na área de trabalho"; GroupDescription: "Atalhos:"

[Files]
Source: "{#SourceExe}"; DestDir: "{app}"; DestName: "PixelForge.exe"; Flags: ignoreversion
Source: "{#IconFile}"; DestDir: "{app}"; DestName: "app-icon.ico"; Flags: ignoreversion
Source: "{#LicenseArchive}"; DestDir: "{app}"; DestName: "third-party-licenses.zip"; Flags: ignoreversion
Source: "{#WebView2Installer}"; Flags: dontcopy

[Icons]
Name: "{group}\Pixel Forge"; Filename: "{app}\PixelForge.exe"; WorkingDir: "{app}"; IconFilename: "{app}\app-icon.ico"; AppUserModelID: "INformigados.PixelForge"
Name: "{autodesktop}\Pixel Forge"; Filename: "{app}\PixelForge.exe"; WorkingDir: "{app}"; IconFilename: "{app}\app-icon.ico"; AppUserModelID: "INformigados.PixelForge"; Tasks: desktopicon

[Run]
Filename: "{app}\PixelForge.exe"; Description: "Iniciar o Pixel Forge"; Flags: nowait postinstall skipifsilent

[Code]
function HasWebView2: Boolean;
var
  Version: String;
  Key: String;
begin
  Key := 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';
  Result := RegQueryStringValue(HKLM32, Key, 'pv', Version) and
            (Version <> '') and (Version <> '0.0.0.0');
  if not Result then
    Result := RegQueryStringValue(HKCU, Key, 'pv', Version) and
              (Version <> '') and (Version <> '0.0.0.0');
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  Result := '';
  if not HasWebView2 then
  begin
    ExtractTemporaryFile('MicrosoftEdgeWebView2RuntimeInstallerX64.exe');
    if not Exec(ExpandConstant('{tmp}\MicrosoftEdgeWebView2RuntimeInstallerX64.exe'),
                '/silent /install', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
    begin
      Result := 'Não foi possível iniciar a instalação do Microsoft WebView2.';
      Exit;
    end;
    if not HasWebView2 then
      Result := 'O Microsoft WebView2 não foi instalado. Reinicie o Windows e execute o instalador novamente.';
  end;
end;
