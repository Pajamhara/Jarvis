"""Petite orbe animée façon Jarvis (tkinter, aucune dépendance en plus).

  - bleue : en veille            - cyan : écoute
  - orange : réfléchit           - verte : parle
Clic = couper la parole · glisser = déplacer · clic droit = menu (Quitter).
"""
from __future__ import annotations

import math
import time
import tkinter as tk

COLORS = {
    "idle": "#2b8cff", "listening": "#00e5ff", "thinking": "#ffb020",
    "speaking": "#3dff9a", "error": "#ff4d4d",
}
ANIM = {  # (vitesse, amplitude) de la pulsation
    "idle": (1.2, 0.04), "listening": (3.0, 0.10), "thinking": (6.0, 0.07),
    "speaking": (5.0, 0.16), "error": (8.0, 0.10),
}
KEY = "#010203"          # couleur rendue transparente (Windows)
DARK = (8, 14, 28)


def mix(color: str, alpha: float) -> str:
    """Mélange `color` avec le fond sombre : alpha=1 -> couleur pure."""
    rgb = [int(color[i:i + 2], 16) for i in (1, 3, 5)]
    out = [int(d + (c - d) * alpha) for c, d in zip(rgb, DARK)]
    return "#%02x%02x%02x" % tuple(out)


class Orb:
    def __init__(self, title: str = "Jarvis", size: int = 110, on_quit=None, on_stop=None) -> None:
        self.size = size
        self.on_quit = on_quit
        self.on_stop = on_stop
        self.state = "idle"
        self._closing = False
        self._t0 = time.monotonic()
        self._drag = (0, 0)
        self._moved = False

        self.root = tk.Tk()
        self.root.title(title)
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=KEY)
        try:
            self.root.attributes("-transparentcolor", KEY)
        except tk.TclError:  # non supporté hors Windows
            pass
        self.canvas = tk.Canvas(self.root, width=size, height=size, bg=KEY, highlightthickness=0)
        self.canvas.pack()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"{size}x{size}+{sw - size - 40}+{sh - size - 100}")

        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="Arrêter de parler", command=self._stop)
        self.menu.add_separator()
        self.menu.add_command(label="Quitter Jarvis", command=self._quit)
        self.canvas.bind("<ButtonPress-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._motion)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.canvas.bind("<Button-3>", lambda e: self.menu.tk_popup(e.x_root, e.y_root))
        self.root.after(33, self._tick)

    # ---- appelable depuis un autre thread (simples affectations) ----
    def set_state(self, state: str) -> None:
        if state in COLORS:
            self.state = state

    def close(self) -> None:
        self._closing = True

    # ---- interactions ----
    def _stop(self) -> None:
        if self.on_stop:
            self.on_stop()

    def _quit(self) -> None:
        if self.on_quit:
            self.on_quit()
        self._closing = True

    def _press(self, e) -> None:
        self._drag = (e.x_root - self.root.winfo_x(), e.y_root - self.root.winfo_y())
        self._moved = False

    def _motion(self, e) -> None:
        x, y = e.x_root - self._drag[0], e.y_root - self._drag[1]
        if abs(x - self.root.winfo_x()) + abs(y - self.root.winfo_y()) > 3:
            self._moved = True
        self.root.geometry(f"+{x}+{y}")

    def _release(self, e) -> None:
        if not self._moved:
            self._stop()

    # ---- dessin ----
    def _tick(self) -> None:
        if self._closing:
            self.root.destroy()
            return
        c = self.canvas
        c.delete("all")
        t = time.monotonic() - self._t0
        color = COLORS[self.state]
        speed, amp = ANIM[self.state]
        mid = self.size / 2
        base = self.size * 0.26 * (1 + math.sin(t * speed) * amp)
        for scale, alpha in ((1.55, 0.12), (1.35, 0.22), (1.18, 0.40)):
            r = base * scale
            c.create_oval(mid - r, mid - r, mid + r, mid + r, fill=mix(color, alpha), outline="")
        c.create_oval(mid - base, mid - base, mid + base, mid + base,
                      fill=mix(color, 0.85), outline=color, width=2)
        r = base * 0.45
        c.create_oval(mid - r, mid - r, mid + r, mid + r, fill=mix(color, 0.55), outline="")
        if self.state == "thinking":
            r = base * 1.3
            c.create_arc(mid - r, mid - r, mid + r, mid + r, start=(t * 240) % 360,
                         extent=90, style="arc", outline=color, width=3)
        self.root.after(33, self._tick)

    def run(self) -> None:
        self.root.mainloop()
