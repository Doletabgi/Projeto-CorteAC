"""
CorteAC (Python Edition para Windows 10 / 11)
Ponto de Entrada da Aplicação
"""

import sys
import os

# Garante que o diretório atual está no PYTHONPATH
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Configura caminhos Tcl/Tk para execução portátil no Windows 10/11
if sys.platform == "win32":
    parent_dir = os.path.dirname(current_dir)
    for base in [current_dir, parent_dir]:
        tcl_dir = os.path.join(base, "tcl", "tcl8.6")
        tk_dir = os.path.join(base, "tcl", "tk8.6")
        if os.path.isdir(tcl_dir):
            os.environ["TCL_LIBRARY"] = tcl_dir
        if os.path.isdir(tk_dir):
            os.environ["TK_LIBRARY"] = tk_dir

import multiprocessing
from ui.main_window import MainWindow

def main():
    # Mantém o atalho da Área de Trabalho/Menu com a versão atual (Linux).
    # Roda antes de qualquer saída (--version/--check-db) e só reescreve se já
    # existir atalho do CorteAC — não cria atalho sem o operador ter um.
    try:
        from config import APP_VERSION
        from ui.desktop_shortcut import sincronizar_atalho
        info = sincronizar_atalho(APP_VERSION)
        if info.get("acao") == "atualizado":
            print(f"Atalho da Área de Trabalho atualizado para CorteAC-{APP_VERSION}")
    except Exception as exc:  # noqa: BLE001
        print(f"[AVISO] Não foi possível atualizar o atalho: {exc}")

    if "--criar-atalho" in sys.argv or "--atalho" in sys.argv:
        from config import APP_VERSION
        from ui.desktop_shortcut import sincronizar_atalho
        info = sincronizar_atalho(APP_VERSION, criar_se_ausente=True)
        if info.get("criados"):
            print(f"Atalho criado/atualizado: CorteAC-{APP_VERSION}")
            for caminho in info["criados"]:
                print(f"  {caminho}")
            for removido in info.get("removidos", []):
                print(f"  removido: {removido}")
            sys.exit(0)
        print(f"Nao foi possivel criar o atalho: {info.get('erro') or 'ambiente sem suporte'}")
        sys.exit(1)

    if "--version" in sys.argv or "-v" in sys.argv:
        from config import APP_NAME, APP_VERSION
        print(f"{APP_NAME} {APP_VERSION}")
        sys.exit(0)

    if "--check-db" in sys.argv:
        import db
        print(f"Backend ativo: {db.get_active_backend()}")
        try:
            with db.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT 1")
                print(f"Conexão com banco bem-sucedida! Backend: {conn.backend}")
            sys.exit(0)
        except Exception as e:
            print(f"Erro ao conectar com banco: {e}", file=sys.stderr)
            sys.exit(1)

    if "--clean-db" in sys.argv or "--reset-layouts" in sys.argv:
        from database import DatabaseManager
        db_mgr = DatabaseManager()
        stats = db_mgr.clean_test_layouts()
        print("Banco de dados higienizado com sucesso:")
        print(f"  Layouts removidos: {stats.get('deleted_layouts', 0)}")
        print(f"  Peças removidas: {stats.get('deleted_pieces', 0)}")
        print(f"  Sessões de teste eliminadas: {stats.get('deleted_sessions', 0)}")
        print(f"  Sessões resetadas para Stand by: {stats.get('reset_sessions', 0)}")
        sys.exit(0)

    print("=" * 60)
    print("  CorteAC (Edição Python para Windows 10 / 11)")
    print("  Recriação Moderna do Sistema Jm2k & ATOM Nesting")
    print("=" * 60)
    app = MainWindow()
    app.mainloop()

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()

