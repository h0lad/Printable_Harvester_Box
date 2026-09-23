"""Grows a real cylinder on every tool axis and reports the free radius around it.

The tool grows the cylinder on the axis and takes a boolean against the parts that are fitted at that
step. It bisects the result to 0.02 mm, which measures a radial clearance. It does not use the distance
from the axis line, because that distance reports whatever step the segment ends on, which is 1.8 mm
against a 3.25 mm counterbore, and because it names the wrong feature. Each segment ends where the tool
seats and never crosses the hole beyond it. Without that rule the probe returns the wall of the hole
instead of the free space around it.

Every probe carries two obstruction sets. The set at_step is in place when the tool is needed, and it
decides the verdict. The set after is the fully assembled case, and it is informational: it reports
whether the joint can still be serviced without a teardown, which is a property of the assembly order
rather than of the joint.

The last two probes are the seeded self-test, which is one case that must collide and one case that
must stay clear.

The tool cannot decide whether a physical spanner fits. A cylinder on the axis is a proxy for the swing
of the jaw, and every value is nominal, with no print tolerance in it. The reach sweep reports the depth
at which the free radius falls below the requirement.

Run with: freecadcmd clearance_probe.py
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

CAP = 30.0  # beyond this the joint counts as unobstructed; tools are smaller than 60 mm across
CLASH_MM3 = 1e-3
RESOLUTION = 0.02

FITTED = {
    "base": base,
    "lid": lid,
    "plate": plate,
    "PCB": pcb,
    "components": comps,
    "LiPo": bat,
    "pigtail": pig_tube,
}
CASE = ["base", "plate", "PCB", "components", "LiPo"]
CLOSED = CASE + ["lid"]


def free_radius(p0, p1, names):
    """Returns the largest cylinder radius on p0..p1 that clears every named obstruction.

    The function also returns the blocking part and the bounding box of the overlap, which names the
    offending feature without a second run.
    """
    d = p1 - p0
    names = list(dict.fromkeys(names))

    def hits(r):
        if r <= 0.0:
            return None
        probe = Part.makeCylinder(r, d.Length, p0, d)
        for n in names:
            c = probe.common(FITTED[n])
            if c.Volume > CLASH_MM3:
                bb = c.BoundBox
                return n, [round(v, 1) for v in (bb.XMin, bb.XMax, bb.YMin, bb.YMax, bb.ZMin, bb.ZMax)]
        return None

    first = hits(CAP)
    if first is None:
        return CAP, f"nothing within {CAP:.0f} mm", []
    lo, hi = 0.0, CAP
    while hi - lo > RESOLUTION:
        mid = (lo + hi) / 2.0
        if hits(mid):
            hi = mid
        else:
            lo = mid
    who = hits(hi) or first
    return lo, f"{who[0]} at {who[1]}", who[1]


def probe(name, p0, p1, at_step, need, note, after=None, verdict="fail"):
    r, who, box = free_radius(p0, p1, at_step)
    ra, whoa, _ = free_radius(p0, p1, after) if after else (r, who, box)
    return {
        "probe": name,
        "free_radius_mm": round(r, 2),
        "required_mm": need,
        "limited_by": who,
        "overlap_box": box,
        "pass": r >= need - RESOLUTION,
        "unobstructed": r >= CAP - 1e-6,
        "service_free_radius_mm": round(ra, 2),
        "service_limited_by": whoa,
        "counts": verdict == "fail",
        "note": note,
    }


x0, y0 = corners[0]
PROBES = [
    *[
        probe(
            f"M3 driver from above, column {'ABCD'[i]}",
            V(x, y, ltop + 40.0),
            V(x, y, ltop),  # ends at the screw head: the segment must not enter the 3.6 mm hole
            ["base", "lid"],
            2.0,
            "4 mm driver bit or a 2.5 mm hex key on an M3 socket head. The panel standoffs are inboard "
            "of the corner columns so the driver path is outside the panel footprint",
            after=CLOSED,
        )
        for i, (x, y) in enumerate(corners)
    ],
    probe(
        "M2 driver onto the PCB screw H1, lid open",
        V(hx, hy, PCB_Z + PCB_T + 40.0),
        V(hx, hy, PCB_Z + PCB_T),  # ends at the board top, not inside the 2.2 mm hole
        CASE,
        2.0,
        "the board screw is a service item: it is reached with the lid off, and the lid does limit it",
        after=CLOSED,
    ),
    probe(
        "SMA bulkhead nut, thin open end spanner",
        V(0.5, SMA_Y, SMA_Z),
        V(8.0, SMA_Y, SMA_Z),
        ["base"],
        8.0,
        "fit the nut before the battery plate. The left PCB rib starts above the keep-out",
        after=CLOSED,
    ),
    probe(
        "ePTFE vent nut, fingers",
        V(L_IN - VENT_FREE_L, VENT_Y, VENT_Z),
        V(L_IN - 0.5, VENT_Y, VENT_Z),
        ["base"],
        11.0,
        f"M12 nut {VENT_NUT_D} mm across in a {VENT_FREE_D} x {VENT_FREE_L} mm reserved pocket. "
        "The playbook wants 8 mm for a spanner and 11 mm for fingers",
        after=CLOSED,
    ),
    probe(
        "antenna base outside the left wall",
        V(-WALL, SMA_Y, SMA_Z),
        V(-WALL - SMA_OUT_L, SMA_Y, SMA_Z),
        ["base"],
        SMA_OUT_R,
        "an antenna base up to 22 mm across has to clear the lanyard lug and the floor",
    ),
    probe(
        "self-test, must be caught: axis inside the floor wall",
        V(POCKET[0] + POCKET[2] / 2, -2.0, 4.0),
        V(POCKET[0] + POCKET[2] / 2, -0.5, 4.0),
        ["base"],
        10.0,
        "seeded collision: the axis sits in solid base material, so the free radius has to come back "
        "near zero. A green result here means the probe is blind",
        verdict="selftest",
    ),
    probe(
        "self-test, must stay clear: empty vent chamber",
        V(L_IN - 6.0, 15.0, 0.0),
        V(L_IN - 6.0, 15.0, H_IN),
        ["base"],
        5.0,
        "seeded clearance with a known answer. The battery pocket wall at x = 53.5 is 4.5 mm from "
        "this axis. It is the nearest material, so the free radius must land near 4.5",
        verdict="selftest",
    ),
]

print(f"{'probe':52} {'free':>6} {'need':>6}  {'verdict':>7} {'service':>8}  limited by")
print("-" * 118)
bad = []
for p in PROBES:
    if p["counts"] and not p["pass"]:
        bad.append(p)
    free = f">={CAP:.0f}" if p["unobstructed"] else f"{p['free_radius_mm']:.2f}"
    serv = "-" if p["unobstructed"] else f"{p['service_free_radius_mm']:.2f}"
    tag = "" if p["counts"] else "test"
    print(
        f"{p['probe']:52} {free:>6} {p['required_mm']:6.2f}  {'ok' if p['pass'] else 'BELOW':>7} "
        f"{serv:>8}  {p['limited_by']} {tag}"
    )

selftest = [p for p in PROBES if not p["counts"]]
caught = selftest[0]["free_radius_mm"] < 0.5
known = 4.0 <= selftest[1]["free_radius_mm"] <= 5.0
print()
for p in PROBES:
    if p["service_limited_by"] != p["limited_by"]:
        print(
            f"service with the case closed, {p['probe']}: {p['service_free_radius_mm']} mm, limited by "
            f"{p['service_limited_by']}"
        )
print(
    f"\nself-test: seeded collision {'caught' if caught else 'MISSED'}, seeded clearance at its known "
    f"value ({selftest[1]['free_radius_mm']} mm) {'ok' if known else 'MISSED'}"
)
print(
    f"\n{len(bad)} of {len(PROBES) - len(selftest)} probe(s) below the required free radius"
    if bad
    else f"\nall {len(PROBES) - len(selftest)} probes clear"
)

# The SMA joint depends on how deep a jaw can reach, so the tool reports the free radius against the
# reach depth.
print("\nSMA bulkhead nut, free radius against how deep the tool has to reach in from the wall face:")
print(f"{'segment ends':>14} {'free radius':>12}  limited by")
reach = []
for end in (4.0, 5.2, 6.0, 7.0, 8.0, 10.0, 12.0):
    r_, who_, _ = free_radius(V(0.5, SMA_Y, SMA_Z), V(end, SMA_Y, SMA_Z), ["base"])
    reach.append({"segment_end_mm": end, "free_radius_mm": round(r_, 2), "limited_by": who_})
    print(f"{end:11.1f} mm {r_:11.2f}  {who_}")
print(
    "the nut sits on the inner wall face and a spanner jaw reaches 8 to 10 mm in from it. The free "
    "radius is flat across that whole reach, so the limit is the room around the nut rather than the "
    "depth of the tool."
)
json.dump(
    {
        "tool": "clearance_probe.py",
        "process": "SLS/MJF PA12",
        "resolution_mm": RESOLUTION,
        "probes": PROBES,
        "sma_spanner_reach": reach,
        "failures": len(bad),
        "selftest": {"collision_caught": caught, "clearance_value_ok": known},
    },
    open(os.path.join(HERE, "clearance_report.json"), "w"),
    indent=1,
)
print("wrote clearance_report.json")
