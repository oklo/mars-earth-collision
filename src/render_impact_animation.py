#!/usr/bin/env python3
"""Render a labelled particle animation from SWIFT snapshots."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import h5py
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


EARTH_OCEAN = np.array([0.025, 0.20, 0.55], dtype=np.float32)
EARTH_LAND_GREEN = np.array([0.18, 0.48, 0.20], dtype=np.float32)
EARTH_LAND_DRY = np.array([0.58, 0.44, 0.24], dtype=np.float32)
EARTH_LAND_BOREAL = np.array([0.10, 0.34, 0.20], dtype=np.float32)
EARTH_ICE = np.array([0.80, 0.86, 0.82], dtype=np.float32)
MARS_SURFACE = np.array([0.70, 0.36, 0.20], dtype=np.float32)
MARS_DARK = np.array([0.28, 0.19, 0.15], dtype=np.float32)
MARS_DUST = np.array([0.82, 0.53, 0.31], dtype=np.float32)
MARS_FROST = np.array([0.78, 0.72, 0.62], dtype=np.float32)
BODY_BASE = np.array([0.075, 0.085, 0.105], dtype=np.float32)
G_INTERNAL = 6.67430e-5
EARTH_SIDEREAL_DAY_SECONDS = 86164.09056


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--snapshot-dir", type=Path, required=True)
    p.add_argument("--basename", required=True)
    p.add_argument("--labels", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--duration", type=float, default=30.0)
    p.add_argument("--fps", type=int, default=24)
    p.add_argument("--width", type=int, default=1920)
    p.add_argument("--height", type=int, default=1080)
    p.add_argument("--frames-dir", type=Path, default=None)
    p.add_argument("--keep-frames", action="store_true")
    p.add_argument("--trail-alpha", type=float, default=0.055)
    p.add_argument("--marker-scale", type=float, default=0.72, help="Multiplier for auto-scaled particle marker sizes.")
    p.add_argument("--surface-size", type=float, default=None, help="Override visible-surface marker area in points^2.")
    p.add_argument("--interior-size", type=float, default=None, help="Override dim body-base marker area in points^2.")
    p.add_argument(
        "--surface-layer",
        choices=["front", "all"],
        default="front",
        help="Draw all labelled surface particles, or only the observer-facing surface layer.",
    )
    p.add_argument(
        "--front-depth-fraction",
        type=float,
        default=0.06,
        help="Include this fraction of a body radius behind the center plane to avoid a hard limb cut.",
    )
    p.add_argument(
        "--view-vector",
        default="0,0,1",
        help="Observer-facing depth axis, comma-separated; 0,0,1 preserves the original x-y view.",
    )
    p.add_argument(
        "--align-final-bodies-horizontal",
        action="store_true",
        help="For fixed-camera renders, rotate the inertial screen axes so final Earth-Mars separation is horizontal.",
    )
    p.add_argument(
        "--camera-mode",
        choices=["fixed", "geosync-impact-longitude"],
        default="fixed",
        help="Use a fixed orthographic view or integrate a geosynchronous test-particle camera.",
    )
    p.add_argument("--camera-softening", type=float, default=0.75, help="Softening length for test camera gravity.")
    p.add_argument("--earth-spin-period-hours", type=float, default=23.9344696)
    p.add_argument("--camera-padding", type=float, default=0.12, help="Projected bounds padding fraction.")
    p.add_argument(
        "--bounds-mode",
        choices=["global", "final-bodies"],
        default="global",
        help="Frame all particles over the full run, or tightly frame robust Earth/Mars extents in the final snapshot.",
    )
    p.add_argument(
        "--bounds-quantile",
        type=float,
        default=0.997,
        help="Central per-body projected quantile used with --bounds-mode final-bodies.",
    )
    p.add_argument("--title-color", default="white")
    p.add_argument("--clock-color", default="#d8dde8")
    p.add_argument("--title-fontsize", type=float, default=18.0)
    p.add_argument("--clock-fontsize", type=float, default=12.0)
    return p.parse_args()


def attr_scalar(value):
    return float(np.asarray(value).reshape(-1)[0])


def snapshot_paths(snapshot_dir: Path, basename: str) -> list[Path]:
    paths = sorted(snapshot_dir.glob(f"{basename}_*.hdf5"))
    if len(paths) < 2:
        raise SystemExit(f"Need at least two snapshots matching {snapshot_dir}/{basename}_*.hdf5")
    return paths


def read_snapshot_ids(path: Path) -> np.ndarray:
    with h5py.File(path, "r") as f:
        return np.asarray(f["PartType0/ParticleIDs"], dtype=np.uint64)


def read_snapshot(path: Path, keep_ids: np.ndarray | None = None):
    with h5py.File(path, "r") as f:
        g = f["PartType0"]
        coords = np.asarray(g["Coordinates"], dtype=np.float32)
        ids = np.asarray(g["ParticleIDs"], dtype=np.uint64)
        masses = np.asarray(g["Masses"], dtype=np.float32) if "Masses" in g else np.ones(len(ids), dtype=np.float32)
        box = np.asarray(f["Header"].attrs["BoxSize"], dtype=np.float32).reshape(-1)
        if len(box) == 1:
            box = np.repeat(box[0], 3).astype(np.float32)
        time = attr_scalar(f["Header"].attrs["Time"])
    coords = coords - 0.5 * box
    if keep_ids is not None:
        order = np.argsort(ids)
        positions = np.searchsorted(ids[order], keep_ids)
        if np.any(positions >= len(ids)) or not np.array_equal(ids[order][positions], keep_ids):
            raise SystemExit(f"Snapshot {path} does not contain all selected persistent ParticleIDs")
        reorder = order[positions]
        ids = ids[reorder]
        coords = coords[reorder]
        masses = masses[reorder]
    return time, coords, ids, masses


def load_labels(path: Path):
    with h5py.File(path, "r") as f:
        ids = np.asarray(f["ParticleIDs"], dtype=np.uint64)
        body_id = np.asarray(f["BodyID"], dtype=np.uint8)
        classes = np.asarray(f["SurfaceClass"], dtype=np.uint8)
        colors = np.asarray(f["ColorRGB"], dtype=np.float32)
        lon = np.asarray(f["LongitudeDeg"], dtype=np.float32) if "LongitudeDeg" in f else np.full(len(ids), np.nan, dtype=np.float32)
        lat = np.asarray(f["LatitudeDeg"], dtype=np.float32) if "LatitudeDeg" in f else np.full(len(ids), np.nan, dtype=np.float32)
    return {int(pid): i for i, pid in enumerate(ids)}, body_id, classes, colors, lon, lat


def order_by_ids(
    ids: np.ndarray,
    id_to_label_idx: dict[int, int],
    body_id: np.ndarray,
    classes: np.ndarray,
    colors: np.ndarray,
    lon: np.ndarray,
    lat: np.ndarray,
):
    idx = np.array([id_to_label_idx[int(pid)] for pid in ids], dtype=np.int64)
    return body_id[idx], classes[idx], colors[idx], lon[idx], lat[idx]


def parse_vector(text: str) -> np.ndarray:
    values = np.array([float(part.strip()) for part in text.split(",")], dtype=np.float64)
    if values.shape != (3,) or not np.all(np.isfinite(values)):
        raise SystemExit("--view-vector must contain three finite comma-separated numbers")
    norm = np.linalg.norm(values)
    if norm == 0:
        raise SystemExit("--view-vector must be non-zero")
    return (values / norm).astype(np.float32)


def view_basis(view_vector: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    depth_axis = view_vector / np.linalg.norm(view_vector)
    if abs(float(np.dot(depth_axis, np.array([0, 0, 1], dtype=np.float32)))) < 0.92:
        up_hint = np.array([0, 0, 1], dtype=np.float32)
    else:
        up_hint = np.array([0, 1, 0], dtype=np.float32)
    right = np.cross(up_hint, depth_axis)
    right /= np.linalg.norm(right)
    up = np.cross(depth_axis, right)
    up /= np.linalg.norm(up)
    return right.astype(np.float32), up.astype(np.float32), depth_axis.astype(np.float32)


def rotate_basis_in_screen(
    basis: tuple[np.ndarray, np.ndarray, np.ndarray],
    theta: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    right, up, depth_axis = basis
    c = float(np.cos(theta))
    s = float(np.sin(theta))
    return (
        (c * right + s * up).astype(np.float32),
        (-s * right + c * up).astype(np.float32),
        depth_axis,
    )


def project(xyz: np.ndarray, basis: tuple[np.ndarray, np.ndarray, np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
    right, up, depth_axis = basis
    x = xyz @ right
    y = xyz @ up
    depth = xyz @ depth_axis
    return np.column_stack((x, y)).astype(np.float32), depth.astype(np.float32)


def camera_basis(camera: np.ndarray, target: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    observer_axis = camera - target
    observer_axis /= np.linalg.norm(observer_axis)
    if abs(float(np.dot(observer_axis, np.array([0, 0, 1], dtype=np.float32)))) < 0.92:
        up_hint = np.array([0, 0, 1], dtype=np.float32)
    else:
        up_hint = np.array([0, 1, 0], dtype=np.float32)
    right = np.cross(up_hint, observer_axis)
    right /= np.linalg.norm(right)
    up = np.cross(observer_axis, right)
    up /= np.linalg.norm(up)
    return right.astype(np.float32), up.astype(np.float32), observer_axis.astype(np.float32)


def project_from_camera(
    xyz: np.ndarray,
    camera: np.ndarray,
    target: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    basis = camera_basis(camera.astype(np.float32), target.astype(np.float32))
    return project((xyz - camera).astype(np.float32), basis)


def center_of_mass(xyz: np.ndarray, masses: np.ndarray, mask: np.ndarray | None = None) -> np.ndarray:
    if mask is None:
        m = masses.astype(np.float64)
        pts = xyz.astype(np.float64)
    else:
        m = masses[mask].astype(np.float64)
        pts = xyz[mask].astype(np.float64)
    return (pts * m[:, None]).sum(axis=0) / m.sum()


def acceleration_at_camera(camera: np.ndarray, xyz: np.ndarray, masses: np.ndarray, softening: float) -> np.ndarray:
    delta = xyz.astype(np.float64) - camera[None, :]
    r2 = np.einsum("ij,ij->i", delta, delta) + softening * softening
    inv_r3 = 1.0 / (r2 * np.sqrt(r2))
    return G_INTERNAL * np.sum(delta * (masses.astype(np.float64) * inv_r3)[:, None], axis=0)


def integrate_geosync_camera(
    times: list[float],
    positions: list[np.ndarray],
    masses: np.ndarray,
    body_id: np.ndarray,
    spin_period_hours: float,
    softening: float,
) -> tuple[np.ndarray, np.ndarray]:
    earth_mask = body_id == 1
    mars_mask = body_id == 2
    earth0 = center_of_mass(positions[0], masses, earth_mask)
    mars0 = center_of_mass(positions[0], masses, mars_mask)
    system_targets = np.array([center_of_mass(xyz, masses) for xyz in positions], dtype=np.float64)

    if len(times) < 2:
        raise SystemExit("Need at least two snapshots to initialize geosynchronous camera velocity.")
    earth1 = center_of_mass(positions[1], masses, earth_mask)
    earth_v0 = (earth1 - earth0) / (times[1] - times[0])

    impact_dir = mars0 - earth0
    impact_dir[2] = 0.0
    if np.linalg.norm(impact_dir) == 0:
        raise SystemExit("Cannot infer impact longitude: initial Earth-Mars xy separation is zero.")
    impact_dir /= np.linalg.norm(impact_dir)

    earth_mass = masses[earth_mask].astype(np.float64).sum()
    omega = 2.0 * np.pi / (spin_period_hours * 3600.0)
    r_geo = (G_INTERNAL * earth_mass / (omega * omega)) ** (1.0 / 3.0)
    rel0 = r_geo * impact_dir
    camera = earth0 + rel0
    velocity = earth_v0 + np.cross(np.array([0.0, 0.0, omega]), rel0)

    cameras = [camera.copy()]
    for i in range(len(times) - 1):
        dt = times[i + 1] - times[i]
        a0 = acceleration_at_camera(camera, positions[i], masses, softening)
        pred = camera + velocity * dt + 0.5 * a0 * dt * dt
        a1 = acceleration_at_camera(pred, positions[i + 1], masses, softening)
        velocity = velocity + 0.5 * (a0 + a1) * dt
        camera = pred
        cameras.append(camera.copy())

    cameras = np.array(cameras, dtype=np.float64)
    mars_distance = np.linalg.norm(cameras[0] - mars0)
    mars_radius = np.quantile(np.linalg.norm(positions[0][mars_mask] - mars0, axis=1), 0.995)
    print(
        "Geosync camera: "
        f"r_geo={r_geo:.3f}, initial Mars-center distance={mars_distance:.3f}, "
        f"Mars r99.5={mars_radius:.3f}"
    )
    return cameras, system_targets


def smooth_noise(lon: np.ndarray, lat: np.ndarray) -> np.ndarray:
    lon_r = np.radians(np.nan_to_num(lon, nan=0.0))
    lat_r = np.radians(np.nan_to_num(lat, nan=0.0))
    n = (
        0.45 * np.sin(2.7 * lon_r + 1.3 * np.sin(lat_r))
        + 0.30 * np.sin(5.1 * lon_r - 2.0 * lat_r)
        + 0.25 * np.cos(3.7 * lon_r + 4.2 * lat_r)
    )
    return np.clip(0.5 + 0.5 * n, 0.0, 1.0).astype(np.float32)


def mars_initial_lonlat(xyz0: np.ndarray, body_id: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    lon = np.full(len(body_id), np.nan, dtype=np.float32)
    lat = np.full(len(body_id), np.nan, dtype=np.float32)
    mars = body_id == 2
    if not np.any(mars):
        return lon, lat
    local = xyz0[mars] - np.median(xyz0[mars], axis=0)
    r = np.linalg.norm(local, axis=1)
    safe = r > 0
    x, y, z = local[safe].T
    mars_idx = np.flatnonzero(mars)[safe]
    lon[mars_idx] = np.degrees(np.arctan2(y, x)).astype(np.float32)
    lat[mars_idx] = np.degrees(np.arcsin(np.clip(z / r[safe], -1.0, 1.0))).astype(np.float32)
    return lon, lat


def realistic_surface_colors(
    classes: np.ndarray,
    source_colors: np.ndarray,
    lon: np.ndarray,
    lat: np.ndarray,
    mars_lon: np.ndarray | None = None,
    mars_lat: np.ndarray | None = None,
) -> np.ndarray:
    colors = np.clip(source_colors, 0.0, 1.0).astype(np.float32)
    noise = smooth_noise(lon, lat)
    abs_lat = np.abs(np.nan_to_num(lat, nan=0.0)).astype(np.float32)

    ocean = classes == 1
    if np.any(ocean):
        deep = EARTH_OCEAN[None, :] * (0.88 + 0.12 * noise[ocean, None])
        polar = np.clip((abs_lat[ocean] - 55.0) / 25.0, 0.0, 1.0)[:, None]
        colors[ocean] = (1.0 - 0.18 * polar) * deep + 0.18 * polar * np.array([0.25, 0.45, 0.70], dtype=np.float32)

    land = classes == 2
    if np.any(land):
        dry_weight = np.clip((abs_lat[land] - 12.0) / 25.0, 0.0, 1.0) * np.clip(noise[land] * 0.9, 0.0, 0.75)
        boreal_weight = np.clip((abs_lat[land] - 48.0) / 28.0, 0.0, 0.65)
        land_color = (1.0 - dry_weight)[:, None] * EARTH_LAND_GREEN + dry_weight[:, None] * EARTH_LAND_DRY
        land_color = (1.0 - boreal_weight)[:, None] * land_color + boreal_weight[:, None] * EARTH_LAND_BOREAL
        colors[land] = np.clip(land_color * (0.92 + 0.12 * noise[land, None]), 0.0, 1.0)

    mars = classes == 3
    if np.any(mars):
        mlon = lon if mars_lon is None else mars_lon
        mlat = lat if mars_lat is None else mars_lat
        mars_noise = smooth_noise(mlon, mlat)
        lon_r = np.radians(np.nan_to_num(mlon[mars], nan=0.0))
        lat_v = np.nan_to_num(mlat[mars], nan=0.0).astype(np.float32)
        lat_r = np.radians(lat_v)

        # A schematic Mars albedo texture: bright Tharsis/Arabia-like dust,
        # dark Syrtis/Sinai/Sirenum-like basaltic provinces, and polar frost.
        bright = (
            0.40 * np.exp(-((np.mod(np.degrees(lon_r) - 250.0 + 180.0, 360.0) - 180.0) / 42.0) ** 2 - ((lat_v - 4.0) / 26.0) ** 2)
            + 0.35 * np.exp(-((np.mod(np.degrees(lon_r) - 25.0 + 180.0, 360.0) - 180.0) / 56.0) ** 2 - ((lat_v - 18.0) / 24.0) ** 2)
        )
        dark = (
            0.65 * np.exp(-((np.mod(np.degrees(lon_r) - 295.0 + 180.0, 360.0) - 180.0) / 34.0) ** 2 - ((lat_v + 12.0) / 18.0) ** 2)
            + 0.50 * np.exp(-((np.mod(np.degrees(lon_r) - 150.0 + 180.0, 360.0) - 180.0) / 55.0) ** 2 - ((lat_v + 25.0) / 20.0) ** 2)
            + 0.35 * np.exp(-((np.mod(np.degrees(lon_r) - 65.0 + 180.0, 360.0) - 180.0) / 45.0) ** 2 - ((lat_v - 5.0) / 18.0) ** 2)
            + 0.18 * (np.cos(2.0 * lon_r - 1.3 * lat_r) > 0.72)
        )
        dark = np.clip(dark * (0.78 + 0.32 * mars_noise[mars]), 0.0, 0.95)
        bright = np.clip(bright * (0.72 + 0.42 * mars_noise[mars]), 0.0, 0.70)
        frost = np.clip((np.abs(lat_v) - 58.0) / 24.0, 0.0, 1.0) * (0.38 + 0.32 * mars_noise[mars])

        dusty = MARS_SURFACE[None, :] * (0.90 + 0.13 * mars_noise[mars, None])
        mars_color = (1.0 - bright)[:, None] * dusty + bright[:, None] * MARS_DUST
        mars_color = (1.0 - dark)[:, None] * mars_color + dark[:, None] * MARS_DARK
        mars_color = (1.0 - 0.42 * frost)[:, None] * mars_color + (0.42 * frost)[:, None] * MARS_FROST
        colors[mars] = np.clip(mars_color, 0.0, 1.0)

    return colors


def visible_surface_mask(
    classes: np.ndarray,
    body_id: np.ndarray,
    depth: np.ndarray,
    args: argparse.Namespace,
) -> np.ndarray:
    surface = classes > 0
    if args.surface_layer == "all":
        return surface

    visible = np.zeros_like(surface)
    for body in (1, 2):
        body_mask = body_id == body
        surf_body = surface & body_mask
        if not np.any(surf_body):
            continue
        center = float(np.median(depth[body_mask]))
        radius = float(np.quantile(np.abs(depth[body_mask] - center), 0.995))
        visible |= surf_body & (depth >= center - args.front_depth_fraction * radius)
    return visible


def auto_sizes(n_particles: int, marker_scale: float, surface_size: float | None, interior_size: float | None) -> tuple[float, float]:
    resolution_scale = np.sqrt(23749.0 / float(max(n_particles, 1)))
    surface = 4.2 * resolution_scale * marker_scale if surface_size is None else surface_size
    interior = 1.15 * resolution_scale * marker_scale if interior_size is None else interior_size
    return float(np.clip(surface, 0.55, 4.2)), float(np.clip(interior, 0.18, 1.5))


def aspect_matched_limits(
    xmin: float,
    xmax: float,
    ymin: float,
    ymax: float,
    aspect: float,
    padding_fraction: float,
) -> tuple[tuple[float, float], tuple[float, float]]:
    xmid = 0.5 * (xmin + xmax)
    ymid = 0.5 * (ymin + ymax)
    xspan = max(float(xmax - xmin), 1e-6)
    yspan = max(float(ymax - ymin), 1e-6)
    xspan *= 1.0 + 2.0 * padding_fraction
    yspan *= 1.0 + 2.0 * padding_fraction
    if xspan / yspan < aspect:
        xspan = yspan * aspect
    else:
        yspan = xspan / aspect
    return (xmid - 0.5 * xspan, xmid + 0.5 * xspan), (ymid - 0.5 * yspan, ymid + 0.5 * yspan)


def final_body_limits(
    final_xy: np.ndarray,
    body_id: np.ndarray,
    aspect: float,
    quantile: float,
    padding_fraction: float,
) -> tuple[tuple[float, float], tuple[float, float]]:
    q = float(np.clip(quantile, 0.80, 0.9999))
    lo = 0.5 * (1.0 - q)
    hi = 1.0 - lo
    boxes = []
    for body in (1, 2):
        xy = final_xy[body_id == body]
        if len(xy) == 0:
            continue
        boxes.append(
            (
                float(np.quantile(xy[:, 0], lo)),
                float(np.quantile(xy[:, 0], hi)),
                float(np.quantile(xy[:, 1], lo)),
                float(np.quantile(xy[:, 1], hi)),
            )
        )
    if not boxes:
        xmin, ymin = np.min(final_xy, axis=0)
        xmax, ymax = np.max(final_xy, axis=0)
    else:
        xmin = min(box[0] for box in boxes)
        xmax = max(box[1] for box in boxes)
        ymin = min(box[2] for box in boxes)
        ymax = max(box[3] for box in boxes)
    return aspect_matched_limits(xmin, xmax, ymin, ymax, aspect, padding_fraction)


def main() -> None:
    args = parse_args()
    paths = snapshot_paths(args.snapshot_dir, args.basename)
    id_to_label_idx, label_body_id, label_classes, label_colors, label_lon, label_lat = load_labels(args.labels)
    basis = view_basis(parse_vector(args.view_vector))

    common_ids = read_snapshot_ids(paths[0])
    initial_count = len(common_ids)
    for path in paths[1:]:
        ids = read_snapshot_ids(path)
        common_ids = common_ids[np.isin(common_ids, ids, assume_unique=False)]
    if len(common_ids) == 0:
        raise SystemExit("No persistent ParticleIDs found across selected snapshots")
    if len(common_ids) < initial_count:
        print(
            f"Using {len(common_ids)} persistent ParticleIDs across {len(paths)} snapshots "
            f"({initial_count - len(common_ids)} particles dropped)."
        )

    times = []
    positions = []
    masses_ref = None
    ids_ref = common_ids
    for path in paths:
        t, xyz, ids, masses = read_snapshot(path, ids_ref)
        if masses_ref is None or not np.array_equal(masses_ref, masses):
            masses_ref = masses
        times.append(t)
        positions.append(xyz.astype(np.float32))

    body_id, classes, source_colors, lon, lat = order_by_ids(
        ids_ref, id_to_label_idx, label_body_id, label_classes, label_colors, label_lon, label_lat
    )
    mars_lon, mars_lat = mars_initial_lonlat(positions[0], body_id)
    colors = realistic_surface_colors(classes, source_colors, lon, lat, mars_lon, mars_lat)
    surface_size, interior_size = auto_sizes(len(ids_ref), args.marker_scale, args.surface_size, args.interior_size)

    if args.camera_mode == "fixed" and args.align_final_bodies_horizontal:
        final_xy0, _ = project(positions[-1], basis)
        earth_center = np.median(final_xy0[body_id == 1], axis=0)
        mars_center = np.median(final_xy0[body_id == 2], axis=0)
        delta = mars_center - earth_center
        if np.linalg.norm(delta) > 0:
            basis = rotate_basis_in_screen(basis, float(np.arctan2(delta[1], delta[0])))

    if args.camera_mode == "geosync-impact-longitude":
        cameras, targets = integrate_geosync_camera(
            times, positions, masses_ref, body_id, args.earth_spin_period_hours, args.camera_softening
        )
        projected_bounds = [project_from_camera(xyz, cam, target)[0] for xyz, cam, target in zip(positions, cameras, targets)]
    else:
        cameras = None
        targets = None
        projected_bounds = [project(xyz, basis)[0] for xyz in positions]
    aspect = args.width / args.height
    if args.bounds_mode == "final-bodies":
        xlim, ylim = final_body_limits(
            projected_bounds[-1], body_id, aspect, args.bounds_quantile, args.camera_padding
        )
    else:
        all_xy = np.concatenate(projected_bounds, axis=0)
        xmin, ymin = np.min(all_xy, axis=0)
        xmax, ymax = np.max(all_xy, axis=0)
        xlim, ylim = aspect_matched_limits(
            float(xmin), float(xmax), float(ymin), float(ymax), aspect, args.camera_padding
        )

    n_frames = int(round(args.duration * args.fps))
    frames_dir = args.frames_dir or Path(f"frames_{args.out.stem}")
    frames_dir.mkdir(parents=True, exist_ok=True)

    fig_w = args.width / 160
    fig_h = args.height / 160
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=160)
    fig.patch.set_facecolor("#03050a")
    ax.set_facecolor("#03050a")
    fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
    ax.set_position([0, 0, 1, 1])
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.axis("off")
    ax.text(
        0.025,
        0.955,
        "Mars-Earth grazing collision",
        transform=ax.transAxes,
        color=args.title_color,
        fontsize=args.title_fontsize,
        ha="left",
        va="top",
    )
    clock = ax.text(
        0.025,
        0.905,
        "",
        transform=ax.transAxes,
        color=args.clock_color,
        fontsize=args.clock_fontsize,
        ha="left",
        va="top",
    )

    if args.camera_mode == "geosync-impact-longitude":
        xy0, depth0 = project_from_camera(positions[0], cameras[0], targets[0])
    else:
        xy0, depth0 = project(positions[0], basis)
    base_colors = np.tile(BODY_BASE, (len(ids_ref), 1))
    base_colors[body_id == 2] = np.array([0.11, 0.075, 0.055], dtype=np.float32)
    scat_base = ax.scatter(xy0[:, 0], xy0[:, 1], s=interior_size, c=base_colors, alpha=0.36, linewidths=0)
    initial_surface = visible_surface_mask(classes, body_id, depth0, args)
    initial_order = np.argsort(depth0[initial_surface])
    surf_xy0 = xy0[initial_surface][initial_order]
    surf_colors0 = colors[initial_surface][initial_order]
    scat_trail = ax.scatter(surf_xy0[:, 0], surf_xy0[:, 1], s=surface_size * 0.55, c=surf_colors0, alpha=args.trail_alpha, linewidths=0)
    scat_surface = ax.scatter(surf_xy0[:, 0], surf_xy0[:, 1], s=surface_size, c=surf_colors0, alpha=0.98, linewidths=0)

    t0 = times[0]
    t1 = times[-1]
    t_samples = np.linspace(t0, t1, n_frames)
    j = 0
    prev_surf_xy = surf_xy0
    prev_surf_colors = surf_colors0
    for frame_idx, t in enumerate(t_samples):
        while j < len(times) - 2 and t > times[j + 1]:
            j += 1
        dt = times[j + 1] - times[j]
        f = 0.0 if dt == 0 else (t - times[j]) / dt
        xyz = (1.0 - f) * positions[j] + f * positions[j + 1]
        if args.camera_mode == "geosync-impact-longitude":
            camera = (1.0 - f) * cameras[j] + f * cameras[j + 1]
            target = (1.0 - f) * targets[j] + f * targets[j + 1]
            xy, depth = project_from_camera(xyz, camera, target)
        else:
            xy, depth = project(xyz, basis)
        scat_base.set_offsets(xy)

        surface = visible_surface_mask(classes, body_id, depth, args)
        order = np.argsort(depth[surface])
        surf_xy = xy[surface][order]
        surf_colors = colors[surface][order]
        scat_surface.set_offsets(surf_xy)
        scat_surface.set_facecolors(surf_colors)
        scat_trail.set_offsets(prev_surf_xy)
        scat_trail.set_facecolors(prev_surf_colors)
        clock.set_text(f"t = {(t - t0) / 3600.0:5.2f} hr")
        frame_path = frames_dir / f"frame_{frame_idx:04d}.png"
        fig.savefig(frame_path, facecolor=fig.get_facecolor(), pad_inches=0)
        if frame_idx % max(1, args.fps * 5) == 0:
            print(f"Rendered frame {frame_idx + 1}/{n_frames}")
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
