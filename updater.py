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
APP_VERSION = "0.11.25b2"
GITHUB_OWNER = "ademirj93"
GITHUB_REPO = "pytuber"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"

def resource_path(relative_path):
    """
    Obtém o caminho absoluto para o recurso, compatível com ambiente de desenvolvimento
    e com executáveis empacotados pelo PyInstaller (--onedir e --onefile).
    """
    try:
        # PyInstaller cria pasta temporária / diretório de bundle em _MEIPASS
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


def parse_version(v_str):
    """
    Converte strings de versão como 'v0.11.25', '0.10.1' ou 'v1.0.0-rc'
    em uma tupla de inteiros para comparação semântica confiável.
    """
    if not v_str:
        return (0,)
    clean = v_str.strip().lstrip("vV")
    numbers = [int(p) for p in re.findall(r"\d+", clean)]
    return tuple(numbers) if numbers else (0,)


def is_newer_version(latest_str, current_str=APP_VERSION):
    """Retorna True se latest_str for estritamente mais recente que current_str."""
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
        self.changelog = ""
        self.asset_name = ""
        self.asset_url = ""
        self.asset_size = 0
        self.downloaded_bytes = 0
        self.total_bytes = 0
        self.progress = 0.0          # 0.0 a 1.0
        self.installer_path = ""
        self.error_message = ""
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


def check_for_updates_async(callback=None):
    """
    Inicia uma thread em segundo plano para consultar o GitHub Releases.
    Não trava a interface e trata silenciosamente falhas de rede/timeout.
    """
    def _worker():
        GLOBAL_UPDATE_INFO.set_status(UpdateStatus.CHECKING)
        try:
            req = urllib.request.Request(
                GITHUB_API_URL,
                headers={
                    "User-Agent": f"Pytuber-Updater/{APP_VERSION}",
                    "Accept": "application/vnd.github.v3+json"
                }
            )
            # Timeout curto de 8 segundos para evitar qualquer lentidão
            with urllib.request.urlopen(req, timeout=8) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode("utf-8"))
                    tag_name = data.get("tag_name", "").strip()
                    clean_version = tag_name.lstrip("vV")
                    body = data.get("body", "").strip() or "Atualizações de desempenho e melhorias visuais."
                    title = data.get("name", "") or tag_name
                    assets = data.get("assets", [])

                    if is_newer_version(tag_name, APP_VERSION):
                        matched_asset = _find_installer_asset(assets)
                        if matched_asset:
                            asset_name = matched_asset.get("name", "")
                            asset_url = matched_asset.get("browser_download_url", "")
                            asset_size = matched_asset.get("size", 0)

                            GLOBAL_UPDATE_INFO.set_status(
                                UpdateStatus.AVAILABLE,
                                latest_version=clean_version,
                                tag_name=tag_name,
                                release_title=title,
                                changelog=body,
                                asset_name=asset_name,
                                asset_url=asset_url,
                                asset_size=asset_size,
                                total_bytes=asset_size
                            )
                        else:
                            # Há nova versão mas o instalador .exe ainda não foi anexado à release
                            GLOBAL_UPDATE_INFO.set_status(
                                UpdateStatus.AVAILABLE,
                                latest_version=clean_version,
                                tag_name=tag_name,
                                release_title=title,
                                changelog=body,
                                asset_name="",
                                asset_url=data.get("html_url", ""),
                                asset_size=0
                            )
                    else:
                        GLOBAL_UPDATE_INFO.set_status(UpdateStatus.UP_TO_DATE)
                else:
                    GLOBAL_UPDATE_INFO.set_status(UpdateStatus.UP_TO_DATE)
        except Exception as e:
            # Falha de conexão, rate-limit ou offline: tratado de forma silenciosa
            GLOBAL_UPDATE_INFO.set_status(UpdateStatus.ERROR, error_message=str(e))
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
                headers={"User-Agent": f"Pytuber-Updater/{APP_VERSION}"}
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
    Executa o instalador baixado via subprocess.Popen e encerra o Pytuber
    de forma limpa para permitir que os arquivos sejam substituídos pelo Inno Setup.
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
