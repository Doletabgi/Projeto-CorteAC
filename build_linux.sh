#!/usr/bin/env bash
set -e
echo "========================================================"
echo "  Compilando CorteAC para Linux (Standalone)"
echo "========================================================"
cd "$(dirname "$0")"

pyinstaller --clean --onefile --add-data "assets:assets" --add-data "samples:samples" --add-data "jobmanager.db:." --add-data "db.example.ini:." --hidden-import pymysql --hidden-import cryptography --name "CorteAC" main.py

echo "Copiando binário para locais de execução..."
cp -f dist/CorteAC corteac_linux
cp -f dist/CorteAC teste_dola_linux 2>/dev/null || true
cp -f dist/CorteAC ../teste_dola_linux 2>/dev/null || true
chmod +x corteac_linux teste_dola_linux 2>/dev/null || true

echo "========================================================"
echo "  Compilacao concluida com sucesso!"
echo "  Executavel gerado em: dist/CorteAC"
echo "  Binario local atualizado: ./corteac_linux"
echo "========================================================"
