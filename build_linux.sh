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

# Icone do aplicativo (usado pela janela E pelo atalho da area de trabalho)
cp -f assets/app_icon.png dist_linux/CorteAC/corteac.png

# Instalador do atalho (gera o .desktop com caminho absoluto e o icone correto)
cat > dist_linux/CorteAC/instalar_atalho.sh <<'ATALHO'
#!/usr/bin/env bash
# Cria/atualiza o atalho do CorteAC no menu de aplicativos e na area de trabalho,
# sempre apontando para a pasta onde este pacote foi extraido (icone incluido).
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
APPS="$HOME/.local/share/applications"
mkdir -p "$APPS"
DESK="$APPS/corteac.desktop"
cat > "$DESK" <<ENTRY
[Desktop Entry]
Type=Application
Name=CorteAC
GenericName=Encaixe e Corte
Comment=JobManager 2000 Reborn - encaixe de couro e corte CAM
Exec=$DIR/corteac_linux
Path=$DIR
Icon=$DIR/corteac.png
Terminal=false
Categories=Graphics;Engineering;
StartupWMClass=corteac_linux
ENTRY
chmod +x "$DESK"
DESKTOP_DIR="$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Desktop")"
if [ -d "$DESKTOP_DIR" ]; then
  cp "$DESK" "$DESKTOP_DIR/corteac.desktop"
  chmod +x "$DESKTOP_DIR/corteac.desktop"
  gio set "$DESKTOP_DIR/corteac.desktop" metadata::trusted true 2>/dev/null || true
fi
update-desktop-database "$APPS" 2>/dev/null || true
echo "Atalho instalado: $DESK"
echo "Icone: $DIR/corteac.png"
echo "Se o icone nao atualizar, encerre a sessao do usuario ou rode: gtk-update-icon-cache"
ATALHO
chmod +x dist_linux/CorteAC/instalar_atalho.sh

chmod +x dist_linux/CorteAC/corteac_linux dist_linux/CorteAC/run.sh 2>/dev/null || true
tar -czf dist/CorteAC-Linux-x64.tar.gz -C dist_linux CorteAC
rm -rf dist_linux

echo "========================================================"
echo "  Compilacao concluida com sucesso!"
echo "  Executavel gerado em: dist/CorteAC e dist/teste_dola"
echo "  Binarios locais atualizados: ./corteac_linux e ./teste_dola_linux"
echo "  Pacote distribuicao Linux gerado: dist/CorteAC-Linux-x64.tar.gz"
echo "========================================================"
