# Registro de Modificações (Changelog) - Pytuber

Todas as alterações notáveis deste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/),
e este projeto adere ao [Versionamento Semântico](https://semver.org/lang/pt-BR/).

---

## [0.11.25b3] - 25/11/2026

### ✨ Novas Funcionalidades
- **Janela Modal "Sobre o Pytuber Studio":**
  - Adicionado botão e modal interativo moderno em Dark Mode exibindo o logotipo oficial em alta resolução (`PyTuber.png`), versão ativa, data da release e créditos.
  - Exibição detalhada do ambiente de execução: versão do interpretador Python e arquitetura (`Python 3.14.10 64-bit`) e versão do sistema operacional Windows (`Windows 11 Build 22631+`).
  - Diagnóstico completo de bibliotecas instaladas com suas respectivas versões: `pygame-ce`, `numpy`, `sounddevice` e status da `pyvirtualcam`.
  - Botão integrado "Buscar Atualizações" diretamente dentro da janela de Sobre.
- **Botão e Sistema de Verificação Manual de Atualizações:**
  - Novo botão "Atualizações" no cabeçalho superior com ícone vetorial de sincronização (`bi-arrow-repeat`) para checagem instantânea de novidades.
  - Badge dinâmico de status no topo (`↻ Verificando...`, `⬆ Nova Versão`, `✓ Atualizado` ou `Baixando...`).
  - Feedback visual imediato via notificações tipo *toast* informando se o sistema já está na versão mais recente ou se há nova versão disponível.
- **Ícones Vetoriais Estilo Bootstrap Icons nos Botões:**
  - Substituição de glifos de texto unicode por ícones vetoriais desenhados nativamente com anti-aliasing nos botões do cabeçalho e modais:
    - Botão "Atualizações": Ícone de recarga/sincronização (`bi-arrow-repeat`).
    - Botão "Sobre": Ícone de informação circular (`bi-info-circle`).
    - Botão "Carregar": Ícone de pasta aberta (`bi-folder2-open`).
    - Botão "Salvar": Ícone de disquete/salvamento (`bi-floppy`).
    - Botão Fechar `[✕]`: Ícone vetorial anti-aliased em cruz diagonal nos modais de Atualização e Sobre.

### 🛡️ Permissões de Administrador & Armazenamento no Disco C
- **Auto-Elevação UAC no Windows:** Implementada rotina `ensure_admin()` em `main.py` com `ctypes.windll.shell32.ShellExecuteW(..., 'runas', ...)`. Se o aplicativo for iniciado sem privilégios administrativos, o prompt de elevação UAC do Windows é disparado automaticamente.
- **Preservação de Diretório de Trabalho (`os.chdir`):** Prevenção contra o comportamento padrão do Windows de alterar o diretório de processos elevados para `C:\Windows\System32`, garantindo que assets e configurações sejam salvos na pasta correta no disco `C:`.
- **Manifesto de Administrador Embutido:** Adicionada a flag `--uac-admin` no script de compilação [build.py](build.py), embutindo a diretiva `requireAdministrator` no executável gerado `Pytuber.exe`.
- **Permissões Totais no Instalador:** Atualizado [setup.iss](setup.iss) com `PrivilegesRequired=admin` e permissões `users-full` nas pastas `{app}\assets` e `{app}\static`.
- **Launcher `run.bat`:** Criado script de execução rápida na raiz do projeto com detecção e ativação automática do ambiente virtual `.venv`.

### 🐛 Correções de Bugs (Bug Fixes)
- **Carregamento de Ícone no Pygame:** Corrigido o erro `Erro ao carregar o ícone: Unsupported ICO bitmap format` no SDL/Pygame ao definir o ícone da janela; agora o carregamento utiliza o arquivo PNG oficial [PyTuber.png](static/PyTuber.png) com escala suave de 64x64 e canal alfa nativo.
- **Correção da Identificação de Tags e Falsos Positivos de Atualização:**
  - Corrigido o comparador de versão em [updater.py](updater.py) que causava falsos alertas de "Nova versão disponível" para quem já estava na versão mais recente (`0.11.25b2`), devido ao sufixo de controle interno `hotfix` e reordenação indevida da lista de releases.
  - Implementada a função `extract_release_version` para extrair a versão canônica priorizando o nome da release quando explícito (ex: `V0.11.25b3`), com verificação de identidade em `is_newer_version`.
  - A checagem agora respeita estritamente a ordem cronológica real de publicação do GitHub (`releases[0]`).
- **Busca Abrangente de Instaladores:** O atualizador agora localiza assets de instaladores `.exe` vinculados a releases irmãs quando a release mais recente no GitHub for criada como tag de anúncio sem anexos diretos.

---

## [0.11.25b2] - 25/11/2026
- Ajustes de estabilidade no motor de streaming e compatibilidade com Python 3.14.10.
- Implementação inicial do módulo de verificação assíncrona com GitHub Releases.
- Criação do pipeline de compilação com Inno Setup 7 e PyInstaller `--onedir`.

---

## [0.11.25] - 25/11/2026
- Redesenho completo da interface para o visual Studio Dark Mode (`#121216`, `#1C1C22`, `#26262E`, `#6366F1`).
- Layout em 2 colunas com preview reativo ao microfone em tempo real.
- Sistema de ponto de ancoragem central (*Anchor Point*) com coordenadas relativas `Δ (X, Y)`.
- Guarda-roupa modular com ajuste de escala contínuo de acessórios e camadas (Frente/Meio/Trás).
- Integração nativa para OBS Studio com transparência Alpha via Captura de Jogo e suporte à Câmera Virtual.
- Correção do botão "Salvar e Voltar" no modo de posições.

---

## [0.8.0] - Versão Anterior
- Implementação inicial do motor 2D em Pygame.
- Reconhecimento básico de áudio por limiar de volume e alternância de sprites.
