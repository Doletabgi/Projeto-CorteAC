#!/usr/bin/env bash
set -e
echo "========================================================"
echo "  Compilando teste dola para Linux (Standalone)"
echo "========================================================"
cd "$(dirname "$0")"

pyinstaller --clean --onefile --add-data "assets:assets" --add-data "samples:samples" --add-data "jobmanager.db:." --name "teste_dola" main.py

echo "========================================================"
echo "  Compilacao concluida com sucesso!"
echo "  Executavel gerado em: dist/teste_dola"
echo "========================================================"
