# Registro de Modificações (Changelog) - Pytuber

Todas as alterações notáveis deste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/),
e este projeto adere ao [Versionamento Semântico](https://semver.org/lang/pt-BR/).

---

## [0.9.0] - 25/11/2026

### 🎨 Nova Interface Gráfica Studio (Dark Mode)
- **Design System Moderno:** Redesenho completo da interface inspirado em ferramentas profissionais como **OBS Studio**, **Discord** e **Veadotube**.
- **Paleta Dark Mode:** Cores escuras de alto contraste (`#121216` fundo principal, `#1C1C22` cards e painéis agrupados com bordas sutis `#2A2A32`, `#26262E` para botões neutros e inputs).
- **Cor de Destaque Unificada:** Uso de cores de destaque vibrantes (`#6366F1` / `#10B981`) restritas a ações primárias (botão "INICIAR", switches ativos e medidor de áudio).
- **Layout em 2 Colunas:**
  - **Coluna Esquerda:** Visualização ao vivo do personagem montado reagindo ao microfone em tempo real, badge de status dinâmico (`● Silêncio` / `● Falando`), botão de destaque em largura total **"▶ INICIAR"** e toggle de Câmera Virtual.
  - **Coluna Direita:** Seções agrupadas em cards com bordas arredondadas de 12px (Camadas/Sprites, Áudio e Ajustes de Renderização).
- **Cards de Sprites Otimizados:** Cada camada (Base, Olhos Abertos, Olhos Fechados, Boca Aberta) agora possui miniatura (thumbnail 32x32px), rótulo e nome de arquivo limpo com botão compacto de seleção.
- **Painel de Áudio Refatorado:** Dropdown de microfones com botão de atualização dinâmica (`↻`), medidor de volume sonoro com gradiente visual suave integrado ao controle de sensibilidade.
- **Ajustes de Renderização Modernos:**
  - Substituição de botões ON/OFF por **Toggle Switches** modernos (Transparente, Sem Bordas, Contorno Sólido e Animações).
  - Indicador visual da cor de fundo (swatch) atualizado dinamicamente.
  - **Controle Segmentado (Segmented Control)** para seleção rápida de FPS: `[ 30 | 60 | 120 ]`.
- **Nova Identidade Visual:** Novo logotipo 512x512 em alta definição salvo em `static/PyTuber.png`, com estética de avatar VTuber com headset e iluminação neon.

---

### 🎯 Sistema de Ponto de Ancoragem (Anchor Point)
- **Retícula de Ancoragem Central:** Adicionado ponto de âncora visual no centro do personagem base (`char`).
- **Alinhamento em Tempo Real:** Linhas guias inteligentes desenhadas em tempo real conectando a âncora aos olhos, boca e acessórios.
- **Coordenadas Relativas Delta:** Exibição contínua na tela dos valores de deslocamento `Δ (X, Y)` em pixels, facilitando o alinhamento simétrico e a calibração de peças.
- **Padronização:** A mesma lógica de ancoragem foi implementada tanto no modo de **Edição de Posições** quanto no **Guarda-Roupa**.

---

### 👗 Guarda-Roupa & Acessórios (Wardrobe)
- **Ajuste de Escala (Tamanho) dos Acessórios:**
  - Slider interativo com arraste suave na barra de controles do preview.
  - Botões de incremento/decremento fino `[-]` e `[+]` e atalho de restauração `1.0x`.
  - Controle de escala contínuo via rotação da roda do mouse (*Scroll*) sobre o acessório.
  - Campo numérico de escala direta na janela de propriedades do item.
- **Janela de Configurações do Item Redesenhada:**
  - Correção das áreas de clique e hitboxes dos botões de ação.
  - Novos ícones minimalistas estilo **Bootstrap Icons**: lápis (`bi-pencil-fill`) para edição e lixeira (`bi-trash-fill`) para exclusão.
- **Trava de Segurança (Lock):** Opção para travar peças no lugar, evitando movimentação acidental enquanto outros acessórios são posicionados.
- **Camadas em 1 Clique:** Alternância instantânea de profundidade entre **Frente**, **Meio** e **Trás**.
- **Categorização em Acordeão:** Suporte a Chapéus, Acessórios, Camisas, Casacos, Calças, Maquiagem, Objetos de Cena e Cor dos Olhos.

---

### 📹 Câmera Virtual & Streaming
- **Toggle de Câmera Virtual com Consentimento:** Ao ativar a chave de câmera virtual, o aplicativo solicita autorização do usuário antes de carregar ou instalar a dependência `pyvirtualcam`.
- **Compatibilidade com Python 3.14.10:** Ajuste do ecossistema e bibliotecas para rodar nativamente em versões modernas do Python com suporte a `pygame-ce 2.5.8+` e wheels oficiais Windows x64.
- **Modo OBS Studio:** Otimização do modo Transparente / Sem Bordas para Captura de Jogo (*Game Capture*) com suporte nativo a canal Alpha sem necessidade de chroma key verde artificial.

---

### 🔄 Sistema de Verificação e Atualização Automática (Auto-Updater)
- **Módulo Centralizado (`updater.py`):**
  - Definição da constante global `APP_VERSION = "0.9.0"`.
  - Consulta assíncrona à API de Releases do GitHub (`https://api.github.com/repos/ademirj93/pytuber/releases/latest`) em thread separada na inicialização do app.
  - Comparador semântico de versões integrado (sem dependência de bibliotecas externas pesadas).
  - Tratamento tolerante a falhas (conexão offline, timeout ou rate limit são ignorados silenciosamente sem travar o app).
- **Interface de Atualização Integrada:**
  - Modal dark mode com cabeçalho de aviso, número da nova versão e caixa de rolagem com o *changelog* oficial da release.
  - Botão de download com barra de progresso animada em tempo real.
  - Download direto do instalador `.exe` para a pasta temporária do Windows (`%TEMP%`).
  - Execução automática do instalador via `subprocess.Popen` e fechamento limpo do Pytuber em execução para permitir sobrescrita de arquivos.
- **Compatibilidade com Executável Compilado:**
  - Implementação da função `resource_path(relative_path)` com suporte a `sys._MEIPASS` para carregar ícones e assets tanto no ambiente de desenvolvimento quanto no binário compilado.

---

### 📦 Pipeline de Compilação & Empacotamento
- **Script de Compilação Automatizado (`build.py` / `build.bat`):**
  - Limpeza automática de diretórios de build anteriores (`build/`, `dist/`).
  - Resolução do problema de isolamento de bibliotecas (`ModuleNotFoundError: No module named 'pygame'`): vinculação explícita da pasta de pacotes do ambiente virtual (`.venv\Lib\site-packages`) via `--paths` e `--collect-all`.
  - Configuração do PyInstaller em modo `--onedir` e `--windowed` (sem tela preta de prompt do DOS), com ícone oficial `static/icon.ico`.
  - Integração direta em 1 comando com o compilador do Inno Setup 7 (`ISCC.exe`).
- **Script do Instalador Profissional (`setup.iss`):**
  - GUID único e fixo (`AppId={{8B1D4F37-9A63-4C3D-81F9-2A5817E294B1}}`), garantindo que atualizações futuras sobrescrevam a versão anterior sem duplicar entradas no Painel de Controle.
  - Compressão ultra eficiente LZMA2 (`Compression=lzma2/ultra64`).
  - Suporte a múltiplos idiomas (Português Brasileiro e Inglês).
  - Criação de atalhos na Área de Trabalho e Menu Iniciar, com desinstalador limpo.
  - Opção de inicialização automática ao término da instalação.
  - Padrão de saída: `Pytuber_Setup_v{#MyAppVersion}.exe`.

---

### 🛡️ Execução Como Administrador & Armazenamento no Disco C
- **Elevação Automática UAC:** Implementação da função `ensure_admin()` em `main.py` utilizando a API nativa do Windows (`ctypes.windll.shell32.IsUserAnAdmin()` e `ShellExecuteW` com verbo `'runas'`). Se o script não for executado como Administrador, o prompt UAC é disparado automaticamente.
- **Preservação de Diretório de Trabalho:** Ao elevar o processo, o diretório base da aplicação é mantido, prevenindo que o Windows mude o diretório padrão para `C:\Windows\System32`.
- **Permissão Total no Disco C:** Garante que a criação de pastas e gravação de arquivos de assets e configurações em diretórios protegidos (como `C:\Program Files\Pytuber\assets` ou na raiz do disco C:) ocorram sem erros de permissão (`PermissionError: [Errno 13]`).
- **Manifesto Embutido no PyInstaller:** Adicionada a flag `--uac-admin` no script [build.py](file:///c:/Users/Ademir/Projetos/pytuber/build.py), embutindo o manifesto `requireAdministrator` no cabeçalho do executável compilado `Pytuber.exe`.
- **Instalador com Permissões de Administrador:** Atualizado [setup.iss](file:///c:/Users/Ademir/Projetos/pytuber/setup.iss) com `PrivilegesRequired=admin` e permissões explícitas `users-full` nas pastas `{app}\assets` e `{app}\static`.
- **Launcher de Execução Direta:** Adicionado o script [run.bat](file:///c:/Users/Ademir/Projetos/pytuber/run.bat) para inicialização rápida com detecção automática do ambiente virtual.

---

### 🐛 Correções de Bugs (Bug Fixes)
- **Menu de Edição de Posições:** Corrigido o botão "Salvar e Voltar", que não persistia as alterações ou travava a navegação de retorno ao menu principal.
- **Hitboxes dos Botões:** Ajustada a área de colisão do mouse em botões de ação e ícones de edição/exclusão no guarda-roupa.
- **Gerenciamento de Recursos:** Garantido que ícones e arquivos estáticos sejam localizados corretamente em qualquer diretório de trabalho.

---

## [0.8.0] - Versão Anterior
- Implementação inicial do motor 2D em Pygame.
- Reconhecimento básico de entrada de áudio via microfone.
- Alternância de sprites de boca aberta/fechada e olhos abertos/fechados.
- Suporte inicial a acessórios básicos.
