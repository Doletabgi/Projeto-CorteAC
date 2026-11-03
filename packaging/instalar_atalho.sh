#!/usr/bin/env bash
# Instala/atualiza o atalho do CorteAC na Área de Trabalho e no menu de aplicativos.
#
# O nome do atalho carrega a VERSÃO (ex.: "CorteAC-1.6.10") e a versão anterior é
# removida, para o operador saber exatamente qual build está na máquina.
#
# O marcador de versão é substituído no empacotamento (build_linux.sh e CI).
set -e

VERSAO_PADRAO="@VERSAO@"
DIR="$(cd "$(dirname "$0")" && pwd)"

# 1. Descobre a versão: primeiro perguntando ao próprio binário, depois o valor gravado no pacote
VERSAO=""
if [ -x "$DIR/corteac_linux" ]; then
    VERSAO="$("$DIR/corteac_linux" --version 2>/dev/null | awk '{print $NF}' | head -n1 || true)"
fi
case "$VERSAO" in
    [0-9]*) : ;;
    *) VERSAO="$VERSAO_PADRAO" ;;
esac

NOME="CorteAC-$VERSAO"
ARQ="corteac-$VERSAO.desktop"
APPS="$HOME/.local/share/applications"
mkdir -p "$APPS"

# 2. Remove atalhos de versões anteriores (mantém sempre um único ícone na mesa)
rm -f "$APPS"/corteac.desktop "$APPS"/corteac-*.desktop 2>/dev/null || true
DESKTOP_DIR="$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Desktop")"
if [ -d "$DESKTOP_DIR" ]; then
    rm -f "$DESKTOP_DIR"/corteac.desktop "$DESKTOP_DIR"/corteac-*.desktop 2>/dev/null || true
    rm -f "$DESKTOP_DIR"/CorteAC*.desktop 2>/dev/null || true
fi

# 3. Gera o .desktop (Exec= aspeado: o caminho pode conter espaços)
DESK="$APPS/$ARQ"
cat > "$DESK" <<ENTRY
[Desktop Entry]
Type=Application
Name=$NOME
GenericName=Encaixe e Corte
Comment=JobManager 2000 Reborn - encaixe de couro e corte CAM (v$VERSAO)
Exec="$DIR/corteac_linux"
Path=$DIR
Icon=$DIR/corteac.png
Terminal=false
Categories=Graphics;Engineering;
StartupWMClass=corteac_linux
X-CorteAC-Version=$VERSAO
ENTRY
chmod +x "$DESK"

# 4. Copia para a Área de Trabalho com o nome versionado
if [ -d "$DESKTOP_DIR" ]; then
    cp "$DESK" "$DESKTOP_DIR/$ARQ"
    chmod +x "$DESKTOP_DIR/$ARQ"
    gio set "$DESKTOP_DIR/$ARQ" metadata::trusted true 2>/dev/null || true
fi

update-desktop-database "$APPS" 2>/dev/null || true

echo "Atalho instalado: $NOME"
echo "  arquivo : $DESK"
[ -d "$DESKTOP_DIR" ] && echo "  desktop : $DESKTOP_DIR/$ARQ"
echo "  icone   : $DIR/corteac.png"
echo "Se o icone ou o nome nao atualizarem na hora, saia e entre na sessao (cache do ambiente)."
