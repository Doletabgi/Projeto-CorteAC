#!/usr/bin/env bash
set -e
echo "========================================================"
echo "  Compilando teste dola para Linux (Standalone)"
echo "========================================================"
cd "$(dirname "$0")"

pyinstaller --clean --onefile --add-data "assets:assets" --add-data "samples:samples" --add-data "jobmanager.db:." --add-data "db.example.ini:." --hidden-import pymysql --hidden-import cryptography --name "teste_dola" main.py

echo "Copiando binário para locais de execução..."
cp -f dist/teste_dola teste_dola_linux
cp -f dist/teste_dola ../teste_dola_linux
chmod +x teste_dola_linux ../teste_dola_linux

echo "========================================================"
echo "  Compilacao concluida com sucesso!"
echo "  Executavel gerado em: dist/teste_dola"
echo "  Atualizados: ./teste_dola_linux e ../teste_dola_linux"
echo "========================================================"
