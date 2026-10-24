@echo off
title CorteAC - Iniciador Windows 10 / 11
color 0B
echo ========================================================
echo   CorteAC (Python Edition para Windows 10 / 11)
echo   Sistema de Gestao de Ordens e Corte Jm2k / ATOM
echo ========================================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo [AVISO] Python 3 nao foi encontrado no seu PATH.
    echo.
    echo Voce pode rodar o CorteAC de duas formas faceis:
    echo.
    echo 1. BAIXAR O EXECUTAVEL PRONTO (.exe) SEM INSTALAR PYTHON:
    echo    Acesse: https://github.com/Doletabgi/Projeto-CorteAC/releases
    echo    Baixe o arquivo "CorteAC-Windows-x64.zip" ou "CorteAC.exe" e abra diretamente!
    echo.
    echo 2. INSTALAR O PYTHON 3:
    echo    Baixe em: https://www.python.org/downloads/
    echo    IMPORTANTE: Marque a opcao "Add python.exe to PATH" durante a instalacao.
    echo.
    pause
    exit /b 1
)

:: Verifica se as dependencias estao instaladas
python -c "import PIL, pymysql, cryptography" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Instalando/atualizando dependencias necessarias...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERRO] Nao foi possivel instalar as dependencias automaticamente.
        pause
        exit /b 1
    )
)

echo.
echo Iniciando o CorteAC...
echo.
python main.py
if errorlevel 1 (
    echo.
    echo [ERRO] Ocorreu um problema ao executar o CorteAC.
    pause
    exit /b 1
)
