# Tools

All scripts expect the macro in `../freecad`.

| script | purpose | run with |
|---|---|---|
| integrity_check.py | compares the committed STEP files with a fresh macro run, prints key dimensions and the collision check | freecadcmd |
| sections_export.py | writes 2D cross sections to sections.json | freecadcmd |
| render_scene.py | tessellates the render scenes to .npz | freecadcmd |
| render_raster.py | renders an .npz scene to PNG: `python3 render_raster.py sA.npz -125 32 sA.png` | python3 |
