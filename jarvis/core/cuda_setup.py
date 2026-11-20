"""Rend visibles les DLL CUDA installées par pip (nvidia-cublas-cu12...) sous Windows.

Sans cela, faster-whisper ne trouve pas cuBLAS et retombe sur le processeur.
Fonctionne aussi dans le .exe PyInstaller (DLL dans <dossier>/_internal/nvidia/*/bin).
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

log = logging.getLogger(__name__)
_done = False


def setup_cuda_dlls() -> None:
    global _done
    if _done or sys.platform != "win32":
        return
    _done = True

    roots: list[Path] = []
    if getattr(sys, "frozen", False):
        roots.append(Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "nvidia")
    try:
        import nvidia  # paquet "namespace" créé par nvidia-cublas-cu12, nvidia-cudnn-cu12...

        roots += [Path(p) for p in nvidia.__path__]
    except ImportError:
        pass

    for root in roots:
        for bin_dir in root.glob("*/bin"):
            try:
                os.add_dll_directory(str(bin_dir))
            except OSError:
                continue
            os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ.get("PATH", "")
            log.debug("DLL CUDA ajoutées : %s", bin_dir)
