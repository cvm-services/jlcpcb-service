"""BOM/CPL transform tests — pure functions, no network."""
import pytest

from jlcpcb_client.bom import build_bom, build_cpl

# Shape KiCad's pos_*.csv actually has.
CPL_ROWS = [
    {"Ref": "C1", "Val": "100nF", "Package": "C_0603", "PosX": "1.00", "PosY": "2.00", "Rot": "90", "Side": "top"},
    {"Ref": "C2", "Val": "100nF", "Package": "C_0603", "PosX": "3.00", "PosY": "4.00", "Rot": "90", "Side": "top"},
    {"Ref": "U1", "Val": "ESP32-C3-WROOM-02", "Package": "ESP32-C3-WROOM-02", "PosX": "5", "PosY": "6", "Rot": "0", "Side": "top"},
    {"Ref": "R_SER", "Val": "0R", "Package": "R_0603", "PosX": "7", "PosY": "8", "Rot": "0", "Side": "top"},
    {"Ref": "C_SH1", "Val": "DNP", "Package": "C_0603", "PosX": "9", "PosY": "10", "Rot": "0", "Side": "top"},
]


def test_cpl_maps_to_jlc_columns():
    rows = build_cpl(CPL_ROWS)
    assert rows[0] == {
        "Designator": "C1", "Mid X": "1.00", "Mid Y": "2.00",
        "Layer": "top", "Rotation": "90",
    }


def test_bom_groups_by_value_and_footprint():
    rows = build_bom(CPL_ROWS)
    by_val = {r["Comment"]: r for r in rows}
    # C1 + C2 share value+footprint -> one line with both designators
    assert by_val["100nF"]["Designator"] == "C1,C2"


def test_bom_excludes_dnp_and_zero_ohm_jumpers():
    rows = build_bom(CPL_ROWS)
    comments = {r["Comment"] for r in rows}
    assert "DNP" not in comments
    assert "0R" not in comments


def test_bom_lines_carry_an_empty_lcsc_column():
    # The column must exist and be empty — never invented. A guessed part
    # number is a scrap board, so unresolved lines must be visible as such.
    rows = build_bom(CPL_ROWS)
    assert all("LCSC Part #" in r for r in rows)
    assert all(r["LCSC Part #"] == "" for r in rows)


def test_bom_accepts_a_part_map_and_reports_unmatched():
    rows = build_bom(CPL_ROWS, part_map={"100nF|C_0603": "C1590"})
    by_val = {r["Comment"]: r for r in rows}
    assert by_val["100nF"]["LCSC Part #"] == "C1590"
    assert by_val["ESP32-C3-WROOM-02"]["LCSC Part #"] == ""
