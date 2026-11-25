; ==============================================================================
; Script de Configuração do Inno Setup 7 - Pytuber
; Gera um instalador profissional para Windows com atalhos, desinstalador e
; suporte a atualizações limpas que substituem versões anteriores sem duplicidade.
; ==============================================================================

#ifndef MyAppVersion
  #define MyAppVersion "0.11.25"
#endif

#define MyAppName "Pytuber"
#define MyAppPublisher "Ademir"
#define MyAppURL "https://github.com/ademirj93/pytuber"
#define MyAppExeName "Pytuber.exe"

[Setup]
; AppId GUID fixo: permite que novas versões atualizem a existente sem duplicar entrada no Windows
AppId={{8B1D4F37-9A63-4C3D-81F9-2A5817E294B1}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; Diretório padrão de instalação (Program Files ou AppData por usuário com lowest)
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes

; Pasta e nome do arquivo gerado (compatível com a busca do updater.py)
OutputDir=dist\installer
OutputBaseFilename=Pytuber_Setup_v{#MyAppVersion}

; Ícones oficiais
SetupIconFile=static\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}

; Compressão máxima LZMA2
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern

; Não requer elevação de administrador obrigatória para facilitar auto-atualizações limpas
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; Fecha o aplicativo em execução automaticamente antes de substituir arquivos
CloseApplications=yes
CloseApplicationsFilter=*.exe
RestartApplications=no

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Copia todos os binários e recursos gerados pelo PyInstaller (--onedir)
Source: "dist\Pytuber\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; NOTA: Arquivos de usuário/configuração locais nunca são sobrescritos com perda de dados

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\static\icon.ico"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\static\icon.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
