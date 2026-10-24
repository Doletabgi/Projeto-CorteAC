#!/usr/bin/env python3
"""
tools/re_dump/extract_help_docs.py

Extração automatizada de documentação da Ajuda HTML oficial do ATOM Layout Editor:
Local de origem: Help/LayoutEditor/*.htm e Help/JM2K/English/*.htm

Extrai:
- Descrição de menus, botões da toolbar e painéis
- Gestos de mouse documentados (seleção, rotação, bump, zoom, catálogo)
- Teclas de atalho e aceleradores declarados na documentação
- Comportamento de rotação (simples, grupo, centro customizado)
- Funções avançadas (Bump, Edit position, Cutting order, Check overlay, Mirror, Substitute)
"""

import sys
import re
import json
from pathlib import Path
from html.parser import HTMLParser

HELP_DIR = Path("/home/dola/Documentos/clone do job/sistemas/antigo/arquivos pos instalacao/Common 100% funcionado/Help/LayoutEditor")
OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "docs" / "ref" / "layout_re"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

class HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text_parts = []
        self.in_script = False

    def handle_starttag(self, tag, attrs):
        if tag in ["script", "style"]:
            self.in_script = True
        elif tag in ["p", "br", "div", "h1", "h2", "h3", "h4", "li", "tr"]:
            self.text_parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ["script", "style"]:
            self.in_script = False
        elif tag in ["p", "div", "h1", "h2", "h3", "h4", "li", "tr"]:
            self.text_parts.append("\n")

    def handle_data(self, data):
        if not self.in_script:
            self.text_parts.append(data)

    def get_text(self):
        raw = "".join(self.text_parts)
        lines = [line.strip() for line in raw.splitlines()]
        clean_lines = []
        for line in lines:
            if line:
                clean_lines.append(line)
        return "\n".join(clean_lines)

def extract_file(path: Path):
    with open(path, "r", encoding="windows-1252", errors="replace") as f:
        html = f.read()
    parser = HTMLTextExtractor()
    parser.feed(html)
    return parser.get_text()

def main():
    if not HELP_DIR.exists():
        print(f"ERRO: {HELP_DIR} não existe.", file=sys.stderr)
        sys.exit(1)

    topics = {}
    summary_lines = []
    summary_lines.append("# RESUMO DA AJUDA OFICIAL DO ATOM LAYOUT EDITOR (FONTE 1: Help/LayoutEditor/)")
    summary_lines.append("=" * 80)
    summary_lines.append("Versão documentada no manual: Atom Layout editor v2.4.11 / Win32 (4 Set 2000)")
    summary_lines.append("Binário analisado: Layout.exe v3.2.7.0 (28 Mar 2013)")
    summary_lines.append("=" * 80 + "\n")

    files = [
        "bdyInterface.htm",
        "bdySelect_a_shape.htm",
        "bdyWorkingWithShapesAdv.htm",
        "bdyCatalog.htm",
        "bdytips.htm",
        "bdyGetStarted.htm",
        "bdyIntroduction.htm",
        "popVersionDifferences.htm"
    ]

    for fname in files:
        fpath = HELP_DIR / fname
        if fpath.exists():
            text = extract_file(fpath)
            topics[fname] = text
            summary_lines.append(f"--- TÓPICO: {fname} ---")
            summary_lines.append(text)
            summary_lines.append("\n" + "-" * 80 + "\n")

    # Salva resumo em texto
    with open(OUTPUT_DIR / "help_interface_summary.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(summary_lines))
    print(f"-> {OUTPUT_DIR / 'help_interface_summary.txt'} gravado.")

    # Salva em JSON estruturado
    with open(OUTPUT_DIR / "help_topics.json", "w", encoding="utf-8") as f:
        json.dump(topics, f, indent=2, ensure_ascii=False)
    print(f"-> {OUTPUT_DIR / 'help_topics.json'} gravado.")

if __name__ == "__main__":
    main()
