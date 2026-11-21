import pytest

tk = pytest.importorskip("tkinter")


def _display_ok():
    try:
        root = tk.Tk()
        root.destroy()
        return True
    except tk.TclError:
        return False


pytestmark = pytest.mark.skipif(not _display_ok(), reason="pas d'écran (Tk) disponible")


def test_mix_colors():
    from jarvis.ui.orb import mix

    assert mix("#ffffff", 1.0) == "#ffffff"
    assert mix("#ffffff", 0.0) == "#080e1c"


def test_orb_runs_all_states_and_closes():
    from jarvis.ui.orb import COLORS, Orb

    events = []
    orb = Orb(size=100, on_quit=lambda: events.append("quit"), on_stop=lambda: events.append("stop"))
    for state in COLORS:
        orb.set_state(state)
        orb._tick()
    orb.set_state("inconnu")           # ignoré
    assert orb.state == "error"
    orb._stop()
    orb._quit()
    assert events == ["stop", "quit"]
    orb.root.after(50, orb.close)
    orb.run()                          # rend la main quand la fenêtre se ferme
