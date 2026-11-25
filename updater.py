"""
updater.py - Módulo de Verificação e Atualização Automática do Pytuber
Gerencia a consulta à API do GitHub Releases, comparação semântica de versões,
download assíncrono do instalador e execução limpa com encerramento do app.
"""

import os
import sys
import ctypes
import json
import re
import time
import tempfile
import threading
import subprocess
import urllib.request
import urllib.error

# --- Versão e Metadados Centrais ---
APP_VERSION = "0.11.25b3"
RELEASE_DATE = "25/11/2026"
GITHUB_OWNER = "ademirj93"
GITHUB_REPO = "pytuber"
GITHUB_RELEASES_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases"
GITHUB_LATEST_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"

def resource_path(relative_path):
    """
    Obtém o caminho absoluto para o recurso, compatível com ambiente de desenvolvimento
    e com executáveis empacotados pelo PyInstaller (--onedir e --onefile).
    """
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(os.path.dirname(__file__))

    direct_path = os.path.join(base_path, relative_path)
    if os.path.exists(direct_path):
        return direct_path

    # Fallback para caso seja passado apenas o nome do arquivo que está em static/
    static_fallback = os.path.join(base_path, "static", relative_path)
    if os.path.exists(static_fallback):
        return static_fallback

    return direct_path


def normalize_version(v_str):
    """Normaliza strings de versão removendo prefixos 'v', espaços e padronizando separadores."""
    if not v_str:
        return ""
    clean = str(v_str).strip().lstrip("vV").lower()
    return re.sub(r"[-_]", ".", clean)


def parse_version(v_str):
    """
    Converte strings de versão como 'v0.11.25', '0-11-25', '0.11.25b2', '0.9.0'
    em uma tupla numérica comparável (ex: [0, 11, 25, 2]).
    """
    if not v_str:
        return (0, 0, 0, 0)
    clean = normalize_version(v_str)
    nums = [int(p) for p in re.findall(r"\d+", clean)]
    while len(nums) < 4:
        nums.append(0)
    return tuple(nums)


def extract_release_version(tag_name, release_name):
    """
    Determina a versão canônica e limpa da release.
    Dá prioridade ao nome da release quando contiver indicação de versão (ex: 'V0.11.25b2'),
    evitando que tags de controle do repositório como '0-11-25-hotfix' causem falsos positivos.
    """
    m_name = re.search(r"v?(\d+[\.\-_]\d+(?:[\.\-_]\d+)?(?:[a-zA-Z0-9\.\-_]+)?)", release_name, re.IGNORECASE)
    m_tag = re.search(r"v?(\d+[\.\-_]\d+(?:[\.\-_]\d+)?(?:[a-zA-Z0-9\.\-_]+)?)", tag_name, re.IGNORECASE)

    if m_name and ("hotfix" in tag_name.lower() or "release" in tag_name.lower()):
        raw = m_name.group(1)
    elif m_name and not release_name.lower().startswith("pytuber"):
        raw = m_name.group(1)
    elif m_tag:
        raw = m_tag.group(1)
    elif m_name:
        raw = m_name.group(1)
    else:
        raw = release_name or tag_name

    clean = raw.strip().lstrip("vV")
    clean = re.sub(r"(?<=\d)-(?=\d)", ".", clean)
    return clean


def is_newer_version(latest_str, current_str=APP_VERSION):
    """Retorna True se latest_str for estritamente mais recente que current_str."""
    if normalize_version(latest_str) == normalize_version(current_str):
        return False
    return parse_version(latest_str) > parse_version(current_str)


class UpdateStatus:
    IDLE = "IDLE"
    CHECKING = "CHECKING"
    AVAILABLE = "AVAILABLE"
    UP_TO_DATE = "UP_TO_DATE"
    DOWNLOADING = "DOWNLOADING"
    DOWNLOADED = "DOWNLOADED"
    INSTALLING = "INSTALLING"
    ERROR = "ERROR"


class UpdateInfo:
    """Estrutura com dados e estado da atualização."""
    def __init__(self):
        self.status = UpdateStatus.IDLE
        self.latest_version = ""
        self.tag_name = ""
        self.release_title = ""
        self.release_date = ""
        self.changelog = ""
        self.asset_name = ""
        self.asset_url = ""
        self.asset_size = 0
        self.downloaded_bytes = 0
        self.total_bytes = 0
        self.progress = 0.0          # 0.0 a 1.0
        self.installer_path = ""
        self.error_message = ""
        self.is_manual_check = False
        self.last_checked_time = 0
        self.lock = threading.Lock()

    def set_status(self, status, **kwargs):
        with self.lock:
            self.status = status
            for k, v in kwargs.items():
                if hasattr(self, k):
                    setattr(self, k, v)


# Instância global do estado de atualização
GLOBAL_UPDATE_INFO = UpdateInfo()


def _find_installer_asset(assets):
    """Busca nos assets da release o instalador do Pytuber (.exe)."""
    if not assets:
        return None
    # 1. Prioridade máxima: Pytuber_Setup_*.exe
    for a in assets:
        name = a.get("name", "")
        if name.lower().startswith("pytuber_setup") and name.lower().endswith(".exe"):
            return a
    # 2. Prioridade secundária: Qualquer *Setup*.exe
    for a in assets:
        name = a.get("name", "")
        if "setup" in name.lower() and name.lower().endswith(".exe"):
            return a
    # 3. Qualquer executável disponível nos assets
    for a in assets:
        name = a.get("name", "")
        if name.lower().endswith(".exe"):
            return a
    return None


def format_iso_date(iso_str):
    """Converte '2026-11-25T16:02:44Z' em '25/11/2026'."""
    if not iso_str:
        return ""
    try:
        parts = iso_str[:10].split("-")
        if len(parts) == 3:
            return f"{parts[2]}/{parts[1]}/{parts[0]}"
    except Exception:
        pass
    return iso_str[:10]


def check_for_updates_async(callback=None, manual=False):
    """
    Inicia uma thread em segundo plano para consultar o GitHub Releases.
    Consulta a lista de releases para suportar releases, tags e pré-lançamentos.
    Não trava a interface gráfica.
    """
    def _worker():
        GLOBAL_UPDATE_INFO.set_status(UpdateStatus.CHECKING, is_manual_check=manual)
        try:
            headers = {
                "User-Agent": f"Pytuber-Studio/{APP_VERSION}",
                "Accept": "application/vnd.github.v3+json"
            }

            data = None
            # 1. Tenta buscar lista completa de releases
            try:
                req = urllib.request.Request(GITHUB_RELEASES_URL, headers=headers)
                with urllib.request.urlopen(req, timeout=10) as response:
                    if response.status == 200:
                        data = json.loads(response.read().decode("utf-8"))
            except Exception:
                data = None

            # 2. Fallback para /releases/latest se lista falhar
            if not data or not isinstance(data, list):
                try:
                    req_latest = urllib.request.Request(GITHUB_LATEST_URL, headers=headers)
                    with urllib.request.urlopen(req_latest, timeout=10) as response:
                        if response.status == 200:
                            single = json.loads(response.read().decode("utf-8"))
                            data = [single] if single else []
                except Exception as e_latest:
                    raise e_latest

            if not data:
                GLOBAL_UPDATE_INFO.set_status(
                    UpdateStatus.UP_TO_DATE,
                    error_message="",
                    last_checked_time=time.time()
                )
                return

            # Filtra releases que não sejam rascunhos (drafts)
            valid_releases = [r for r in data if not r.get("draft", False)]
            if not valid_releases:
                GLOBAL_UPDATE_INFO.set_status(UpdateStatus.UP_TO_DATE, last_checked_time=time.time())
                return

            # A lista do GitHub já é fornecida em ordem cronológica (a mais recente publicada no topo)
            target_release = valid_releases[0]

            tag_name = target_release.get("tag_name", "").strip()
            release_name = target_release.get("name", "").strip() or tag_name
            clean_version = extract_release_version(tag_name, release_name)
            
            body = target_release.get("body", "").strip() or "Melhorias de desempenho e estabilidade."
            pub_date = format_iso_date(target_release.get("published_at", ""))
            assets = target_release.get("assets", [])

            # Busca instalador .exe na release principal ou nas outras releases públicas
            matched_asset = _find_installer_asset(assets)
            if not matched_asset:
                for other_rel in valid_releases[1:]:
                    matched_asset = _find_installer_asset(other_rel.get("assets", []))
                    if matched_asset:
                        break

            # Avalia se a versão encontrada é estritamente superior à atual
            if is_newer_version(clean_version, APP_VERSION):
                asset_name = matched_asset.get("name", "") if matched_asset else ""
                asset_url = matched_asset.get("browser_download_url", "") if matched_asset else target_release.get("html_url", "")
                asset_size = matched_asset.get("size", 0) if matched_asset else 0

                GLOBAL_UPDATE_INFO.set_status(
                    UpdateStatus.AVAILABLE,
                    latest_version=clean_version,
                    tag_name=tag_name,
                    release_title=release_name,
                    release_date=pub_date,
                    changelog=body,
                    asset_name=asset_name,
                    asset_url=asset_url,
                    asset_size=asset_size,
                    total_bytes=asset_size,
                    last_checked_time=time.time()
                )
            else:
                GLOBAL_UPDATE_INFO.set_status(
                    UpdateStatus.UP_TO_DATE,
                    latest_version=clean_version,
                    tag_name=tag_name,
                    release_title=release_name,
                    release_date=pub_date,
                    last_checked_time=time.time()
                )

        except urllib.error.HTTPError as he:
            err_msg = f"HTTP {he.code}: {he.reason}"
            if he.code == 403:
                err_msg = "Limite de consultas do GitHub atingido temporariamente."
            GLOBAL_UPDATE_INFO.set_status(UpdateStatus.ERROR, error_message=err_msg, last_checked_time=time.time())
        except Exception as e:
            GLOBAL_UPDATE_INFO.set_status(UpdateStatus.ERROR, error_message="Sem conexão com a internet ou GitHub indisponível.", last_checked_time=time.time())
        finally:
            if callback:
                try:
                    callback(GLOBAL_UPDATE_INFO)
                except Exception:
                    pass

    t = threading.Thread(target=_worker, name="PytuberUpdateChecker", daemon=True)
    t.start()
    return t


def download_update_async(update_info=None, on_progress=None, on_complete=None, on_error=None):
    """
    Baixa o instalador .exe para a pasta temporária do Windows com feedback de progresso.
    """
    info = update_info or GLOBAL_UPDATE_INFO
    if not info.asset_url:
        if on_error:
            on_error("URL de download indisponível.")
        return None

    def _worker():
        info.set_status(UpdateStatus.DOWNLOADING, progress=0.0, downloaded_bytes=0)
        dest_filename = info.asset_name or f"Pytuber_Setup_v{info.latest_version}.exe"
        temp_dir = tempfile.gettempdir()
        dest_path = os.path.join(temp_dir, dest_filename)

        try:
            req = urllib.request.Request(
                info.asset_url,
                headers={"User-Agent": f"Pytuber-Studio/{APP_VERSION}"}
            )
            with urllib.request.urlopen(req, timeout=30) as resp, open(dest_path, "wb") as out_file:
                total_size = int(resp.headers.get("Content-Length", info.asset_size or 0))
                info.total_bytes = total_size
                downloaded = 0
                chunk_size = 64 * 1024  # 64 KB

                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    out_file.write(chunk)
                    downloaded += len(chunk)
                    prog = (downloaded / total_size) if total_size > 0 else 0.0
                    info.set_status(
                        UpdateStatus.DOWNLOADING,
                        downloaded_bytes=downloaded,
                        progress=min(1.0, prog)
                    )
                    if on_progress:
                        try:
                            on_progress(prog, downloaded, total_size)
                        except Exception:
                            pass

            info.set_status(
                UpdateStatus.DOWNLOADED,
                installer_path=dest_path,
                progress=1.0
            )
            if on_complete:
                try:
                    on_complete(dest_path)
                except Exception:
                    pass

        except Exception as e:
            info.set_status(UpdateStatus.ERROR, error_message=str(e))
            if on_error:
                try:
                    on_error(str(e))
                except Exception:
                    pass

    t = threading.Thread(target=_worker, name="PytuberUpdateDownloader", daemon=True)
    t.start()
    return t


def launch_installer_and_exit(installer_path=None):
    """
    Executa o instalador baixado via subprocess.Popen com privilégios de Administrador
    e encerra o Pytuber de forma limpa para permitir a substituição dos arquivos pelo Inno Setup.
    """
    path_to_run = installer_path or GLOBAL_UPDATE_INFO.installer_path
    if not path_to_run or not os.path.exists(path_to_run):
        return False

    GLOBAL_UPDATE_INFO.set_status(UpdateStatus.INSTALLING)

    try:
        # Inicia o instalador com privilégios de Administrador
        if sys.platform == "win32":
            ret = ctypes.windll.shell32.ShellExecuteW(
                None,
                "runas",
                path_to_run,
                None,
                None,
                1  # SW_SHOWNORMAL
            )
            if ret <= 32:
                # Fallback caso o usuário use outro mecanismo ou recuse
                subprocess.Popen(
                    [path_to_run],
                    shell=False,
                    creationflags=subprocess.DETACHED_PROCESS
                )
        else:
            subprocess.Popen([path_to_run], shell=False)
    except Exception as e:
        print(f"Erro ao disparar instalador: {e}")
        return False

    # Encerra pygame limpo se estiver carregado
    if "pygame" in sys.modules:
        try:
            import pygame
            pygame.quit()
        except Exception:
            pass

    # Encerra o processo atual imediatamente
    sys.exit(0)
