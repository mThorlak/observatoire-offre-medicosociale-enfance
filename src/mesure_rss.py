"""
mesure_rss.py — pic de mémoire résidente (RSS) du processus courant, portable.

`resource.getrusage` (bibliothèque standard) n'existe que sur POSIX. Ce
projet tourne aussi bien en CI (`ubuntu-latest`) qu'en développement local,
parfois sous Windows, où `resource` n'existe pas. Sous Windows, on interroge
l'équivalent via l'API Win32 (`GetProcessMemoryInfo`) par `ctypes` — aucune
dépendance tierce, même principe que le reste du projet.

Aucune dépendance tierce. Compatible Python 3.9+.
"""

from __future__ import annotations

import sys


def rss_max_mio() -> float:
    """Pic de RSS du processus courant, en mébioctets (Mio)."""
    if sys.platform == "win32":
        return _rss_max_mio_windows()
    import resource

    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def _rss_max_mio_windows() -> float:
    import ctypes
    from ctypes import wintypes

    class ProcessMemoryCounters(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)

    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.GetCurrentProcess.argtypes = []
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    psapi.GetProcessMemoryInfo.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(ProcessMemoryCounters),
        wintypes.DWORD,
    ]

    compteurs = ProcessMemoryCounters()
    compteurs.cb = ctypes.sizeof(ProcessMemoryCounters)
    processus_courant = kernel32.GetCurrentProcess()
    reussite = psapi.GetProcessMemoryInfo(
        processus_courant, ctypes.byref(compteurs), compteurs.cb
    )
    if not reussite:
        raise OSError(ctypes.get_last_error(), "GetProcessMemoryInfo a échoué")
    return compteurs.PeakWorkingSetSize / (1024 * 1024)
