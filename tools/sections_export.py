"""Writes 2D cross sections of the model to sections.json.

Run with: freecadcmd sections_export.py
The macro is executed in this namespace, so its parameters and shapes are used directly.
"""
# ruff: noqa: F821  (names come from the macro that is exec'd below)

import json
import os

os.environ["LHB_NO_EXPORT"] = "1"
HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in dir() else os.getcwd()
MACRO = os.path.join(HERE, "..", "freecad", "LoRaHarvesterBox_Enclosure.FCMacro")
exec(open(MACRO, encoding="utf-8").read(), globals())

SECTIONS = {}


def section(name, shapes, plane, value, axes):
    """Cuts every shape with a thin slab and stores the resulting edges as polylines."""
    segments = []
    for shape, tag in shapes:
        if plane == "y":
            slab = box(-200, value - 0.01, -200, 500, 0.02, 500)
        elif plane == "x":
            slab = box(value - 0.01, -200, -200, 0.02, 500, 500)
        else:
            slab = box(-200, -200, value - 0.01, 500, 500, 0.02)
        for edge in shape.common(slab).Edges:
            span = edge.LastParameter - edge.FirstParameter
            points = [edge.valueAt(edge.FirstParameter + span * i / 12) for i in range(13)]
            segments.append([tag, [[getattr(p, axes[0]), getattr(p, axes[1])] for p in points]])
    SECTIONS[name] = segments


section("vent_xz", [(base, "base"), (lid, "lid"), (vent_nut_dummy, "nut"), (vent_plug, "plug")],
        "y", VENT_Y, ("x", "z"))
section("tie_yz", [(base, "base")], "x", TIE_X[0], ("y", "z"))
section("corner_xz", [(base, "base"), (lid, "lid")], "y", -BOSS_OFF, ("x", "z"))
section("rim_xz", [(base, "base"), (lid, "lid")], "y", 20.0, ("x", "z"))
section("pcb_xy", [(base, "base"), (pcb, "pcb")], "z", PCB_Z + 0.8, ("x", "y"))

with open(os.path.join(HERE, "sections.json"), "w") as handle:
    json.dump(SECTIONS, handle)
print("ok", {k: len(v) for k, v in SECTIONS.items()})
