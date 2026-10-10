"""Self-contained synthetic IES / LDT files for testing UI, not real manufacturer data."""
from __future__ import annotations

import numpy as np


def _pattern(kind: str, gamma: np.ndarray, c: np.ndarray) -> np.ndarray:
    g = gamma[None, :]
    az = np.deg2rad(c[:, None])
    if kind == "narrow":
        return 920 * np.exp(-0.5 * (g / 22) ** 2)
    if kind == "narrow_similar":
        return 880 * np.exp(-0.5 * (g / 24) ** 2)
    if kind == "wide":
        return 620 * np.exp(-0.5 * (g / 47) ** 2)
    if kind == "batwing":
        return 320 + 420 * np.exp(-0.5 * ((g - 48) / 17) ** 2)
    if kind == "oval":
        return 820 * np.exp(-0.5 * (g / (27 + 11 * np.cos(2 * az))) ** 2)
    if kind == "asymmetric":
        return 780 * np.exp(-0.5 * ((g - 15 * (np.cos(az)+1)) / 25) ** 2)
    raise KeyError(kind)


def make_ies(label: str, kind: str, watts: float = 30) -> bytes:
    gamma = np.arange(0, 181, 10)
    cs = np.arange(0, 361, 10)
    values = _pattern(kind, gamma, cs)
    if len(values) == 1:
        values = np.broadcast_to(values, (len(cs), len(gamma))).copy()
    values[-1] = values[0]
    rows = ["IESNA:LM-63-2002", "[MANUFAC] PRÓBKI SYNTETYCZNE / NIE PRODUCENT",
            f"[LUMCAT] {label}", "TILT=NONE", "1 -1 1 19 37 1 2 0.5 0.5 0.1",
            f"1 1 {watts:.2f}", " ".join(map(str, gamma)), " ".join(map(str, cs))]
    rows.extend(" ".join(f"{value:.5f}" for value in plane) for plane in values)
    return ("\n".join(rows) + "\n").encode("utf-8")


def make_ldt(label: str, kind: str, luminous_flux_lm: int = 3500) -> bytes:
    # Rotational symmetry, Mc=36, Ng=19, C=0..350, gamma=0..180
    cs = np.arange(0, 360, 10)
    gamma = np.arange(0, 181, 10)
    raw = _pattern(kind, gamma, np.array([0.0])).reshape(-1) / (luminous_flux_lm/1000)
    lines = ["PRÓBKI SYNTETYCZNE", "1", "1", "36", "10", "19", "10",
             "DEMO", label, f"{label}-01", "demo.ldt", "2026 demo", "300", "300", "40",
             "280", "280", "0", "0", "0", "0", "100", "100", "1", "0", "1",
             "-1", "LED example", str(luminous_flux_lm), "4000", "80", "30"]
    lines.extend("0" for _ in range(10))
    lines.extend(str(int(x)) for x in cs)
    lines.extend(str(int(x)) for x in gamma)
    lines.extend(f"{value:.5f}" for value in raw)
    return ("\n".join(lines) + "\n").encode("utf-8")


def samples() -> dict[str, bytes]:
    return {
        "DEMO_01_Spot_IES.ies": make_ies("Spot 22°", "narrow"),
        "DEMO_02_SpotPodobny_IES.ies": make_ies("Spot 24°", "narrow_similar"),
        "DEMO_03_Downlight_IES.ies": make_ies("Downlight 47°", "wide"),
        "DEMO_04_Batwing_IES.ies": make_ies("Panel batwing", "batwing"),
        "DEMO_05_Owal_IES.ies": make_ies("Rozsył owalny", "oval"),
        "DEMO_06_Asymetria_IES.ies": make_ies("Rozsył asymetryczny", "asymmetric"),
        "DEMO_07_LDT_Spot.ldt": make_ldt("Spot wersja LDT", "narrow"),
        "DEMO_08_LDT_Wide.ldt": make_ldt("Downlight wersja LDT", "wide"),
    }
