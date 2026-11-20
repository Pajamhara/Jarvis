import sys
import traceback

from jarvis.app import main

if __name__ == "__main__":
    code = 1
    try:
        code = main()
    except Exception:
        traceback.print_exc()
    # Dans le .exe, la console se fermerait instantanément : on laisse le temps de lire l'erreur.
    if getattr(sys, "frozen", False) and code != 0:
        input("\nAppuyez sur Entrée pour fermer...")
    raise SystemExit(code)
