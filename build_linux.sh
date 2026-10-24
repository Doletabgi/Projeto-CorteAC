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

echo "Empacotando pacote portatil dist/CorteAC-Linux-x64.tar.gz..."
mkdir -p dist_linux/CorteAC
cp -f corteac_linux dist_linux/CorteAC/
cp -f README_LINUX.txt dist_linux/CorteAC/ 2>/dev/null || true
cp -f run.sh dist_linux/CorteAC/ 2>/dev/null || true
cp -f db.example.ini dist_linux/CorteAC/ 2>/dev/null || true
chmod +x dist_linux/CorteAC/corteac_linux dist_linux/CorteAC/run.sh 2>/dev/null || true
tar -czf dist/CorteAC-Linux-x64.tar.gz -C dist_linux CorteAC
rm -rf dist_linux

echo "========================================================"
echo "  Compilacao concluida com sucesso!"
echo "  Executavel gerado em: dist/CorteAC e dist/teste_dola"
echo "  Binarios locais atualizados: ./corteac_linux e ./teste_dola_linux"
echo "  Pacote distribuicao Linux gerado: dist/CorteAC-Linux-x64.tar.gz"
echo "========================================================"
