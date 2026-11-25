@echo off
setlocal
title Compilando Pytuber com PyInstaller e Inno Setup

echo ==============================================================================
echo  INICIANDO PROCESSO DE COMPILACAO E EMPACOTAMENTO DO PYTUBER
echo ==============================================================================
echo.

:: Verifica se o ambiente virtual existe e usa seu python, caso contrario usa python do PATH
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

"%PYTHON_EXE%" build.py

if errorlevel 1 (
    echo.
    echo [ERRO] Ocorreu uma falha durante o processo de build.
    pause
    exit /b 1
)

echo.
echo ==============================================================================
echo  PROCESSO CONCLUIDO COM SUCESSO!
echo ==============================================================================
pause
