"""Writes 2D cross sections of the model to sections.json, and draws them to docs/.

The playbook treats the dimensioned section as its most effective single review tool, so the tool draws
the sections at scale and commits them as images. The same polylines go to JSON for anything that wants
the numbers.

It writes docs/validation_sections.png, which holds five views, and docs/vent_detail.png, which is the
vent at a larger scale. matplotlib draws both, so the tool needs it.

Run with: freecadcmd sections_export.py
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
    """Cuts every shape with a thin slab and stores the resulting edges as polylines in SECTIONS."""
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


section(
    "vent_xz", [(base, "base"), (lid, "lid"), (vent_nut_dummy, "nut"), (vent_plug, "plug")], "y", VENT_Y, ("x", "z")
)
section("tie_yz", [(base, "base")], "x", TIE_X[0], ("y", "z"))
section("corner_xz", [(base, "base"), (lid, "lid")], "y", -BOSS_OFF, ("x", "z"))
section("rim_xz", [(base, "base"), (lid, "lid")], "y", 20.0, ("x", "z"))
section("pcb_xy", [(base, "base"), (pcb, "pcb")], "z", PCB_Z + 0.8, ("x", "y"))

with open(os.path.join(HERE, "sections.json"), "w") as handle:
    json.dump(SECTIONS, handle)
print("ok", {k: len(v) for k, v in SECTIONS.items()})

import matplotlib  # noqa: E402  (only needed for the drawing half)

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

COLOUR = {
    "base": "#4a5568",
    "lid": "#a0aec0",
    "plate": "#2d3748",
    "pcb": "#276749",
    "nut": "#d69e2e",
    "plug": "#1a202c",
}
VIEW = {
    "vent_xz": ("vent plug and its nut, y = %.1f" % VENT_Y, None),
    "tie_yz": ("lashing tunnel, x = %.1f" % TIE_X[0], None),
    "corner_xz": ("screw column and O-ring groove, y = %.1f" % -BOSS_OFF, None),
    "rim_xz": ("wall, groove and lid skirt, y = 20", None),
    "pcb_xy": ("board in the cavity, z = %.1f" % (PCB_Z + 0.8), None),
}
fig, axes = plt.subplots(2, 3, figsize=(21, 12))
for ax, (name, (title, _)) in zip(axes.ravel(), VIEW.items()):
    for tag, pts in SECTIONS[name]:
        xs, ys = zip(*pts)
        ax.plot(xs, ys, color=COLOUR.get(tag, "k"), lw=1.0, label=tag)
    ax.set_title(title, fontsize=11)
    ax.set_aspect("equal")
    ax.grid(alpha=0.25, lw=0.5)
    handles, labels = ax.get_legend_handles_labels()
    seen = dict(zip(labels, handles))
    ax.legend(seen.values(), seen.keys(), fontsize=8, loc="upper right")
axes.ravel()[-1].axis("off")
fig.tight_layout()
fig.savefig(os.path.join(HERE, "..", "docs", "validation_sections.png"), dpi=130)
print("wrote docs/validation_sections.png")

fig2, ax = plt.subplots(figsize=(9, 7))
for tag, pts in SECTIONS["vent_xz"]:
    xs, ys = zip(*pts)
    ax.plot(xs, ys, color=COLOUR.get(tag, "k"), lw=1.2, label=tag)
ax.set_xlim(L_IN - 4.0, L_IN + WALL + 7.0)
ax.set_ylim(VENT_Z - 12.0, VENT_Z + 12.0)
ax.set_title("vent plug, thread engagement and nut grip space, y = %.1f" % VENT_Y, fontsize=11)
ax.set_aspect("equal")
ax.grid(alpha=0.25, lw=0.5)
handles, labels = ax.get_legend_handles_labels()
seen = dict(zip(labels, handles))
ax.legend(seen.values(), seen.keys(), fontsize=8)
fig2.tight_layout()
fig2.savefig(os.path.join(HERE, "..", "docs", "vent_detail.png"), dpi=140)
print("wrote docs/vent_detail.png")
