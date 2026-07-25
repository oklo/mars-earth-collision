#!/usr/bin/env python3
"""Render trial storyboard frames with a semi-transparent SPH density layer."""

from __future__ import annotations

import argparse
from pathlib import Path

import h5py
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.ndimage import gaussian_filter, maximum_filter

from render_impact_animation import (
    load_labels,
    mars_initial_lonlat,
    order_by_ids,
    project,
    realistic_surface_colors,
    snapshot_paths,
    visible_surface_mask,
)
from render_storyboard_animation import (
    auto_sizes,
    body_centers,
    contact_index,
    storyboard_camera,
    view_basis,
)


EARTH_VOLUME = np.array([0.18, 0.46, 0.82], dtype=np.float32)
MARS_VOLUME = np.array([0.82, 0.42, 0.20], dtype=np.float32)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--snapshot-dir", type=Path, required=True)
    p.add_argument("--basename", required=True)
    p.add_argument("--labels", type=Path, required=True)
    p.add_argument("--outdir", type=Path, default=Path("density_trial_frames"))
    p.add_argument("--duration", type=float, default=60.0)
    p.add_argument("--width", type=int, default=1920)
    p.add_argument("--height", type=int, default=1080)
    p.add_argument("--density-width", type=int, default=960)
    p.add_argument("--marker-scale", type=float, default=0.72)
    p.add_argument("--kernel-scale", type=float, default=1.25)
    p.add_argument("--density-alpha", type=float, default=0.54)
    p.add_argument("--density-gamma", type=float, default=0.72)
    p.add_argument("--front-depth-fraction", type=float, default=0.08)
    p.add_argument("--occlusion-depth-fraction", type=float, default=0.16)
    p.add_argument("--contact-time-hours", type=float, default=None)
    p.add_argument(
        "--taus",
        default="6,14,20,40,48,59",
        help="Comma-separated movie times, in seconds, to render from the 60 s storyboard.",
    )
    return p.parse_args()


def attr_scalar(value) -> float:
    return float(np.asarray(value).reshape(-1)[0])


def read_snapshot_all(path: Path):
    with h5py.File(path, "r") as f:
        g = f["PartType0"]
        coords = np.asarray(g["Coordinates"], dtype=np.float32)
        ids = np.asarray(g["ParticleIDs"], dtype=np.uint64)
        masses = np.asarray(g["Masses"], dtype=np.float32)
        smoothing = np.asarray(g["SmoothingLengths"], dtype=np.float32)
        densities = np.asarray(g["Densities"], dtype=np.float32)
        box = np.asarray(f["Header"].attrs["BoxSize"], dtype=np.float32).reshape(-1)
        if len(box) == 1:
            box = np.repeat(box[0], 3).astype(np.float32)
        time = attr_scalar(f["Header"].attrs["Time"])
    return time, coords - 0.5 * box, ids, masses, smoothing, densities


def reorder_to_reference(ids: np.ndarray, ids_ref: np.ndarray) -> np.ndarray | None:
    if np.array_equal(ids, ids_ref):
        return None
    lookup = {int(pid): i for i, pid in enumerate(ids)}
    return np.array([lookup[int(pid)] for pid in ids_ref], dtype=np.int64)


def load_geometry(paths: list[Path], ids_ref: np.ndarray):
    times: list[float] = []
    positions: list[np.ndarray] = []
    masses_ref: np.ndarray | None = None
    for path in paths:
        t, xyz, ids, masses, _, _ = read_snapshot_all(path)
        reorder = reorder_to_reference(ids, ids_ref)
        if reorder is not None:
            xyz = xyz[reorder]
            masses = masses[reorder]
        times.append(float(t))
        positions.append(xyz.astype(np.float32))
        masses_ref = masses.astype(np.float32)
    if masses_ref is None:
        raise SystemExit("No snapshots loaded")
    return np.asarray(times, dtype=np.float64), positions, masses_ref


def nearest_snapshot(paths: list[Path], times: np.ndarray, target_t: float, ids_ref: np.ndarray):
    i = int(np.argmin(np.abs(times - target_t)))
    t, xyz, ids, masses, smoothing, densities = read_snapshot_all(paths[i])
    reorder = reorder_to_reference(ids, ids_ref)
    if reorder is not None:
        xyz = xyz[reorder]
        masses = masses[reorder]
        smoothing = smoothing[reorder]
        densities = densities[reorder]
    return i, float(t), xyz.astype(np.float32), masses.astype(np.float32), smoothing.astype(np.float32), densities.astype(np.float32)


def parse_taus(text: str) -> list[float]:
    vals = [float(part.strip()) for part in text.split(",") if part.strip()]
    if not vals:
        raise SystemExit("--taus must contain at least one value")
    return vals


def splat_density(
    xy: np.ndarray,
    smoothing: np.ndarray,
    masses: np.ndarray,
    body_id: np.ndarray,
    extent: tuple[float, float, float, float],
    nx: int,
    ny: int,
    kernel_scale: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    xmin, xmax, ymin, ymax = extent
    xpix = (xy[:, 0] - xmin) / (xmax - xmin) * nx
    ypix = (xy[:, 1] - ymin) / (ymax - ymin) * ny
    valid = (xpix >= 0) & (xpix < nx) & (ypix >= 0) & (ypix < ny)
    if not np.any(valid):
        return np.zeros((ny, nx), dtype=np.float32), np.zeros((ny, nx), dtype=np.float32), np.zeros((ny, nx), dtype=np.float32)

    xpix = xpix[valid]
    ypix = ypix[valid]
    ix = np.floor(xpix).astype(np.int64)
    iy = np.floor(ypix).astype(np.int64)
    body = body_id[valid]
    w = masses[valid].astype(np.float64)
    h_pix = np.clip(smoothing[valid].astype(np.float64) * kernel_scale / ((xmax - xmin) / nx), 0.65, 18.0)

    earth = np.zeros((ny, nx), dtype=np.float64)
    mars = np.zeros((ny, nx), dtype=np.float64)
    bins = np.array([0.65, 0.95, 1.35, 1.9, 2.7, 3.8, 5.4, 7.6, 10.8, 15.2, 21.5])
    which = np.clip(np.searchsorted(bins, h_pix, side="right") - 1, 0, len(bins) - 2)
    for b in range(len(bins) - 1):
        use = which == b
        if not np.any(use):
            continue
        sigma = float(np.sqrt(bins[b] * bins[b + 1]))
        e_impulse = np.zeros((ny, nx), dtype=np.float64)
        m_impulse = np.zeros((ny, nx), dtype=np.float64)
        e = use & (body == 1)
        m = use & (body == 2)
        if np.any(e):
            np.add.at(e_impulse, (iy[e], ix[e]), w[e])
            earth += gaussian_filter(e_impulse, sigma=sigma, mode="constant", truncate=3.0)
        if np.any(m):
            np.add.at(m_impulse, (iy[m], ix[m]), w[m])
            mars += gaussian_filter(m_impulse, sigma=sigma, mode="constant", truncate=3.0)
    total = earth + mars
    return earth.astype(np.float32), mars.astype(np.float32), total.astype(np.float32)


def density_rgba(earth: np.ndarray, mars: np.ndarray, alpha_max: float, gamma: float) -> np.ndarray:
    total = earth + mars
    rgba = np.zeros((*total.shape, 4), dtype=np.float32)
    positive = total > 0
    if not np.any(positive):
        return rgba
    norm = float(np.quantile(total[positive], 0.995))
    norm = max(norm, float(np.max(total[positive])) * 1e-6)
    intensity = np.log1p(total / norm) / np.log1p(6.0)
    intensity = np.clip(intensity, 0.0, 1.0) ** gamma
    rgb = (
        earth[..., None] * EARTH_VOLUME[None, None, :]
        + mars[..., None] * MARS_VOLUME[None, None, :]
    ) / np.maximum(total[..., None], 1e-30)
    rgba[..., :3] = np.clip(rgb * (0.42 + 0.82 * intensity[..., None]), 0.0, 1.0)
    rgba[..., 3] = np.clip(alpha_max * intensity, 0.0, alpha_max)
    rgba[~positive, 3] = 0.0
    return rgba


def front_depth_map(
    xy: np.ndarray,
    depth: np.ndarray,
    body_id: np.ndarray,
    extent: tuple[float, float, float, float],
    nx: int,
    ny: int,
    footprint: int,
) -> np.ndarray:
    xmin, xmax, ymin, ymax = extent
    xpix = (xy[:, 0] - xmin) / (xmax - xmin) * nx
    ypix = (xy[:, 1] - ymin) / (ymax - ymin) * ny
    valid = (xpix >= 0) & (xpix < nx) & (ypix >= 0) & (ypix < ny) & (body_id > 0)
    front = np.full((ny, nx), -np.inf, dtype=np.float32)
    if not np.any(valid):
        return front
    ix = np.floor(xpix[valid]).astype(np.int64)
    iy = np.floor(ypix[valid]).astype(np.int64)
    np.maximum.at(front, (iy, ix), depth[valid].astype(np.float32))
    filled = np.where(np.isfinite(front), front, -1e30).astype(np.float32)
    return maximum_filter(filled, size=max(1, footprint), mode="nearest")


def surface_occlusion_mask(
    surface: np.ndarray,
    xy: np.ndarray,
    depth: np.ndarray,
    body_id: np.ndarray,
    front_map: np.ndarray,
    extent: tuple[float, float, float, float],
    radius_depth: float,
    tolerance_fraction: float,
) -> np.ndarray:
    xmin, xmax, ymin, ymax = extent
    ny, nx = front_map.shape
    xpix = (xy[:, 0] - xmin) / (xmax - xmin) * nx
    ypix = (xy[:, 1] - ymin) / (ymax - ymin) * ny
    in_frame = (xpix >= 0) & (xpix < nx) & (ypix >= 0) & (ypix < ny)
    occluded = np.zeros_like(surface)
    candidates = surface & in_frame & (body_id > 0)
    if not np.any(candidates):
        return occluded
    ix = np.floor(xpix[candidates]).astype(np.int64)
    iy = np.floor(ypix[candidates]).astype(np.int64)
    front = front_map[iy, ix]
    tol = tolerance_fraction * radius_depth
    occluded[candidates] = depth[candidates] < (front - tol)
    return occluded


def main() -> None:
    args = parse_args()
    paths = snapshot_paths(args.snapshot_dir, args.basename)
    t0, xyz0, ids_ref, _, _, _ = read_snapshot_all(paths[0])
    id_to_label_idx, label_body_id, label_classes, label_colors, label_lon, label_lat = load_labels(args.labels)
    body_id, classes, source_colors, lon, lat = order_by_ids(
        ids_ref, id_to_label_idx, label_body_id, label_classes, label_colors, label_lon, label_lat
    )
    mars_lon, mars_lat = mars_initial_lonlat(xyz0, body_id)
    colors = realistic_surface_colors(classes, source_colors, lon, lat, mars_lon, mars_lat)
    times, positions, masses = load_geometry(paths, ids_ref)
    earth, mars, system = body_centers(positions, masses, body_id)
    contact_i = contact_index(times, earth, mars, args.contact_time_hours)
    surface_size, _ = auto_sizes(len(body_id), args.marker_scale)

    args.outdir.mkdir(parents=True, exist_ok=True)
    aspect = args.width / args.height
    density_nx = args.density_width
    density_ny = int(round(args.density_width / aspect))
    taus = parse_taus(args.taus)
    print(f"Density trials: contact snapshot={contact_i:04d} t={times[contact_i] / 3600.0:.4f} hr")

    fig, ax = plt.subplots(figsize=(args.width / 160, args.height / 160), dpi=160)
    fig.patch.set_facecolor("#03050a")
    ax.set_facecolor("#03050a")
    fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
    ax.set_position([0, 0, 1, 1])
    ax.set_aspect("equal", adjustable="box")
    ax.axis("off")

    for out_i, tau in enumerate(taus):
        ax.clear()
        ax.set_facecolor("#03050a")
        ax.set_aspect("equal", adjustable="box")
        ax.axis("off")
        t, view, target, span, segment = storyboard_camera(tau, args.duration, times, contact_i, earth, mars, system)
        snap_i, snap_t, xyz, snap_masses, smoothing, densities = nearest_snapshot(paths, times, t, ids_ref)
        basis = view_basis(view)
        xy, depth = project((xyz - target).astype(np.float32), basis)
        yhalf = 0.5 * span
        xhalf = yhalf * aspect
        extent = (-xhalf, xhalf, -yhalf, yhalf)
        ax.set_xlim(-xhalf, xhalf)
        ax.set_ylim(-yhalf, yhalf)

        earth_density, mars_density, total_density = splat_density(
            xy, smoothing, snap_masses, body_id, extent, density_nx, density_ny, args.kernel_scale
        )
        rgba = density_rgba(earth_density, mars_density, args.density_alpha, args.density_gamma)
        ax.imshow(rgba, extent=extent, origin="lower", interpolation="bilinear", zorder=1)

        density_radius = float(np.median(smoothing[np.isfinite(smoothing)]) * args.kernel_scale)
        footprint = int(np.clip(np.ceil(2.5 * density_radius / ((2 * xhalf) / density_nx)), 3, 41))
        front = front_depth_map(xy, depth, body_id, extent, density_nx, density_ny, footprint)
        body_depth_radius = float(max(np.quantile(np.abs(depth[body_id == 1] - np.median(depth[body_id == 1])), 0.995), 1e-6))
        surface = visible_surface_mask(
            classes,
            body_id,
            depth,
            argparse.Namespace(surface_layer="front", front_depth_fraction=args.front_depth_fraction),
        )
        far_side = surface_occlusion_mask(
            surface, xy, depth, body_id, front, extent, body_depth_radius, args.occlusion_depth_fraction
        )
        surface &= ~far_side
        order = np.argsort(depth[surface])
        ax.scatter(
            xy[surface][order, 0],
            xy[surface][order, 1],
            s=surface_size,
            c=colors[surface][order],
            alpha=0.98,
            linewidths=0,
            zorder=3,
        )
        ax.text(0.025, 0.955, "Mars-Earth grazing collision", transform=ax.transAxes, color="white", fontsize=18, ha="left", va="top")
        ax.text(0.025, 0.905, f"t = {(snap_t - times[0]) / 3600.0:5.2f} hr", transform=ax.transAxes, color="#d8dde8", fontsize=12, ha="left", va="top")
        ax.text(0.025, 0.865, f"{segment}; density layer", transform=ax.transAxes, color="#8791a5", fontsize=8, ha="left", va="top")
        out = args.outdir / f"density_trial_tau{tau:05.1f}_snap{snap_i:04d}.png"
        fig.savefig(out, facecolor=fig.get_facecolor(), pad_inches=0)
        hidden = int(np.count_nonzero(far_side))
        drawn = int(np.count_nonzero(surface))
        print(f"{out}: tau={tau:.2f}s snapshot={snap_i:04d} t={snap_t / 3600.0:.4f} hr segment={segment} surface_drawn={drawn} far_side_hidden={hidden}")

    plt.close(fig)


if __name__ == "__main__":
    main()
