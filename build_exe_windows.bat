@echo off
title Compilando CorteAC para Windows (.exe)
echo ========================================================
echo   Compilando CorteAC para Windows 10 / 11 (.exe)
echo ========================================================
echo.

python -m pip install --upgrade pyinstaller
if errorlevel 1 (
    echo [ERRO] Nao foi possivel instalar o PyInstaller. Verifique a conexao ou o Python.
    pause
    exit /b 1
)

echo.
echo Gerando executavel standalone (CorteAC.exe)...
pyinstaller --clean --onefile --noconsole --icon "assets/app_icon.ico" --add-data "assets;assets" --add-data "samples;samples" --name "CorteAC" main.py

if errorlevel 1 (
    echo.
    echo [ERRO] Ocorreu uma falha na compilacao.
    pause
    exit /b 1
)

echo.
echo ========================================================
echo   Compilacao concluida com sucesso!
echo   Executavel gerado em: dist\CorteAC.exe
echo ========================================================
pause
