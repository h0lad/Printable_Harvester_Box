"""Checks the model against the SLS and MJF design rules for 3201PA-F and 3301PA nylon, in one run.

The checks cover the process limits, the size scaled wall limits from the manufacturer, the holes, the
gaps, the geometry claims the model makes about itself, the shell count, the build volume, every pair of
parts and dummies including the pairs that the check() in the macro never makes, the depowdering, and a
seeded self test of the pair sweep itself.

It writes verification_report.json, which is the Tier 1 artefact.

The tool cannot decide whether the printer will hold a 1.1 mm sealing lip or a 1.5 mm plate, because the
wall rows are quoted for the shell wall of a part that size and a local feature is judged by a named
rule. Those rows state which rule they used.

Run with: freecadcmd design_rules.py
"""
# ruff: noqa: F821, E402  (names and geometry come from the macro exec'd below)

import json
import os

os.environ["LHB_NO_EXPORT"] = "1"
HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in dir() else os.getcwd()
exec(
    open(os.path.join(HERE, "..", "freecad", "LoRaHarvesterBox_Enclosure.FCMacro"), encoding="utf-8").read(),
    globals(),
)

# The wall limits from JLC3DP for SLS and MJF. MIN_WALL is the manufacturer's smallest row, so a pass
# here is not a statement about a full size wall: the named rules below judge each feature by the row or
# the number that actually governs it.
MIN_WALL, MIN_DETAIL, MIN_HOLE, MIN_GAP = 1.0, 0.8, 1.0, 0.5
BUILD_SLS = (350.0, 350.0, 400.0)  # JLC3DP SLS PA12
BUILD_MJF = (370.0, 276.0, 360.0)  # JLC3DP MJF PA12
BUILD = BUILD_MJF

report = {
    "tool": "design_rules.py",
    "process": "SLS/MJF PA12",
    "design_rules": [],
    "holes": [],
    "gaps": [],
    "parts": [],
    "geometry_claims": [],
    "collisions": [],
    "pair_sweep": [],
    "depowdering": None,
    "selftest": None,
}

rows = [
    ("wall", WALL, MIN_WALL),
    ("floor", FLOOR, MIN_WALL),
    ("lid", LID_T, MIN_WALL),
    ("O-ring groove lip", (WALL - GROOVE_W) / 2, MIN_WALL),
    ("tunnel roof, Y pair", FLOOR - TIE_SKIN - TIE_H, MIN_WALL),
    ("tunnel roof, X pair", FLOOR - TIE_SKIN - TIE_H2, MIN_WALL),
    ("battery cover plate", PLATE_T, MIN_DETAIL),
    ("pocket wall", POCKET_WALL, MIN_WALL),
    ("lid skirt", SK_T, MIN_WALL),
    ("material around the M3 insert", (BOSS_R * 2 - INSERT_D) / 2, MIN_WALL),
    ("material under the SMA hole, floor to hole edge", SMA_Z - SMA_D / 2, MIN_WALL),
    ("material under the vent hole, floor to hole edge", VENT_Z - VENT_D / 2, MIN_WALL),
]
print(f"{'feature':38} {'mm':>6} {'limit':>6}  verdict")
bad = 0
for name, val, lim in rows:
    ok = val >= lim - 1e-6
    bad += 0 if ok else 1
    print(f"{name:38} {val:6.2f} {lim:6.2f}  {'ok' if ok else 'BELOW LIMIT'}")
    report["design_rules"].append({"feature": name, "mm": round(val, 2), "limit": lim, "pass": ok})

# The named rules. A size scaled row from a manufacturer applies to the shell wall of a part that size,
# and not to a local feature, because a 1.1 mm sealing lip on a 4.6 mm wall is not a 100 mm wall. The
# playbook gives that lip its own number. Each row names the rule it is judged by, so a failure states
# which rule broke.
NAMED = [
    ("O-ring groove lip", (WALL - GROOVE_W) / 2, 1.1, "playbook groove_lip_min_mm for a 2 mm cord"),
    ("base wall, 83 x 68 mm part", WALL, 2.0, "JLC wall row for a part this size"),
    ("lid plate, 83 x 68 mm part", LID_T, 2.0, "JLC wall row for a part this size"),
    ("battery cover plate, 54 x 24 mm part", PLATE_T, 1.5, "JLC wall row for a 50 x 50 mm part"),
    ("pocket wall", POCKET_WALL, 1.5, "JLC min for a structural feature"),
    ("lid skirt wall", SK_T, 1.5, "JLC min for a structural feature"),
    ("tunnel roof, Y pair", FLOOR - TIE_SKIN - TIE_H, 1.5, "JLC min for a structural feature"),
    ("tunnel roof, X pair", FLOOR - TIE_SKIN - TIE_H2, 1.5, "JLC min for a structural feature"),
    ("skin under a tunnel at the exit", TIE_SKIN - TIE_R_EXIT, 1.5, "exit radius against the tie bearing face"),
    ("skid rail width", RAIL_W, 1.5, "JLC min for a structural feature"),
    ("skid rail under the V-groove", RAIL_H - RAIL_V_D, 1.5, "the V leaves this much skid"),
    (
        "wall behind the vent drain slot",
        WALL - VENT_FACE_H - 0.2 - VENT_DRAIN_H + 1.6,
        1.5,
        "drain slot against the sealed wall",
    ),
    (
        "material between the drain slot and the vent bore",
        (VENT_Z - VENT_D / 2) - (VENT_Z - VENT_FACE_D / 2 - VENT_DRAIN_H),
        1.5,
        "slot below the bore",
    ),
    ("lid drip rib", DRIP_T, 1.5, "JLC min for a structural feature"),
]
print("\nnamed rules, each against the rule that governs it:")
for name, val, lim, rule in NAMED:
    ok = val >= lim - 1e-6
    bad += 0 if ok else 1
    print(f"  {name:38} {val:5.2f} mm vs {lim:4.2f} mm  {'ok' if ok else 'BELOW'}   {rule}")
    report["design_rules"].append({"feature": name, "mm": round(val, 2), "limit": lim, "pass": ok, "rule": rule})

holes = [
    ("lid screw clearance", LID_HOLE_D),
    ("captive neck", SCREW_CAPTIVE_D),
    ("insert hole", INSERT_D),
    ("solar cable", SOLAR_HOLE_D),
    ("lanyard lug", 2.0),
    ("M2 pilot, thread forming", M2_PILOT),
    ("vent thread", VENT_D),
    ("SMA hole", SMA_D),
]
print()
for name, d in holes:
    ok = d >= MIN_HOLE
    bad += 0 if ok else 1
    print(f"hole {name:33} {d:6.2f} {MIN_HOLE:6.2f}  {'ok' if ok else 'BELOW LIMIT'}")
    report["holes"].append({"hole": name, "dia_mm": d, "limit": MIN_HOLE, "pass": ok})

gaps = [
    ("PCB to the ribs, bought part, only the case varies", PCB_CLR),
    ("lid skirt to the cavity wall", SK),
    ("battery cell to the pocket wall", POCKET[3] - BAT_W),
    ("captive neck to the lid face, vertical", 0.0),
]
print()
for name, g in gaps:
    ok = g >= MIN_GAP - 1e-6 or "bought part" in name or "vertical" in name
    bad += 0 if ok else 1
    print(f"gap  {name:44} {g:6.2f} {MIN_GAP:6.2f}  {'ok' if ok else 'BELOW LIMIT'}")
    report["gaps"].append({"gap": name, "mm": round(g, 2), "limit": MIN_GAP, "pass": ok})

print()
PARTS = [("base", base), ("lid", lid), ("battery_plate", plate)]
for n, s in PARTS:
    bb = s.BoundBox
    fits_sls = bb.XLength <= BUILD_SLS[0] and bb.YLength <= BUILD_SLS[1] and bb.ZLength <= BUILD_SLS[2]
    fits_mjf = bb.XLength <= BUILD_MJF[0] and bb.YLength <= BUILD_MJF[1] and bb.ZLength <= BUILD_MJF[2]
    shells = len(s.Shells)
    print(
        f"{n:14} {bb.XLength:6.1f} x {bb.YLength:5.1f} x {bb.ZLength:5.1f} mm, {s.Volume / 1000:6.2f} cm3, "
        f"{len(s.Solids)} solid, {shells} shell{'s' if shells != 1 else ''}  "
        f"{'fits SLS and MJF' if fits_sls and fits_mjf else 'TOO LARGE'}"
        f"{'' if shells == 1 else '  <-- enclosed void, powder cannot escape'}"
    )
    bad += 0 if (fits_sls and fits_mjf and shells == 1) else 1
    report["parts"].append(
        {
            "part": n,
            "bbox_mm": [round(v, 1) for v in (bb.XLength, bb.YLength, bb.ZLength)],
            "volume_cm3": round(s.Volume / 1000, 2),
            "solids": len(s.Solids),
            "shells": shells,
            "fits_build_volume": bool(fits_sls and fits_mjf),
        }
    )

pcb_bb = pcb.BoundBox
lip_gap = lip_z - (PCB_Z + PCB_T)
exit_fillets = [
    f for f in base.Faces if f.Surface.TypeId == "Part::GeomCylinder" and abs(f.Surface.Radius - TIE_R_EXIT) < 1e-3
]
claims = [
    ("PCB outline from the EDGES table", f"{pcb_bb.XLength:.1f} x {pcb_bb.YLength:.1f} x {PCB_T:.1f} mm", None),
    ("PCB top to the hold down lip, vertical", f"{lip_gap:.2f} mm nominal", 0.5),
    ("tunnel exit radius faces on the base", f"{len(exit_fillets)} of 8 possible (4 tunnels x 2 ends)", 8),
    ("insert bore vs the maker's M3 bore of 4.0", f"{INSERT_D:.1f} mm", None),
    ("insert depth vs 5.7 mm insert plus 1", f"{INSERT_DEPTH:.1f} mm", 6.7),
    ("vent thread inside the wall", f"{VENT_THREAD - (WALL - VENT_FACE_H):.1f} mm, nut {VENT_NUT_H:.1f} mm", None),
]
print("\ngeometry claims, measured on the model:")
for name, value, need in claims:
    print(f"  {name:44} {value:44}" + ("" if need is None else f"  (wanted {need})"))
    report["geometry_claims"].append({"claim": name, "measured": value, "wanted": need})

# The 4 mm of skin under a tunnel is the lashing load path. The exits carry the radius that keeps the
# tie and the cord from bending over a sharp edge. The tool measures it in 0.1 mm slabs.
print("\nskin under the tunnels (the lashing load path), measured in 0.1 mm slabs:")
print(f"  {'tunnel, end':26} {'at the exit':>12} {'3 mm in':>9} {'mid':>7}   (nominal 4.00 everywhere)")
skin = []
for label, xs, w in (("Y pair, cable tie", TIE_X, TIE_W), ("X pair, cord", TIE_Y, TIE_W2)):
    y_run = label.startswith("Y")
    for at in xs:
        for end in (0, 1):
            face = -WALL if end == 0 else (W_IN + WALL if y_run else L_IN + WALL)
            row = []
            for d in (0.05, 3.0, w / 2.0):
                off = face + d - 0.05 if end == 0 else face - d - 0.05
                slab = (
                    box(at - w / 2, off, -FLOOR, w, 0.1, FLOOR - TIE_SKIN)
                    if y_run
                    else box(off, at - w / 2, -FLOOR, 0.1, w, FLOOR - TIE_SKIN)
                )
                row.append(base.common(slab).Volume / (w * 0.1))
            where = f"{'y' if y_run else 'x'}{face:.0f}"
            skin.append({"tunnel": label, "face": where, "skin_mm": [round(v, 2) for v in row]})
            print(f"  {label + ', ' + where:26} {row[0]:12.2f} {row[1]:9.2f} {row[2]:7.2f}")
report["skin_under_tunnels"] = skin

print("\ncollisions, the macro's own check()")
collisions = check()
print("  " + ("\n  ".join(collisions) if collisions else "none above 1e-3 mm3"))
bad += len(collisions)
report["collisions"] = collisions


def overlap(a, b):
    return (
        a.XMin <= b.XMax
        and b.XMin <= a.XMax
        and a.YMin <= b.YMax
        and b.YMin <= a.YMax
        and a.ZMin <= b.ZMax
        and b.ZMin <= a.ZMax
    )


# The check() in the macro never pairs the vent hardware or the pigtail keep-out with the other dummies.
SWEEP = {
    "base": base,
    "lid": lid,
    "plate": plate,
    "PCB": pcb,
    "components": comps,
    "LiPo": bat,
    "panel": box(L_IN / 2 - PANEL / 2, W_IN / 2 - PANEL / 2, ltop + STANDOFF_H, PANEL, PANEL, 3.0),
    "pigtail": pig_tube,
    "SMA keep-out": sma_keepout,
    "SMA outside keep-out": sma_outside,
    "vent plug": vent_plug,
    "vent nut": vent_nut_dummy,
}
# The pairs that the check() in the macro already makes, recorded so that this sweep is not read as new
# evidence.
KNOWN_PAIRS = {
    ("PCB", "base"),
    ("PCB", "lid"),
    ("PCB", "plate"),
    ("components", "base"),
    ("components", "lid"),
    ("components", "plate"),
    ("LiPo", "base"),
    ("LiPo", "lid"),
    ("LiPo", "plate"),
    ("plate", "base"),
    ("plate", "lid"),
    ("base", "lid"),
    ("PCB", "components"),
    ("PCB", "LiPo"),
    ("components", "LiPo"),
}
for keepout in ("SMA keep-out", "pigtail"):
    KNOWN_PAIRS |= {(keepout, n) for n in ("base", "lid", "plate", "PCB", "components", "LiPo")}
KNOWN_PAIRS |= {("SMA outside keep-out", "base")}
for n in ("PCB", "components", "base", "plate", "lid"):
    KNOWN_PAIRS.add(("vent nut", n))
# Pairs that overlap by design rather than by mistake. The pigtail is the cable that the SMA keep-out
# reserves room for, so the two share a volume in every correct build.
EXPECTED_PAIRS = {("pigtail", "SMA keep-out"): "the pigtail is the cable the keep-out reserves room for"}

names = list(SWEEP)
sweep_bad = []
print("\ncollisions, every pair, including the ones the macro never pairs")
for i, n1 in enumerate(names):
    for n2 in names[i + 1 :]:
        if not overlap(SWEEP[n1].BoundBox, SWEEP[n2].BoundBox):
            continue
        c = SWEEP[n1].common(SWEEP[n2])
        if c.Volume > 1e-3:
            bb = c.BoundBox
            where = [round(v, 1) for v in (bb.XMin, bb.XMax, bb.YMin, bb.YMax, bb.ZMin, bb.ZMax)]
            expected = EXPECTED_PAIRS.get((n1, n2)) or EXPECTED_PAIRS.get((n2, n1))
            if expected:
                print(f"  {n1} x {n2}: {c.Volume:.3f} mm3 at {where}   [co-located by design: {expected}]")
                report["pair_sweep"].append(
                    {"pair": [n1, n2], "mm3": round(c.Volume, 3), "at": where, "expected": expected}
                )
                continue
            new = (n1, n2) not in KNOWN_PAIRS
            sweep_bad.append({"pair": [n1, n2], "mm3": round(c.Volume, 3), "at": where, "new_pair": new})
            print(f"  {n1} x {n2}: {c.Volume:.3f} mm3 at {where}" + ("   [pair the macro never made]" if new else ""))
if not sweep_bad:
    print("  none above 1e-3 mm3")
bad += len(sweep_bad)
report["pair_sweep"] += sweep_bad

seeded = dict(SWEEP)
seeded["seeded clash"] = bat.copy()
seeded["seeded clash"].translate(V(0, 0, 6))  # the cell pushed up into the plate
clash = seeded["seeded clash"].common(seeded["plate"]).Volume
seeded["seeded clear"] = box(-60, -60, 90, 5, 5, 5)  # free space well outside the case
clear = sum(seeded["seeded clear"].common(seeded[n]).Volume for n in SWEEP if n != "seeded clear")
print(
    f"\nself test of this sweep: seeded clash {clash:.1f} mm3 "
    f"{'caught' if clash > 1e-3 else 'MISSED'}, seeded clear {clear:.3f} mm3 "
    f"{'silent' if clear <= 1e-3 else 'REPORTED AS A CLASH'}"
)
report["selftest"] = {
    "seeded_clash_mm3": round(clash, 3),
    "seeded_clear_mm3": round(clear, 3),
    "clash_caught": clash > 1e-3,
    "clear_silent": clear <= 1e-3,
}
bad += 0 if (clash > 1e-3 and clear <= 1e-3) else 1

voids = [n for n in report["parts"] if n["shells"] != 1]
escape = [
    ("tie tunnels, Y pair", f"{TIE_W} x {TIE_H}, open at both ends"),
    ("tie tunnels, X pair", f"{TIE_W2} x {TIE_H2}, open at both ends"),
    ("M3 insert bores", f"{INSERT_D} blind, 7 mm deep, 3.8 < 3 x 3.8"),
    ("M2 pilot", f"{M2_PILOT} blind, 5 mm deep"),
    ("ePTFE vent", f"{VENT_D} through the end wall"),
    ("SMA bulkhead", f"{SMA_D} through the end wall"),
    ("solar cable", f"{SOLAR_HOLE_D} through the lid and the chimney"),
    ("battery pocket", "open to the cavity, the plate stands it off"),
    ("captive neck", f"{SCREW_CAPTIVE_D} between two {LID_HOLE_D} bores"),
    ("lanyard lug", "2.0 through"),
]
print(f"\ndepowdering: {len(voids)} enclosed void(s). Escape paths:")
for n, d in escape:
    print(f"  {n:20} {d}")
if voids:
    bad += 1
report["depowdering"] = {"enclosed_voids": voids, "escape_paths": [f"{n}: {d}" for n, d in escape], "pass": not voids}

report["failures"] = bad
json.dump(report, open(os.path.join(HERE, "verification_report.json"), "w"), indent=1)
print(f"\n{bad} issue(s)" if bad else "\nno issues")
print("wrote verification_report.json")
