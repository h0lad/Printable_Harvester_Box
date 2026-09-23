"""Loads the antenna with wind and reports the stress in the wall around the SMA bulkhead.

The mast joint of the box is the lashing tunnels, which tools/fem_cable_ties.py covers. The antenna is a
separate load path. The wind force on the whip turns into a moment at the bulkhead, and the bulkhead nut
clamps a 4.6 mm wall that carries a 6.9 mm hole. The model is the left slice of the base plus the shank,
the flange and the nut of the bulkhead, and it reduces the whip to a straight cantilever.

Run with: freecadcmd fem_antenna_wind.py    env: V_WIND (m/s), L_ANT (mm)
"""
# ruff: noqa: F821, E402  (names and FreeCAD modules come from the macro exec'd below)

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

V_WIND = float(os.environ.get("V_WIND", "45"))
L_ANT = float(os.environ.get("L_ANT", "120")) / 1000.0
D_ANT = 0.010
CD = 1.1
q = 0.5 * 1.25 * V_WIND**2
F = q * CD * L_ANT * D_ANT
print(
    f"wind {V_WIND:.0f} m/s, antenna {L_ANT * 1000:.0f} mm x {D_ANT * 1000:.0f} mm -> F = {F:.2f} N, "
    f"moment at the wall = {F * (L_ANT / 2 + 0.02) * 1000:.0f} Nmm"
)

sl = base.common(box(-40, -20, -FLOOR - 5, 70, W_IN + 40, FLOOR + H_IN + 10))  # left slice of the base
sl = sl.fuse(cyl(-18.0, SMA_Y, SMA_Z, 3.6, 24.0, V(1, 0, 0)))  # bulkhead shank through the wall
sl = sl.fuse(cyl(-WALL, SMA_Y, SMA_Z, 8.0, 2.0, V(-1, 0, 0)))  # flange on the outer wall face
sl = sl.fuse(cyl(0.0, SMA_Y, SMA_Z, 5.0, 3.0, V(1, 0, 0)))  # nut on the inner wall face
sl = sl.fuse(cyl(-WALL - 2.0, SMA_Y, SMA_Z, 8.0, 14.0, V(-1, 0, 0)))  # connector body
sl = sl.fuse(cyl(-16.0, SMA_Y, SMA_Z, D_ANT * 1000 / 2, L_ANT * 1000))  # whip
sl = sl.removeSplitter()
print("valid", sl.isValid(), "solids", len(sl.Solids), "shells", len(sl.Shells))
if len(sl.Solids) != 1:
    raise SystemExit("the slice is not one solid: fix the lofting before trusting the numbers")
sl = sl.Solids[0]
doc = App.newDocument("fem")
part = doc.addObject("Part::Feature", "Slice")
part.Shape = sl

fix, load = [], []
for i, f in enumerate(sl.Faces):
    c = f.CenterOfMass
    if f.Surface.TypeId == "Part::GeomPlane" and (abs(c.z + FLOOR + RAIL_H) < 1e-3 or abs(c.x - 30.0) < 1e-3):
        fix.append(f"Face{i + 1}")
    if f.Surface.TypeId == "Part::GeomCylinder" and abs(f.Surface.Radius - D_ANT * 1000 / 2) < 1e-3:
        load.append(f"Face{i + 1}")
print("fixed faces", len(fix), "loaded faces", len(load))
an = ObjectsFem.makeAnalysis(doc, "A")
solver = ObjectsFem.makeSolverCalculiXCcxTools(doc)
an.addObject(solver)
solver.WorkingDir = os.path.join(HERE, "femrun_wind")
os.makedirs(solver.WorkingDir, exist_ok=True)
mat = ObjectsFem.makeMaterialSolid(doc, "PA12")
m = mat.Material
m.update({"Name": "PA12", "YoungsModulus": "1700 MPa", "PoissonRatio": "0.39", "Density": "1010 kg/m^3"})
mat.Material = m
an.addObject(mat)
fx = ObjectsFem.makeConstraintFixed(doc, "Fix")
fx.References = [(part, fix)]
an.addObject(fx)
fc = ObjectsFem.makeConstraintForce(doc, "F")
fc.References = [(part, load)]
fc.Force = f"{F:.3f} N"
fc.DirectionVector = App.Vector(0, 1, 0)
fc.Reversed = False
an.addObject(fc)
mesh = ObjectsFem.makeMeshGmsh(doc, "Mesh")
mesh.Shape = part
mesh.CharacteristicLengthMax = "2.5 mm"
mesh.CharacteristicLengthMin = "0.8 mm"
mesh.ElementOrder = "1st"
an.addObject(mesh)
g = GmshTools(mesh)
g.create_mesh()
print("nodes", mesh.FemMesh.NodeCount)
doc.recompute()
fea = ccxtools.FemToolsCcx(an, solver)
fea.update_objects()
fea.setup_working_dir()
fea.setup_ccx()
fea.check_prerequisites()
fea.write_inp_file()
fea.ccx_run()
fea.load_results()
res = [o for o in doc.Objects if o.isDerivedFrom("Fem::FemResultObject")][0]
vm, disp = res.vonMises, res.DisplacementLengths
fm = mesh.FemMesh
wall = sorted(
    v
    for n, v in zip(res.NodeNumbers, vm)
    if -WALL - 1 < fm.getNodeById(n).x < WALL + 6 and abs(fm.getNodeById(n).y - SMA_Y) < 12
)
print(f"MAX_VM {max(vm):.1f} MPa, tip deflection {max(disp):.2f} mm")
print(
    f"wall around the SMA hole and the nut: max {wall[-1]:.1f} MPa, p99 {wall[int(0.99 * len(wall))]:.1f} MPa, "
    f"safety factor at p99 {48.0 / wall[int(0.99 * len(wall))]:.1f}"
)
