"""Renders a tessellated scene (.npz from render_scene.py) to a PNG.

Usage: python3 render_raster.py scene.npz <azimuth deg> <elevation deg> out.png
"""

import math
import sys

import numpy as np
from PIL import Image, ImageFilter


def render(npz, azimuth, elevation, out_path, width=1500, height=1100, supersample=2, pad=0.05):
    data = np.load(npz)
    count = len([k for k in data.files if k.startswith("t")])
    groups = [(data[f"t{i}"].astype(np.float64), data[f"c{i}"]) for i in range(count)]

    az, el = math.radians(azimuth), math.radians(elevation)
    camera = np.array([math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)])
    up = np.array([0, 0, 1.0]) if abs(elevation) < 89 else np.array([0, 1.0, 0])
    right = np.cross(-camera, up)
    right /= np.linalg.norm(right)
    view = np.stack([right, np.cross(right, -camera), camera])

    corners = np.vstack([g[0].reshape(-1, 3) for g in groups]) @ view.T
    low, high = corners.min(0), corners.max(0)
    w, h = width * supersample, height * supersample
    scale = min(w * (1 - 2 * pad) / (high[0] - low[0]), h * (1 - 2 * pad) / (high[1] - low[1]))
    off_x = w / 2 - scale * (low[0] + high[0]) / 2
    off_y = h / 2 + scale * (low[1] + high[1]) / 2

    depth = np.full((h, w), -1e9)
    colour = np.ones((h, w, 3))
    ident = np.full((h, w), -1, np.int32)
    normals = np.zeros((h, w, 3))

    key = np.array([-0.35, -0.5, 0.8])
    key = view @ (key / np.linalg.norm(key))
    fill = np.array([0.6, 0.3, 0.75])
    fill /= np.linalg.norm(fill)
    half = key + np.array([0, 0, 1.0])
    half /= np.linalg.norm(half)

    for index, (triangles, base_colour) in enumerate(groups):
        points = triangles @ view.T
        normal = np.cross(points[:, 1] - points[:, 0], points[:, 2] - points[:, 0])
        length = np.linalg.norm(normal, axis=1)
        keep = length > 1e-12
        points, normal = points[keep], normal[keep] / length[keep, None]
        normal[normal[:, 2] < 0] *= -1

        diffuse = 0.28 + 0.55 * np.clip(normal @ key, 0, 1) + 0.22 * np.clip(normal @ fill, 0, 1)
        specular = 0.22 * np.clip(normal @ half, 0, 1) ** 40
        shade = np.clip(np.outer(diffuse, base_colour) + specular[:, None], 0, 1)

        px = off_x + scale * points[:, :, 0]
        py = off_y - scale * points[:, :, 1]
        pz = points[:, :, 2]

        for k in range(len(points)):
            x0, x1, x2 = px[k]
            y0, y1, y2 = py[k]
            xmin = max(int(math.floor(min(x0, x1, x2))), 0)
            xmax = min(int(math.ceil(max(x0, x1, x2))), w - 1)
            ymin = max(int(math.floor(min(y0, y1, y2))), 0)
            ymax = min(int(math.ceil(max(y0, y1, y2))), h - 1)
            if xmax < xmin or ymax < ymin:
                continue
            area = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
            if abs(area) < 1e-9:
                continue
            gx, gy = np.meshgrid(np.arange(xmin, xmax + 1) + 0.5, np.arange(ymin, ymax + 1) + 0.5)
            b0 = ((y1 - y2) * (gx - x2) + (x2 - x1) * (gy - y2)) / area
            b1 = ((y2 - y0) * (gx - x2) + (x0 - x2) * (gy - y2)) / area
            b2 = 1 - b0 - b1
            inside = (b0 >= -1e-6) & (b1 >= -1e-6) & (b2 >= -1e-6)
            if not inside.any():
                continue
            z = b0 * pz[k, 0] + b1 * pz[k, 1] + b2 * pz[k, 2]
            window = depth[ymin:ymax + 1, xmin:xmax + 1]
            update = inside & (z > window)
            if not update.any():
                continue
            window[update] = z[update]
            colour[ymin:ymax + 1, xmin:xmax + 1][update] = shade[k]
            ident[ymin:ymax + 1, xmin:xmax + 1][update] = index
            normals[ymin:ymax + 1, xmin:xmax + 1][update] = normal[k]

    edge = np.zeros((h, w), bool)
    for dy, dx in ((0, 1), (1, 0)):
        here, there = ident[:h - dy, :w - dx], ident[dy:, dx:]
        crease = (normals[:h - dy, :w - dx] * normals[dy:, dx:]).sum(-1) < 0.75
        step = np.abs(depth[:h - dy, :w - dx] - depth[dy:, dx:]) > 1.2
        edge[:h - dy, :w - dx] |= (here != there) | ((here >= 0) & crease) | ((here >= 0) & (there >= 0) & step)
    if supersample > 1:
        edge = np.array(Image.fromarray(edge.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(3))) > 0

    background = ident < 0
    gradient = np.linspace(0.97, 0.88, h)[:, None, None] * np.ones((1, w, 3))
    colour[background] = gradient[background]
    colour[edge] *= 0.25

    image = Image.fromarray((colour * 255).astype(np.uint8)).resize((width, height), Image.LANCZOS)
    image.save(out_path)
    return image


if __name__ == "__main__":
    render(sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4])
