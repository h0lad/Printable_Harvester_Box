"""Compares the committed STEP files with a fresh macro run and prints the key dimensions.

Run with: freecadcmd integrity_check.py
"""
# ruff: noqa: F821  (names come from the macro that is exec'd below)

import os

os.environ["LHB_NO_EXPORT"] = "1"
HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in dir() else os.getcwd()
ROOT = os.path.join(HERE, "..")
exec(open(os.path.join(ROOT, "freecad", "LoRaHarvesterBox_Enclosure.FCMacro"), encoding="utf-8").read(), globals())

import Part  # noqa: E402  (FreeCAD modules are only available once the macro has run)

print("part            committed cm3   fresh cm3   delta")
for name, shape in (("base", base), ("lid", lid), ("battery_plate", plate)):
    path = os.path.join(ROOT, "steps_stl", f"LoRaHarvesterBox_{name}.step")
    if not os.path.exists(path):
        print(f"{name:15s} MISSING")
        continue
    committed = Part.Shape()
    committed.read(path)
    delta = abs(committed.Volume - shape.Volume) / 1000
    print(f"{name:15s} {committed.Volume / 1000:10.2f} {shape.Volume / 1000:12.2f} {delta:9.3f}")

print()
print("body            %.1f x %.1f x %.1f mm" % (L_IN + 2 * WALL, W_IN + 2 * WALL, FLOOR + H_IN + LID_T))
print("over columns    %.1f x %.1f mm" % (base.BoundBox.XLength, base.BoundBox.YLength))
print("cavity          %.1f x %.1f x %.1f mm" % (L_IN, W_IN, H_IN))
print("groove lips     %.2f mm each" % ((WALL - GROOVE_W) / 2))
print("vent            hole %.1f dia, thread %.1f long, nut %.1f x %.1f"
      % (VENT_D, VENT_THREAD, VENT_NUT_D, VENT_NUT_H))
print("vent clamp      %.1f mm of wall, %.1f mm of thread inside, %.1f mm spare"
      % (WALL - VENT_FACE_H, VENT_THREAD - (WALL - VENT_FACE_H), VENT_THREAD - (WALL - VENT_FACE_H) - VENT_NUT_H))
print("grip space      %.1f dia x %.1f deep inside" % (VENT_FREE_D, VENT_FREE_L))
for name, shape in (("PCB", pcb), ("plate", plate), ("lid", lid)):
    print("grip space to %-6s %.1f mm" % (name, vent_nut.distToShape(shape)[0]))
print("plug head       %.1f dia x %.1f, %.1f mm above ground when flat"
      % (VENT_CAP_D, VENT_CAP_H, FLOOR + VENT_Z - VENT_CAP_D / 2))
print("tunnels         Y %.1f x %.1f, X %.1f x %.1f, skin %.1f, roof %.1f/%.1f"
      % (TIE_W, TIE_H, TIE_W2, TIE_H2, TIE_SKIN, FLOOR - TIE_SKIN - TIE_H, FLOOR - TIE_SKIN - TIE_H2))
print("captive neck    %.1f dia x %.1f in a %.1f mm lid" % (SCREW_CAPTIVE_D, SCREW_CAPTIVE_L, LID_T))
print("panel           %.0f x %.0f on 9 spacers, gap %.1f mm" % (PANEL, PANEL, STANDOFF_H))
print("collisions:", check() or "none")
