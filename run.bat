@echo off
title teste dola (Win10 Edition)
echo ========================================================
echo   Iniciando teste dola no Windows 10...
echo   Linguagem: Python 3
echo ========================================================
python main.py
if errorlevel 1 (
    echo.
    echo Ocorreu um erro ao iniciar. Verifique se o Python 3 esta instalado no sistema.
    pause
)
