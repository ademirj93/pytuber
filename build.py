#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
build.py - Script de Compilação e Empacotamento Automatizado do Pytuber
Executa a limpeza, compilação com PyInstaller (--onedir) e criação do instalador Inno Setup.
Garante que o ambiente virtual (.venv) e todas as bibliotecas (pygame, numpy, sounddevice, pyvirtualcam)
sejam 100% incorporados ao executável final.
"""

import os
import sys
import shutil
import subprocess

# Tenta carregar a versão centralizada do updater.py
try:
    from updater import APP_VERSION
except ImportError:
    APP_VERSION = "0.9.0"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def print_header(title):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)

def clean_previous_builds():
    """Remove pastas de compilações anteriores (build, dist)."""
    print_header("1. LIMPANDO DIRETÓRIOS DE BUILD ANTERIORES")
    dirs_to_clean = [
        os.path.join(BASE_DIR, "build"),
        os.path.join(BASE_DIR, "dist")
    ]
    for d in dirs_to_clean:
        if os.path.exists(d):
            print(f"-> Removendo: {d}")
            try:
                shutil.rmtree(d)
            except Exception as e:
                print(f"   [Aviso] Não foi possível remover {d}: {e}")
    print("-> Limpeza concluída!")

def resolve_pyinstaller_command():
    """
    Localiza o PyInstaller e garante a resolução das bibliotecas do .venv.
    Retorna uma tupla (cmd_base, venv_site_packages, env_dict).
    """
    venv_python = os.path.join(BASE_DIR, ".venv", "Scripts", "python.exe")
    venv_site_packages = os.path.join(BASE_DIR, ".venv", "Lib", "site-packages")
    env = os.environ.copy()

    # Se existe .venv, inclui no PYTHONPATH para que o PyInstaller encontre tudo
    if os.path.exists(venv_site_packages):
        current_pp = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = f"{venv_site_packages};{current_pp}" if current_pp else venv_site_packages

    # 1. Verifica se PyInstaller está instalado dentro do .venv
    if os.path.exists(venv_python):
        try:
            res = subprocess.run([venv_python, "-m", "PyInstaller", "--version"], capture_output=True, text=True)
            if res.returncode == 0:
                print(f"-> Usando PyInstaller da .venv ({res.stdout.strip()}): {venv_python}")
                return [venv_python, "-m", "PyInstaller"], venv_site_packages, env
        except Exception:
            pass

    # 2. Verifica se PyInstaller está no ambiente do python atual
    try:
        res = subprocess.run([sys.executable, "-m", "PyInstaller", "--version"], capture_output=True, text=True)
        if res.returncode == 0:
            print(f"-> Usando PyInstaller de {sys.executable} ({res.stdout.strip()})")
            return [sys.executable, "-m", "PyInstaller"], venv_site_packages, env
    except Exception:
        pass

    # 3. Tenta chamar o comando py -3.14 -m PyInstaller
    try:
        res = subprocess.run(["py", "-3.14", "-m", "PyInstaller", "--version"], capture_output=True, text=True)
        if res.returncode == 0:
            print(f"-> Usando PyInstaller via launcher py -3.14 ({res.stdout.strip()})")
            return ["py", "-3.14", "-m", "PyInstaller"], venv_site_packages, env
    except Exception:
        pass

    # 4. Fallback para pyinstaller no PATH
    which_pyi = shutil.which("pyinstaller")
    if which_pyi:
        print(f"-> Usando PyInstaller do PATH: {which_pyi}")
        return [which_pyi], venv_site_packages, env

    return None, venv_site_packages, env

def run_pyinstaller():
    """Compila o aplicativo com PyInstaller no modo --onedir incorporando o .venv."""
    print_header(f"2. COMPILANDO PYTUBER v{APP_VERSION} COM PYINSTALLER")
    
    cmd_base, venv_site_packages, env = resolve_pyinstaller_command()
    if not cmd_base:
        print("[ERRO] PyInstaller não encontrado!")
        print("Instale o PyInstaller no ambiente com:")
        print("  .\\.venv\\Scripts\\python.exe -m pip install pyinstaller")
        return False

    static_src = os.path.join(BASE_DIR, "static")
    assets_src = os.path.join(BASE_DIR, "assets")
    icon_src = os.path.join(static_src, "icon.ico")

    pyinstaller_cmd = list(cmd_base) + [
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--name=Pytuber",
        f"--icon={icon_src}",
        f"--add-data={static_src};static",
        f"--add-data={assets_src};assets",
        "--clean",
    ]

    # Incorpora explicitamente a pasta site-packages do .venv para garantir
    # que pygame, numpy, sounddevice e pyvirtualcam sejam empacotados
    if os.path.exists(venv_site_packages):
        print(f"-> Vinculando bibliotecas do ambiente virtual: {venv_site_packages}")
        pyinstaller_cmd.extend([
            f"--paths={venv_site_packages}",
            "--collect-all=pygame",
            "--collect-all=pyvirtualcam",
            "--collect-all=sounddevice",
            "--collect-all=numpy"
        ])

    pyinstaller_cmd.append(os.path.join(BASE_DIR, "main.py"))

    print("\nComando de execução:")
    print(" ".join(pyinstaller_cmd) + "\n")
    
    result = subprocess.run(pyinstaller_cmd, cwd=BASE_DIR, env=env)
    if result.returncode != 0:
        print(f"\n[ERRO] Falha na compilação do PyInstaller (código {result.returncode})")
        return False

    print("\n-> Compilação do PyInstaller finalizada com sucesso!")
    return True

def find_inno_setup_compiler():
    """Localiza o compilador do Inno Setup (ISCC.exe)."""
    candidates = [
        r"C:\Program Files\Inno Setup 7\ISCC.exe",
        r"C:\Program Files (x86)\Inno Setup 7\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        shutil.which("ISCC.exe")
    ]
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    return None

def build_installer():
    """Gera o instalador .exe chamando o Inno Setup."""
    print_header("3. CRIANDO INSTALADOR COM INNO SETUP")
    
    iscc_path = find_inno_setup_compiler()
    if not iscc_path:
        print("[Aviso] Compilador do Inno Setup (ISCC.exe) não foi encontrado.")
        print("Para gerar o instalador manualmente, abra o arquivo 'setup.iss' no Inno Setup e clique em 'Compile'.")
        return False

    iss_file = os.path.join(BASE_DIR, "setup.iss")
    if not os.path.exists(iss_file):
        print(f"[ERRO] Arquivo {iss_file} não encontrado!")
        return False

    print(f"-> Usando Inno Setup: {iscc_path}")
    iscc_cmd = [
        iscc_path,
        f"/DMyAppVersion={APP_VERSION}",
        iss_file
    ]

    result = subprocess.run(iscc_cmd, cwd=BASE_DIR)
    if result.returncode != 0:
        print(f"\n[ERRO] Falha na criação do instalador pelo Inno Setup (código {result.returncode})")
        return False

    installer_output = os.path.join(BASE_DIR, "dist", "installer", f"Pytuber_Setup_v{APP_VERSION}.exe")
    print("\n" + "=" * 70)
    print("  SUCESSO! INSTALADOR GERADO COM ÊXITO")
    print("=" * 70)
    print(f"-> Arquivo do Instalador: {installer_output}")
    if os.path.exists(installer_output):
        print(f"-> Tamanho: {os.path.getsize(installer_output) / (1024*1024):.2f} MB")
    print(f"-> Pronto para anexar na release do GitHub como 'Pytuber_Setup_v{APP_VERSION}.exe'!")
    return True

def main():
    clean_previous_builds()
    if not run_pyinstaller():
        sys.exit(1)
    build_installer()

if __name__ == "__main__":
    main()
