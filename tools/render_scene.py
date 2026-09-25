"""Tessellates the render scenes into .npz files for render_raster.py.

# ruff: noqa: F821  (names come from the macro that is exec'd below)
"""
import math
import os

os.environ["LHB_NO_EXPORT"] = "1"
HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in dir() else os.getcwd()
MACRO = os.path.join(HERE, "..", "freecad", "LoRaHarvesterBox_Enclosure.FCMacro")
exec(open(MACRO, encoding="utf-8").read(), globals())

import numpy as np  # noqa: E402  (kept next to the FreeCAD imports the macro brings in)

COLOUR = dict(base=(0.74, 0.77, 0.81), lid=(0.66, 0.69, 0.74), plate=(0.30, 0.31, 0.34),
              pcb=(0.07, 0.40, 0.18), panel=(0.07, 0.10, 0.22), silver=(0.82, 0.83, 0.86),
              gold=(0.86, 0.68, 0.26), black=(0.10, 0.10, 0.11), oring=(0.92, 0.36, 0.18),
              steel=(0.62, 0.63, 0.66), battery=(0.25, 0.50, 0.85), plug=(0.14, 0.14, 0.15),
              nut=(0.95, 0.72, 0.15))
LID_TOP = H_IN + LID_T


def hex_body(x0, x1, y, z, across_flats, colour):
    """Hexagonal prism along X, used for the SMA nuts."""
    radius = across_flats / math.sqrt(3)
    profile = Part.makePolygon([V(0, radius * math.cos(math.radians(a)), radius * math.sin(math.radians(a)))
                                for a in range(0, 361, 60)])
    solid = Part.Face(profile).extrude(V(x1 - x0, 0, 0))
    solid.translate(V(x0, y, z))
    return (solid, colour)


def oring():
    """Sweeps the 2 mm cord along the centre line of the groove."""
    rim = rbox(-WALL / 2, -WALL / 2, 0, L_IN + WALL, W_IN + WALL, 1, R_IN + WALL / 2)
    face = [f for f in rim.Faces if abs(f.Surface.Axis.z) > 0.9 and f.BoundBox.ZMax < 0.01][0]
    wire = face.OuterWire
    edge = [e for e in wire.Edges if e.Curve.TypeId == "Part::GeomLine"][0]
    start = edge.Vertexes[0].Point
    direction = edge.Vertexes[1].Point - start
    direction.normalize()
    cord = wire.makePipeShell([Part.Wire(Part.Circle(start, direction, 1.0).toShape())], True, True)
    cord.translate(V(0, 0, H_IN - GROOVE_D + 1.0))
    return (cord, COLOUR["oring"])


def tessellate(items, lift=0.0, cut=None):
    groups = []
    for shape, colour in items:
        shape = shape.copy()
        if cut is not None:
            shape = shape.common(cut)
            if shape.Volume < 1e-3:
                continue
        if lift:
            shape.translate(V(0, 0, lift))
        points, facets = shape.tessellate(0.03)
        if not facets:
            continue
        vertices = np.array([[p.x, p.y, p.z] for p in points])
        groups.append((vertices[np.array(facets)], colour))
    return groups


def save(name, groups):
    payload = {}
    for i, (triangles, colour) in enumerate(groups):
        payload[f"t{i}"] = triangles
        payload[f"c{i}"] = np.array(colour)
    np.savez_compressed(os.path.join(HERE, f"{name}.npz"), **payload)
    print(name, len(groups), sum(len(g[0]) for g in groups))


panel = [(box(L_IN / 2 - PANEL / 2, W_IN / 2 - PANEL / 2, LID_TOP + STANDOFF_H, PANEL, PANEL, 3.0), COLOUR["panel"])]
for i in range(1, 5):
    x = L_IN / 2 - PANEL / 2 + i * PANEL / 5 - 0.2
    panel.append((box(x, W_IN / 2 - PANEL / 2 + 2, LID_TOP + STANDOFF_H + 3.0, 0.4, PANEL - 4, 0.05), COLOUR["silver"]))

sma = [(cyl(-8.0, SMA_Y, SMA_Z, 3.1, 16.0, V(1, 0, 0)), COLOUR["gold"]),
       (cyl(8.0, SMA_Y, SMA_Z, 2.4, SMA_NOSE - 8.0, V(1, 0, 0)), COLOUR["gold"]),
       hex_body(0.2, 3.0, SMA_Y, SMA_Z, 8, COLOUR["gold"]),
       hex_body(-6.2, -4.0, SMA_Y, SMA_Z, 8, COLOUR["gold"])]

antenna = [(cyl(-6.4, SMA_Y, SMA_Z, 9.0, 8.0, V(-1, 0, 0)), COLOUR["black"]),
           (Part.makeSphere(5.5, V(-19.5, SMA_Y, SMA_Z)), COLOUR["black"]),
           (cyl(-14.4, SMA_Y, SMA_Z, 4.0, 5.1, V(-1, 0, 0)), COLOUR["black"]),
           (cyl(-19.5, SMA_Y, SMA_Z, 5.0, 60), COLOUR["black"]),
           (Part.makeCone(5.0, 2.5, 8, V(-19.5, SMA_Y, SMA_Z + 60)), COLOUR["black"])]

screws = [(cyl(x, y, LID_TOP - 0.01, 2.75, 2.0).fuse(cyl(x, y, LID_TOP - 9, 1.5, 9)), COLOUR["steel"])
          for (x, y) in corners]

vent = [(vent_plug, COLOUR["plug"]), (vent_nut_dummy, COLOUR["nut"])]
inside = [(pcb, COLOUR["pcb"]), (comps, COLOUR["silver"]), (bat, COLOUR["battery"])] + sma + vent
shell = [(base, COLOUR["base"]), (plate, COLOUR["plate"]), oring()]
lid_group = [(lid, COLOUR["lid"])] + panel

save("sA", tessellate(shell + inside + antenna) + tessellate(lid_group, 45) + tessellate(screws, 60))
save("sB", tessellate(shell + inside + lid_group + screws + antenna))
save("sC", tessellate(shell + inside + lid_group + screws + antenna, cut=box(-150, SMA_Y, -80, 400, 200, 300)))
save("sD", tessellate(shell + inside + lid_group + screws + antenna))
save("sE", tessellate(shell + inside + lid_group + screws + antenna, cut=box(-150, VENT_Y, -80, 400, 200, 300)))
save("sF", tessellate([(base, COLOUR["base"])] + vent, cut=box(40, VENT_Y - 26, VENT_Z - 24, 45, 52, 50)))
save("sG", tessellate([(base, COLOUR["base"]), (lid, COLOUR["lid"])] + vent,
                      cut=box(48, VENT_Y, VENT_Z - 20, 36, 30, 42)))
