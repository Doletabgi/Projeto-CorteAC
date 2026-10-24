#!/usr/bin/env bash
set -e
echo "========================================================"
echo "  Compilando CorteAC para Linux (Standalone)"
echo "========================================================"
cd "$(dirname "$0")"

pyinstaller --clean --onefile --add-data "assets:assets" --add-data "samples:samples" --add-data "jobmanager.db:." --add-data "db.example.ini:." --hidden-import pymysql --hidden-import cryptography --name "CorteAC" main.py

echo "Atualizando binários executáveis centralizados..."
cp -f dist/CorteAC corteac_linux
cp -f dist/CorteAC teste_dola_linux
cp -f dist/CorteAC dist/teste_dola
chmod +x corteac_linux teste_dola_linux dist/teste_dola

echo "========================================================"
echo "  Compilacao concluida com sucesso!"
echo "  Executavel gerado em: dist/CorteAC e dist/teste_dola"
echo "  Binarios locais atualizados: ./corteac_linux e ./teste_dola_linux"
echo "========================================================"
