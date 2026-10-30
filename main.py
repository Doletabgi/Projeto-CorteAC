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

    print("=" * 60)
    print("  CorteAC (Edição Python para Windows 10 / 11)")
    print("  Recriação Moderna do Sistema Jm2k & ATOM Nesting")
    print("=" * 60)
    app = MainWindow()
    app.mainloop()

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()

