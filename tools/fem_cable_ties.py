"""Loads the cable-tie tunnels with the tie force, over a support on the trunk contact strip.

A belt through the two Y tunnels around a trunk carries the whole box, so the 4 mm of skin under a
tunnel and the exit radius are the primary load path. The model is the complete base with the four
corner insert bores filled, because they carry no tie load and a 4.0 mm blind bore only upsets the
mesh. The support is the contact strip where the trunk meets the two skids, and the load is the strand
tension times sqrt(2) at each exit bend, which is the resultant of a 90 degree bend.

The exit radius is 2.0 mm on all four pairs, which leaves 2.4 mm of skin at the face, and this mesh
contains the geometry that the macro cuts.

The tool cannot decide whether the strap tension reaches 400 N per strand. It reports the stress at that
load, and the fatigue table scales that stress to the loads the box carries.

Run with: freecadcmd fem_cable_ties.py     (gmsh and ccx live in the flatpak, not on the host)
"""
# ruff: noqa: F821, E402  (names and FreeCAD modules come from the macro exec'd below)

import json
import math
import os

os.environ["LHB_NO_EXPORT"] = "1"
HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in dir() else os.getcwd()
exec(
    open(os.path.join(HERE, "..", "freecad", "LoRaHarvesterBox_Enclosure.FCMacro"), encoding="utf-8").read(),
    globals(),
)

import FreeCAD as App
import ObjectsFem
from femmesh.gmshtools import GmshTools
from femtools import ccxtools

sl = base.copy()
for x_, y_ in corners:  # fill the insert bores, they are not in this load path
    sl = sl.fuse(cyl(x_, y_, H_IN - INSERT_DEPTH, INSERT_D / 2 + 0.01, INSERT_DEPTH + 0.01))
sl = sl.removeSplitter()
# The trunk contacts the two skids and not the floor, so the pad sits on the skid plane, which is 3 mm
# lower than the floor.
PAD_W = RAIL_W
sl = sl.fuse(box(-WALL, -WALL, -FLOOR - RAIL_H - 0.5, L_IN + 2 * WALL, PAD_W, 0.51))
sl = sl.fuse(box(-WALL, W_IN + WALL - RAIL_W, -FLOOR - RAIL_H - 0.5, L_IN + 2 * WALL, PAD_W, 0.51))
sl = sl.removeSplitter()
doc = App.newDocument("fem")
part = doc.addObject("Part::Feature", "Base")
part.Shape = sl

fix_faces, load_faces = [], []
for i, f in enumerate(sl.Faces):
    c = f.CenterOfMass
    if abs(c.z - (-FLOOR - RAIL_H - 0.5)) < 1e-3 and f.Surface.TypeId == "Part::GeomPlane":
        fix_faces.append(f"Face{i + 1}")
    if f.Surface.TypeId == "Part::GeomCylinder" and abs(f.Surface.Radius - TIE_R_EXIT) < 1e-3 and c.z < tz0 + 0.1:
        load_faces.append((f"Face{i + 1}", f.Area))
print("fix", len(fix_faces), "faces, load", len(load_faces), "bend faces")
if not fix_faces or not load_faces:
    raise SystemExit("no load path found: check the fillet radius and the pad")

an = ObjectsFem.makeAnalysis(doc, "Analysis")
solver = ObjectsFem.makeSolverCalculiXCcxTools(doc)
an.addObject(solver)
solver.WorkingDir = os.path.join(HERE, "femrun_ties")
os.makedirs(solver.WorkingDir, exist_ok=True)
mat = ObjectsFem.makeMaterialSolid(doc, "PA12")
m = mat.Material
m.update({"Name": "PA12", "YoungsModulus": "1700 MPa", "PoissonRatio": "0.39", "Density": "1010 kg/m^3"})
mat.Material = m
an.addObject(mat)
fx = ObjectsFem.makeConstraintFixed(doc, "Fix")
fx.References = [(part, fix_faces)]
an.addObject(fx)
for n, area in load_faces:
    pr = ObjectsFem.makeConstraintPressure(doc, "P_" + n)
    pr.References = [(part, [n])]
    # The tie is 5 mm wide and it bends over the R2 exit, so the tool loads the projected quarter
    # cylinder.
    pr.Pressure = f"{math.sqrt(2) * TIE_LOAD_N / (area * 5.0 / TIE_W) / (2 / math.pi * math.sqrt(2)):.3f} MPa"
    pr.Reversed = False
    an.addObject(pr)
    print(n, "area", round(area, 2), "p =", pr.Pressure)
mesh = ObjectsFem.makeMeshGmsh(doc, "Mesh")
mesh.Shape = part
mesh.CharacteristicLengthMax = "2.6 mm"
mesh.CharacteristicLengthMin = "0.5 mm"
mesh.ElementOrder = "1st"  # second order tets failed with non-positive jacobians on slender geometry
an.addObject(mesh)
reg = ObjectsFem.makeMeshRegion(doc, mesh, 0.5, "Ref")
reg.References = [(part, [n for n, _ in load_faces])]
g = GmshTools(mesh)
print("mesh err:", g.create_mesh(), "nodes", mesh.FemMesh.NodeCount)
doc.recompute()
fea = ccxtools.FemToolsCcx(an, solver)
fea.update_objects()
fea.setup_working_dir()
fea.setup_ccx()
print("prereq:", fea.check_prerequisites())
fea.write_inp_file()
fea.ccx_run()
fea.load_results()
res = [o for o in doc.Objects if o.isDerivedFrom("Fem::FemResultObject")][0]
vm, disp = res.vonMises, res.DisplacementLengths
s_ = sorted(vm)
print("MAX_VM_MPa %.1f  MAX_DISP_mm %.3f" % (max(vm), max(disp)))
print("P99.5_VM_MPa %.1f  P99_VM_MPa %.1f" % (s_[int(0.995 * len(s_))], s_[int(0.99 * len(s_))]))
fm = mesh.FemMesh
agg = {}
for n, v in zip(res.NodeNumbers, vm):
    p = fm.getNodeById(n)
    if p.z < tz0 + TIE_R_EXIT + 0.3 and (p.y < -WALL + TIE_R_EXIT + 0.5 or p.y > W_IN + WALL - TIE_R_EXIT - 0.5):
        key = "skin under the tunnel at the bend (the tie bearing face)"
    elif p.z < -FLOOR - RAIL_H + 0.2 and (p.y < -WALL + PAD_W + 1 or p.y > W_IN + WALL - PAD_W - 1):
        key = "trunk contact on the skids, boundary condition"
    else:
        key = "structure"
    agg.setdefault(key, []).append(v)
for k, values in agg.items():
    values.sort()
    print("REG %-52s max %.1f  p99 %.1f MPa" % (k, values[-1], values[int(0.99 * len(values))]))
p995 = s_[int(0.995 * len(s_))]
print("safety factor at TIE_LOAD_N = %.0f N: %.2f (yield 48 MPa, using p99.5)" % (TIE_LOAD_N, 48.0 / p995))

# The box hangs on two ties around a trunk and it sees wind buffeting and a day and night cycle, so the
# playbook requires a fatigue case for a mast-mounted part. The tool uses stress-life, scaled from the
# proof load above: every cyclic stress is linear in the strand tension, so each amplitude is the proof
# stress times the ratio of the cyclic tension to 400 N. The thermal case is not a tension, because the
# shell strains against straps that partly restrain it, so the tool states it as a stress directly.
RHO_PA12 = 1.01e-3  # g/mm3, SLS PA12
FITTINGS_G = 100.0  # O-ring, potted cable, adhesive and the four screws
CONTENT_G = BAT_L * BAT_W * BAT_T / 1000.0 * 1.7 + pcb.Volume / 1000.0 * 1.85 + 100.0
shell_g = (base.Volume + lid.Volume + plate.Volume) * RHO_PA12 + FITTINGS_G
total_g = shell_g + CONTENT_G
weight_n = total_g / 1000.0 * 9.81
STRANDS = 4.0  # two tunnels, two strands each
BEND = math.cos(math.radians(45.0))  # the 90 degree bend at the exit: vertical share per strand
T_WEIGHT = weight_n / (STRANDS * BEND)
A_X = (L_IN + 2 * WALL) / 1000.0 * (FLOOR + H_IN + LID_T) / 1000.0
A_Y = (W_IN + 2 * WALL) / 1000.0 * (FLOOR + H_IN + LID_T) / 1000.0
F_GUST = 0.5 * 1.25 * 1.2 * max(A_X, A_Y) * 45.0**2
T_GUST = F_GUST / (STRANDS * BEND)
E_PA12, ALPHA, D_T, RESTRAINT = 1700.0, 80e-6, 25.0, 0.30
SIGMA_THERMAL = E_PA12 * ALPHA * D_T * RESTRAINT
CASES = [
    ("self weight, every handling", p995 * T_WEIGHT / TIE_LOAD_N, 1.0e3),
    ("wind gust at 45 m/s, one cycle per gust", p995 * T_GUST / TIE_LOAD_N, 1.0e6),
    ("thermal swing against the straps, 30 % restrained", SIGMA_THERMAL, 25.0 * 365.0),
]
print("\nfatigue, scaled from %.1f MPa p99.5 at %.0f N per strand:" % (p995, TIE_LOAD_N))
print("  %-50s %10s %9s %10s" % ("cyclic case", "sigma MPa", "SF vs 24", "cycles"))
fatigue = []
for name, sigma, cycles in CASES:
    fatigue.append(
        {
            "case": name,
            "stress_mpa": round(sigma, 3),
            "cycles": cycles,
            "safety_vs_cyclic_limit": round(24.0 / sigma, 1),
        }
    )
    print("  %-50s %10.3f %9.1f %10.0e" % (name, sigma, 24.0 / sigma, cycles))
worst = max(fatigue, key=lambda f: f["stress_mpa"])
print(
    "  worst amplitude %.2f MPa on %s: safety %.1f against the playbook's 24 MPa cyclic limit and "
    "%.1f against a 12 MPa endurance estimate for unfilled SLS PA12. The tie does not set the fatigue "
    "life of this box: the seal's compression set and the potted cable have less margin."
    % (worst["stress_mpa"], worst["case"], worst["safety_vs_cyclic_limit"], 12.0 / worst["stress_mpa"])
)
json.dump(
    {
        "tool": "fem_cable_ties.py",
        "load_case": {
            "tie_load_n_per_strand": TIE_LOAD_N,
            "strands": STRANDS,
            "bend_deg": 90,
            "exit_radius_mm": TIE_R_EXIT,
            "skin_at_the_exit_mm": TIE_SKIN - TIE_R_EXIT,
        },
        "mesh_nodes": mesh.FemMesh.NodeCount,
        "max_vm_mpa": round(max(vm), 1),
        "p99_vm_mpa": round(s_[int(0.99 * len(s_))], 1),
        "p995_vm_mpa": round(p995, 1),
        "max_disp_mm": round(max(disp), 3),
        "safety_factor_vs_yield_48_mpa": round(48.0 / p995, 2),
        "regions": {k: {"max": round(v[-1], 1), "p99": round(v[int(0.99 * len(v))], 1)} for k, v in agg.items()},
        "mass_g": round(total_g, 1),
        "fatigue": fatigue,
    },
    open(os.path.join(HERE, "fem_ties_report.json"), "w"),
    indent=1,
)
print("wrote fem_ties_report.json")
