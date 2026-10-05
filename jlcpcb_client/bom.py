"""BOM and CPL transforms for JLCPCB assembly quoting.

Pure functions over rows — no network, no browser, no file I/O. KiCad's
placement export (`pos_*.csv`) uses Ref/Val/Package/PosX/PosY/Rot/Side; JLCPCB
wants different column names and a grouped BOM.

Two rules are encoded here because getting them wrong ruins a board:

1. `DNP` designators and `0R` jumpers are excluded — a jumper is a wire, not a
   component, and JLC will not place it.
2. The LCSC column is left **empty** when a part is not resolved. It is never
   guessed. A caller can see at a glance which lines still need a part number.
"""
from typing import Dict, Iterable, List, Optional

DEFAULT_CPL_HEADER = ["Designator", "Mid X", "Mid Y", "Layer", "Rotation"]
BOM_HEADER = ["Comment", "Designator", "Footprint", "Layer", "LCSC Part #"]

# Values that must not reach an assembly BOM.
EXCLUDED_VALUES = {"DNP", "0R", "0", "0R0"}


def build_cpl(rows: Iterable[dict]) -> List[dict]:
    """Map KiCad placement rows to JLCPCB CPL columns.

    JLCPCB expects the midpoint in the board's coordinate system on whichever
    side the part sits; KiCad already reports PosX/PosY in mm from the origin.
    """
    out = []
    for r in rows:
        out.append({
            "Designator": str(r.get("Ref", "")).strip(),
            "Mid X": str(r.get("PosX", "")).strip(),
            "Mid Y": str(r.get("PosY", "")).strip(),
            "Layer": _layer(r.get("Side", "")),
            "Rotation": str(r.get("Rot", "0")).strip() or "0",
        })
    return out


def _layer(side: str) -> str:
    s = (side or "").strip().lower()
    if s in ("bottom", "back", "b"):
        return "bottom"
    return "top"


def build_bom(rows: Iterable[dict], part_map: Optional[Dict[str, str]] = None) -> List[dict]:
    """Group placements into a JLCPCB BOM, one line per (value, footprint).

    `part_map` keys are ``"<value>|<footprint>"`` and values are LCSC part
    numbers. Anything absent from the map produces an empty LCSC column rather
    than a guess.
    """
    part_map = part_map or {}
    groups: Dict[tuple, List[str]] = {}
    order: List[tuple] = []
    for r in rows:
        val = str(r.get("Val", "")).strip()
        if val.upper() in EXCLUDED_VALUES:
            continue
        fp = str(r.get("Package", "")).strip()
        key = (val, fp)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(str(r.get("Ref", "")).strip())

    out = []
    for val, fp in order:
        refs = groups[(val, fp)]
        out.append({
            "Comment": val,
            "Designator": ",".join(refs),
            "Footprint": fp,
            "Layer": "top",
            "LCSC Part #": part_map.get(f"{val}|{fp}", ""),
        })
    return out


def unmatched_lines(bom_rows: Iterable[dict]) -> List[dict]:
    """BOM lines still needing a part number — the honest 'not quotable' set."""
    return [r for r in bom_rows if not str(r.get("LCSC Part #", "")).strip()]
