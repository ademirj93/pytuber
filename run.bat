@echo off
setlocal
title Pytuber Studio
cd /d "%~dp0"

:: Executa com o Python do ambiente virtual se existir, senao com o python do sistema
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

"%PYTHON_EXE%" main.py %*
