#!/usr/bin/env python3
"""Render a storyboarded inertial-frame Mars-Earth grazing-collision animation."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import h5py
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from render_impact_animation import (
    BODY_BASE,
    load_labels,
    mars_initial_lonlat,
    order_by_ids,
    project,
    realistic_surface_colors,
    read_snapshot,
    snapshot_paths,
    visible_surface_mask,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--snapshot-dir", type=Path, required=True)
    p.add_argument("--basename", required=True)
    p.add_argument("--labels", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--duration", type=float, default=60.0)
    p.add_argument("--fps", type=int, default=24)
    p.add_argument("--width", type=int, default=1920)
    p.add_argument("--height", type=int, default=1080)
    p.add_argument("--frames-dir", type=Path, default=None)
    p.add_argument("--keep-frames", action="store_true")
    p.add_argument("--marker-scale", type=float, default=0.72)
    p.add_argument("--trail-alpha", type=float, default=0.045)
    p.add_argument("--contact-time-hours", type=float, default=None)
    return p.parse_args()


def unit(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    if n == 0:
        raise ValueError("zero vector")
    return v / n


def view_basis(view_vector: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    depth_axis = unit(view_vector.astype(np.float64))
    up_hint = np.array([0.0, 0.0, 1.0])
    if abs(float(np.dot(depth_axis, up_hint))) > 0.92:
        up_hint = np.array([0.0, 1.0, 0.0])
    right = unit(np.cross(up_hint, depth_axis))
    up = unit(np.cross(depth_axis, right))
    return right.astype(np.float32), up.astype(np.float32), depth_axis.astype(np.float32)


def center_of_mass(xyz: np.ndarray, masses: np.ndarray, mask: np.ndarray) -> np.ndarray:
    w = masses[mask].astype(np.float64)
    return (xyz[mask].astype(np.float64) * w[:, None]).sum(axis=0) / w.sum()


def interp_array(times: np.ndarray, values: list[np.ndarray], t: float) -> tuple[np.ndarray, int, float]:
    j = int(np.searchsorted(times, t, side="right") - 1)
    j = max(0, min(j, len(times) - 2))
    dt = times[j + 1] - times[j]
    f = 0.0 if dt == 0 else (t - times[j]) / dt
    return (1.0 - f) * values[j] + f * values[j + 1], j, f


def smoothstep(x: float) -> float:
    x = float(np.clip(x, 0.0, 1.0))
    return x * x * (3.0 - 2.0 * x)


def quantile_span(xy: np.ndarray, aspect: float, quantile: float = 0.997, pad: float = 1.18) -> float:
    cx, cy = np.median(xy, axis=0)
    dx = np.quantile(np.abs(xy[:, 0] - cx), quantile) * 2.0 / aspect
    dy = np.quantile(np.abs(xy[:, 1] - cy), quantile) * 2.0
    return float(max(dx, dy) * pad)


def auto_sizes(n_particles: int, marker_scale: float) -> tuple[float, float]:
    resolution_scale = np.sqrt(23749.0 / float(max(n_particles, 1)))
    surface = float(np.clip(4.2 * resolution_scale * marker_scale, 0.55, 4.2))
    interior = float(np.clip(1.15 * resolution_scale * marker_scale, 0.18, 1.5))
    return surface, interior


def load_snapshots(args: argparse.Namespace):
    paths = snapshot_paths(args.snapshot_dir, args.basename)
    id_to_label_idx, label_body_id, label_classes, label_colors, label_lon, label_lat = load_labels(args.labels)

    times: list[float] = []
    positions: list[np.ndarray] = []
    ids_ref = None
    masses_ref = None
    for path in paths:
        t, xyz, ids, masses = read_snapshot(path)
        if ids_ref is None:
            ids_ref = ids
            masses_ref = masses
        elif not np.array_equal(ids_ref, ids):
            current_lookup = {int(pid): i for i, pid in enumerate(ids)}
            reorder = np.array([current_lookup[int(pid)] for pid in ids_ref], dtype=np.int64)
            xyz = xyz[reorder]
            masses = masses[reorder]
        times.append(float(t))
        positions.append(xyz.astype(np.float32))
        masses_ref = masses.astype(np.float32)

    body_id, classes, source_colors, lon, lat = order_by_ids(
        ids_ref, id_to_label_idx, label_body_id, label_classes, label_colors, label_lon, label_lat
    )
    mars_lon, mars_lat = mars_initial_lonlat(positions[0], body_id)
    colors = realistic_surface_colors(classes, source_colors, lon, lat, mars_lon, mars_lat)
    return np.asarray(times), positions, masses_ref, body_id, classes, colors


def body_centers(positions: list[np.ndarray], masses: np.ndarray, body_id: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    earth_mask = body_id == 1
    mars_mask = body_id == 2
    earth = np.array([center_of_mass(xyz, masses, earth_mask) for xyz in positions], dtype=np.float64)
    mars = np.array([center_of_mass(xyz, masses, mars_mask) for xyz in positions], dtype=np.float64)
    system = np.array([center_of_mass(xyz, masses, np.ones(len(body_id), dtype=bool)) for xyz in positions], dtype=np.float64)
    return earth, mars, system


def contact_index(times: np.ndarray, earth: np.ndarray, mars: np.ndarray, requested_hours: float | None) -> int:
    if requested_hours is not None:
        return int(np.argmin(np.abs(times - requested_hours * 3600.0)))
    d = np.linalg.norm(mars - earth, axis=1)
    return int(np.argmin(d))


def storyboard_camera(
    tau: float,
    total_duration: float,
    times: np.ndarray,
    contact_i: int,
    earth: np.ndarray,
    mars: np.ndarray,
    system: np.ndarray,
) -> tuple[float, np.ndarray, np.ndarray, float, str]:
    t0, t1 = float(times[0]), float(times[-1])
    tc = float(times[contact_i])
    base = np.array([14.0, 12.0, 24.0, 10.0], dtype=np.float64)
    edges = np.concatenate(([0.0], np.cumsum(base / base.sum() * total_duration)))

    r_contact = unit(mars[contact_i] - earth[contact_i])
    z = np.array([0.0, 0.0, 1.0])
    side = unit(np.cross(z, r_contact))
    if np.dot(side, np.array([0.0, 1.0, 0.0])) < 0:
        side = -side

    run_view = unit(0.55 * side - 0.45 * r_contact + 0.70 * z)
    fly_end_view = unit(-0.35 * side + 0.75 * r_contact + 0.55 * z)
    evo_view = unit(-0.45 * side + 0.45 * r_contact + 0.77 * z)
    earth_tour_view = unit(0.20 * side - 0.35 * r_contact + 0.92 * z)
    mars_tour_view = unit(-0.35 * side + 0.55 * r_contact + 0.76 * z)
    final_wide_view = unit(-0.55 * side + 0.35 * r_contact + 0.76 * z)

    if tau <= edges[1]:
        s = smoothstep((tau - edges[0]) / (edges[1] - edges[0]))
        t = (1.0 - s) * t0 + s * tc
        target = np.interp(t, times, system[:, 0]), np.interp(t, times, system[:, 1]), np.interp(t, times, system[:, 2])
        return t, run_view, np.asarray(target), 40.0 - 14.0 * s, "run-up"

    if tau <= edges[2]:
        s = smoothstep((tau - edges[1]) / (edges[2] - edges[1]))
        theta = np.radians(-25.0 + 245.0 * s)
        view = unit(np.cos(theta) * run_view + np.sin(theta) * fly_end_view + (0.10 + 0.28 * np.sin(np.pi * s)) * z)
        target = 0.58 * earth[contact_i] + 0.42 * mars[contact_i]
        span = 22.0 - 4.0 * np.sin(np.pi * s)
        return tc, view, target, span, "frozen fly-through"

    if tau <= edges[3]:
        s = smoothstep((tau - edges[2]) / (edges[3] - edges[2]))
        t = (1.0 - s) * tc + s * t1
        sys_target = np.array(
            (
                np.interp(t, times, system[:, 0]),
                np.interp(t, times, system[:, 1]),
                np.interp(t, times, system[:, 2]),
            )
        )
        earth_target = np.array(
            (
                np.interp(t, times, earth[:, 0]),
                np.interp(t, times, earth[:, 1]),
                np.interp(t, times, earth[:, 2]),
            )
        )
        mars_target = np.array(
            (
                np.interp(t, times, mars[:, 0]),
                np.interp(t, times, mars[:, 1]),
                np.interp(t, times, mars[:, 2]),
            )
        )
        pair_target = 0.5 * (earth_target + mars_target)
        target = (1.0 - 0.75 * s) * sys_target + (0.75 * s) * pair_target
        view = unit((1.0 - 0.35 * s) * fly_end_view + (0.35 + 0.35 * s) * evo_view)
        return t, view, np.asarray(target), 52.0 + 42.0 * s, "evolution"

    s = smoothstep((tau - edges[3]) / (edges[4] - edges[3]))
    t = t1
    final_pair_target = 0.5 * (earth[-1] + mars[-1])
    if s < 0.30:
        q = smoothstep(s / 0.30)
        target = (1.0 - q) * system[-1] + q * earth[-1]
        view = unit((1.0 - q) * evo_view + q * earth_tour_view)
        span = (1.0 - q) * 50.0 + q * 17.0
    elif s < 0.60:
        q = smoothstep((s - 0.30) / 0.30)
        target = (1.0 - q) * earth[-1] + q * mars[-1]
        view = unit((1.0 - q) * earth_tour_view + q * mars_tour_view)
        span = (1.0 - q) * 17.0 + q * 18.0
    else:
        q = smoothstep((s - 0.60) / 0.40)
        target = (1.0 - q) * mars[-1] + q * final_pair_target
        view = unit((1.0 - q) * mars_tour_view + q * final_wide_view)
        span = (1.0 - q) * 18.0 + q * 82.0
    return t, view, target, span, "final tour"


def main() -> None:
    args = parse_args()
    times, positions, masses, body_id, classes, colors = load_snapshots(args)
    earth, mars, system = body_centers(positions, masses, body_id)
    contact_i = contact_index(times, earth, mars, args.contact_time_hours)
    print(f"Storyboard contact snapshot={contact_i:04d} t={times[contact_i] / 3600.0:.4f} hr")

    n_frames = int(round(args.duration * args.fps))
    frames_dir = args.frames_dir or Path(f"frames_{args.out.stem}")
    frames_dir.mkdir(parents=True, exist_ok=True)
    surface_size, interior_size = auto_sizes(len(body_id), args.marker_scale)
    aspect = args.width / args.height

    fig, ax = plt.subplots(figsize=(args.width / 160, args.height / 160), dpi=160)
    fig.patch.set_facecolor("#03050a")
    ax.set_facecolor("#03050a")
    fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
    ax.set_position([0, 0, 1, 1])
    ax.set_aspect("equal", adjustable="box")
    ax.axis("off")
    title = ax.text(0.025, 0.955, "Mars-Earth grazing collision", transform=ax.transAxes, color="white", fontsize=18, ha="left", va="top")
    clock = ax.text(0.025, 0.905, "", transform=ax.transAxes, color="#d8dde8", fontsize=12, ha="left", va="top")

    base_colors = np.tile(BODY_BASE, (len(body_id), 1))
    base_colors[body_id == 2] = np.array([0.12, 0.075, 0.055], dtype=np.float32)

    prev_surf_xy = None
    prev_surf_colors = None
    scat_base = None
    scat_trail = None
    scat_surface = None
    for frame_idx in range(n_frames):
        tau = args.duration * frame_idx / max(1, n_frames - 1)
        t, view, target, span, segment = storyboard_camera(tau, args.duration, times, contact_i, earth, mars, system)
        xyz, _, _ = interp_array(times, positions, t)
        basis = view_basis(view)
        xy, depth = project((xyz - target).astype(np.float32), basis)

        yhalf = 0.5 * span
        xhalf = yhalf * aspect
        ax.set_xlim(-xhalf, xhalf)
        ax.set_ylim(-yhalf, yhalf)

        if scat_base is None:
            scat_base = ax.scatter(xy[:, 0], xy[:, 1], s=interior_size, c=base_colors, alpha=0.30, linewidths=0)
        else:
            scat_base.set_offsets(xy)

        surface = visible_surface_mask(classes, body_id, depth, argparse.Namespace(surface_layer="front", front_depth_fraction=0.08))
        order = np.argsort(depth[surface])
        surf_xy = xy[surface][order]
        surf_colors = colors[surface][order]
        if prev_surf_xy is None:
            prev_surf_xy = surf_xy
            prev_surf_colors = surf_colors
        if scat_trail is None:
            scat_trail = ax.scatter(prev_surf_xy[:, 0], prev_surf_xy[:, 1], s=surface_size * 0.50, c=prev_surf_colors, alpha=args.trail_alpha, linewidths=0)
            scat_surface = ax.scatter(surf_xy[:, 0], surf_xy[:, 1], s=surface_size, c=surf_colors, alpha=0.98, linewidths=0)
        else:
            scat_trail.set_offsets(prev_surf_xy)
            scat_trail.set_facecolors(prev_surf_colors)
            scat_surface.set_offsets(surf_xy)
            scat_surface.set_facecolors(surf_colors)

        title.set_text("Mars-Earth grazing collision")
        clock.set_text(f"t = {(t - times[0]) / 3600.0:5.2f} hr")
        fig.savefig(frames_dir / f"frame_{frame_idx:04d}.png", facecolor=fig.get_facecolor(), pad_inches=0)
        if frame_idx % max(1, args.fps * 5) == 0:
            print(f"Rendered frame {frame_idx + 1}/{n_frames} ({segment})")
        prev_surf_xy = surf_xy
        prev_surf_colors = surf_colors

    plt.close(fig)
    cmd = [
        "ffmpeg", "-y", "-framerate", str(args.fps),
        "-i", str(frames_dir / "frame_%04d.png"),
        "-t", str(args.duration),
        "-vf", f"scale={args.width}:{args.height}:force_original_aspect_ratio=decrease,pad={args.width}:{args.height}:(ow-iw)/2:(oh-ih)/2,format=yuv420p",
        "-c:v", "libx264", "-preset", "slow", "-crf", "18",
        str(args.out),
    ]
    subprocess.run(cmd, check=True)
    print(f"Wrote {args.out}")
    if not args.keep_frames:
        for frame in frames_dir.glob("frame_*.png"):
            frame.unlink()
        try:
            frames_dir.rmdir()
        except OSError:
            pass


if __name__ == "__main__":
    main()
