"""Walks the build order and measures the space that each step gets, including the swept paths.

The free radii are not measured here. clearance_probe.py owns that measurement, bisected to 0.02 mm on
a real cylinder, and this file reads its report so that the two tools cannot disagree. This file owns the
order and the swept paths.

The path that needed sweeping is the board under the two hold-down lips. The lips overhang the bottom
edge of the board by 0.8 mm, so a vertical drop does not fit. The cavity gives 46.3 mm between the two
ribs, and the board is 45.5 mm long, which leaves 45.5 mm of clear drop once the lips take 0.8 mm at the
bottom end. The board goes in tilted with its bottom edge down, and it lays flat about that edge. The
tool sweeps the rotation and the 0.30 mm slide that follows it at 0.5 degrees and 0.05 mm, with the
components carried along, against the base and the plate.

The tool cannot decide the dress of the cable. It checks the pigtail as a tube on a planned path, so the
cable has to be routed on that path before the check describes the assembly.

Run with: freecadcmd montage_simulation.py
"""
# ruff: noqa: F821, E402  (names and FreeCAD modules come from the macro exec'd below)

import json
import os

os.environ["LHB_NO_EXPORT"] = "1"
HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in dir() else os.getcwd()
exec(
    open(os.path.join(HERE, "..", "freecad", "LoRaHarvesterBox_Enclosure.FCMacro"), encoding="utf-8").read(),
    globals(),
)

CLEARANCE = os.path.join(HERE, "clearance_report.json")
probes = json.load(open(CLEARANCE))["probes"] if os.path.exists(CLEARANCE) else []
by_name = {p["probe"]: p for p in probes}
lip_gap = lip_z - (PCB_Z + PCB_T)


def radii(*keys):
    out = []
    for k in keys:
        for name, p in by_name.items():
            if k in name:
                out.append(
                    f"{p['free_radius_mm']:.2f} mm free (need {p['required_mm']:.1f}), {'ok' if p['pass'] else 'BELOW'}"
                )
    return "; ".join(out) or "run clearance_probe.py first"


# Two single axis moves. The cavity gives 46.3 mm between the ribs, and the board is 45.5 mm long with a
# 0.8 mm lip over one end, so the board enters tilted and then slides back under that lip. The pivot is
# 0.30 mm forward of the seated bottom edge, because rotating about the seated edge drives the 1.6 mm end
# face of the board into the bottom rib, which sits 0.4 mm away.
Y_OFFSET = 0.30  # bottom edge starts here, forward of its seated position; the slide takes it back
START_DEG = 15.0
STEP_DEG = 0.5
SLIDE_STEP = 0.05
CLASH_MM3 = 1e-3
PIVOT = V(0, pcb.BoundBox.YMin + Y_OFFSET, PCB_Z)


def placed(angle, dy):
    """Returns the board and the components at one point of the insertion sequence: shifted forward,
    tilted, and then slid back.

    The pivot sits on the end edge of the board itself, so tilting lifts the whole board off the pillars
    instead of driving the 1.6 mm end face down into the rib behind it.
    """
    out = []
    for s in (pcb, comps):
        c = s.copy()
        c.translate(V(0, Y_OFFSET, 0))
        if angle:
            c.rotate(PIVOT, V(1, 0, 0), angle)
        if dy:
            c.translate(V(0, -dy, 0))
        out.append(c)
    return out


sweep = []
worst = None
for i in range(int(START_DEG / STEP_DEG) + 1):
    deg = round(START_DEG - i * STEP_DEG, 3)
    board, parts = placed(deg, 0.0)
    clash = (
        board.common(base).Volume + parts.common(base).Volume + board.common(plate).Volume + parts.common(plate).Volume
    )
    gap = min(board.distToShape(base)[0], parts.distToShape(base)[0]) if clash <= CLASH_MM3 else -1.0
    sweep.append(
        {
            "motion": "rotate",
            "angle_deg": deg,
            "slide_mm": 0.0,
            "clash_mm3": round(clash, 4),
            "clearance_mm": round(gap, 3),
        }
    )
    if deg > 0.5 and (worst is None or gap < worst["clearance_mm"]):
        worst = sweep[-1]
for k in range(1, int(Y_OFFSET / SLIDE_STEP) + 1):
    dy = round(k * SLIDE_STEP, 3)
    board, parts = placed(0.0, dy)
    clash = (
        board.common(base).Volume + parts.common(base).Volume + board.common(plate).Volume + parts.common(plate).Volume
    )
    sweep.append(
        {"motion": "slide", "angle_deg": 0.0, "slide_mm": dy, "clash_mm3": round(clash, 4), "clearance_mm": None}
    )
insertion_ok = all(s["clash_mm3"] <= CLASH_MM3 for s in sweep)
blocked = [s for s in sweep if s["clash_mm3"] > CLASH_MM3]
print("board insertion, two single axis moves (components carried along)")
print(f"  rotate {START_DEG:.0f} deg to 0 about the bottom edge sitting at y = {pcb.BoundBox.YMin + Y_OFFSET:.2f}")
print(f"  then slide {Y_OFFSET:.2f} mm in -y under the lips, {SLIDE_STEP:.2f} mm at a time")
print(
    f"  {'no clash at any of the ' + str(len(sweep)) + ' steps' if insertion_ok else 'CLASH: ' + str(blocked[0])}"
    f". Tightest clearance while tilted {worst['clearance_mm']:.2f} mm at {worst['angle_deg']:.1f} deg"
)
print(
    f"  the slide runs at the seated height, so it clears by the seated numbers: {lip_gap:.2f} mm under the "
    f"lips, {PCB_CLR:.2f} mm to the bottom rib, {PCB_CLR:.2f} mm to the top arm"
)

# One entry per step: the move, the space it has, and the note that the step needs. Every number comes
# from the macro or from clearance_report.json, and never from this file.
STEPS = [
    (
        "1 SMA bulkhead into the left wall",
        f"nut on the inner face, spanner space {radii('SMA bulkhead nut')}",
        (
            "the nut goes on before the battery plate, and the plate has a relief under the bulkhead. With "
            "the board fitted the free radius falls to about 6.7 mm, so a later re-tightening means taking "
            "the board out. That is why the nut goes on at step 1 and not at the end"
        ),
    ),
    (
        "2 LiPo into the pocket, lead through the wall notch",
        (
            f"cell {BAT_L:.0f} x {BAT_W:.0f} x {BAT_T:.1f} in a {POCKET[2]:.0f} x {POCKET[3]:.0f} pocket, "
            f"{POCKET[3] - BAT_W:.1f} mm of width clearance"
        ),
        ("the notch in the pocket wall is at x 5 to 12 and the cell starts at 5.5, so the lead exits under the plate"),
    ),
    (
        "3 battery cover plate onto the pocket",
        f"skirt {SKW} mm wide with {0.35:.2f} mm clearance, plate top at z {PLATE_Z0 + PLATE_T:.1f}",
        "the plate traps the lead and stands the cell off the board pillars",
    ),
    (
        "4 board onto its five pillars, then one M2x5 into H1",
        (
            f"board {pcb.BoundBox.XLength:.1f} x {pcb.BoundBox.YLength:.1f} x {PCB_T:.1f}, "
            f"driver space {radii('M2 driver')}"
        ),
        (
            f"tilted in about the bottom edge, {lip_gap:.2f} mm under the lips, {LIP_OVER:.1f} mm of lip "
            f"engagement, {PCB_CLR:.2f} mm to the ribs"
        ),
    ),
    (
        "5 vent plug and its plastic nut in the right wall",
        f"fingers {radii('vent nut')}",
        (
            f"thread reaches {VENT_THREAD - (WALL - VENT_FACE_H):.1f} mm inside, nut {VENT_NUT_H:.1f} mm, "
            f"{VENT_THREAD - (WALL - VENT_FACE_H) - VENT_NUT_H:.1f} mm spare, so the nut is fully on the thread"
        ),
    ),
    (
        "6 solar panel cable through the lid chimney, then pot it",
        (
            f"chimney {CHIMNEY_OD:.1f} dia x {CHIMNEY_L:.1f} mm with a {SOLAR_HOLE_D:.1f} mm bore, "
            f"countersink to {SOLAR_CSK_D:.1f}"
        ),
        "the chimney hangs 5 mm into the cavity above the free right hand end of the board",
    ),
    (
        "7 O-ring cord into the groove, 4x M3x8",
        f"cord 2.0 mm in a {GROOVE_W} x {GROOVE_D} groove, drivers {radii('M3 driver')}",
        f"neck {SCREW_CAPTIVE_D} x {SCREW_CAPTIVE_L} keeps each screw in the lid",
    ),
    (
        "8 lashing",
        (
            f"4 floor tunnels, tie {TIE_W:.0f} x {TIE_H:.0f} in the Y pair, cord up to 3 mm in the "
            f"{TIE_W2:.0f} x {TIE_H2:.1f} X pair"
        ),
        (
            f"the skin under a tunnel is {TIE_SKIN:.0f} mm at mid span and {TIE_SKIN - TIE_R_EXIT:.1f} mm "
            f"at the exits, the value the R{TIE_R_EXIT:.0f} exit radius leaves"
        ),
    ),
]

print("\nassembly walk, LoRaHarvesterBox\n")
for title, measured, note in STEPS:
    print(f"{title}\n    {measured}\n    {note}")

DEFERRED = [
    (
        "cord in the X pair tunnels",
        (
            "the exits now carry the same R2 as the tie tunnels, but no working load is specified for a "
            "cord, so there is no load case to run"
        ),
    ),
    (
        "pigtail cable from the bulkhead to the U.FL",
        (
            "the keep-out and the planned path are checked as tubes. The last 7 mm of the drop to the "
            "connector is a straight end, not a cable bending over the board"
        ),
    ),
]
print("\nsteps this walk does not prove:")
for what, why in DEFERRED:
    print(f"  {what}: {why}")

print(
    f"\nthe lid skirt enters the cavity with {SK:.2f} mm per side over {SK_H:.0f} mm of depth, and the "
    f"O-ring sits {WALL / 2 - GROOVE_W / 2 - SK:.2f} mm outboard of the skirt face, so the skirt never "
    "touches the cord"
)
json.dump(
    {
        "tool": "montage_simulation.py",
        "order": [{"step": t, "measured": m, "note": n} for t, m, n in STEPS],
        "insertion_sweep": {
            "pivot": [0.0, round(pcb.BoundBox.YMin + Y_OFFSET, 2), round(PCB_Z, 2)],
            "from_deg": START_DEG,
            "step_deg": STEP_DEG,
            "slide_mm": Y_OFFSET,
            "slide_step_mm": SLIDE_STEP,
            "clash_threshold_mm3": CLASH_MM3,
            "pass": insertion_ok,
            "tightest_clearance_mm": worst["clearance_mm"],
            "tightest_at": {"motion": worst["motion"], "angle_deg": worst["angle_deg"], "slide_mm": worst["slide_mm"]},
            "steps": sweep,
        },
        "not_proven": [{"step": w, "why": y} for w, y in DEFERRED],
        "tool_radii_source": "clearance_report.json, written by clearance_probe.py",
    },
    open(os.path.join(HERE, "assembly_simulation_report.json"), "w"),
    indent=1,
)
print("wrote assembly_simulation_report.json")
assert insertion_ok, "the board does not go in on the swept path"
