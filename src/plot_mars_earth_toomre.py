#!/usr/bin/env python3
"""Render a Toomre-style Mars--Earth approach diagram at a selected epoch.

The orbital state is a Newtonian two-body back-propagation of the settled
200k-particle SPH initial condition.  The central encounter epoch is the
measured maximum-coupling time, 7800 s after the SPH initial condition.
Planet centres and orbital tracks are plotted to scale by default; the
optional display-scale argument can enlarge the globes for alternate layouts.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import h5py
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
import numpy as np
import shapefile
from scipy.integrate import solve_ivp


# oklo.org uses the macOS system-sans stack.  Helvetica Neue is the first
# explicitly named family in that stack that Matplotlib can address directly.
plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Helvetica Neue"],
        "mathtext.fontset": "custom",
        "mathtext.rm": "Helvetica Neue",
        "mathtext.it": "Helvetica Neue:italic",
        "mathtext.bf": "Helvetica Neue:bold",
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
    }
)


G_SI = 6.67430e-11
CENTRAL_TIME_S = 7800.0
FRAME_T_FROM_CENTRAL_S = -48.0 * 3600.0
EARTH_SPIN_PERIOD_H = 23.9344696
MARS_SPIN_PERIOD_H = 24.623
PLANET_DISPLAY_SCALE = 1.0
MEAN_LUNAR_DISTANCE_KM = 384_400.0
MOON_RADIUS_KM = 1_737.4
MOON_DIAGRAM_PHASE_DEG = 330.0

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_IC = REPO_ROOT / "data" / "mars_earth_grazing_settled_n200000.hdf5"
DEFAULT_LABELS = (
    REPO_ROOT / "data" / "mars_earth_grazing_settled_n200000_labels.hdf5"
)
DEFAULT_CONTINENTS = REPO_ROOT / "data" / "natural_earth" / "ne_110m_land.shp"
DEFAULT_OUT = Path("figures/mars_earth_toomre_tminus48h")

# Approximate footprints from the USGS/IAU Gazetteer of Planetary
# Nomenclature nightly Mars GIS release.  These are region extents, not
# topographic contours.  Longitudes are positive east.
MARS_FEATURES = (
    ("Arabia Terra", 5.7185, 21.2490, -29.6896, 49.4356, -18.0714, 45.3642),
    ("Syrtis Major", 67.1030, 9.2007, 58.8824, 76.6443, -1.3707, 19.4087),
    ("Hellas", 70.5025, -42.4301, 45.5822, 96.1171, -55.4167, -27.8630),
    ("Isidis", 88.3772, 13.9357, 77.6228, 98.9085, 3.1974, 22.5902),
    ("Utopia", 117.5168, 46.7363, 71.8562, 164.8869, 12.9159, 73.1699),
    ("Elysium", 154.7372, 2.9790, 128.2560, 179.1131, -7.7709, 11.4038),
    ("Olympus", 226.1975, 18.6528, 220.7567, 232.1984, 13.4818, 23.6760),
    ("Tharsis", 247.4165, 1.5703, 236.3638, 258.9829, -11.6210, 15.7123),
    ("Valles Marineris", 301.4123, -14.0059, 267.5958, 331.1543, -18.3293, -2.7768),
    ("Argyre", 316.6902, -49.8406, 306.1232, 326.6159, -57.2918, -42.4359),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ic", type=Path, default=DEFAULT_IC)
    parser.add_argument("--labels", type=Path, default=DEFAULT_LABELS)
    parser.add_argument("--continents", type=Path, default=DEFAULT_CONTINENTS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--display-scale", type=float, default=PLANET_DISPLAY_SCALE)
    parser.add_argument(
        "--frame-time-central-h",
        type=float,
        default=FRAME_T_FROM_CENTRAL_S / 3600.0,
        help="Frame time in hours relative to maximum encounter coupling.",
    )
    parser.add_argument(
        "--hide-moon",
        action="store_true",
        help="Omit the diagrammatic Moon and lunar orbit.",
    )
    return parser.parse_args()


def scalar_attr(value: object) -> float:
    return float(np.asarray(value).reshape(-1)[0])


def read_initial_state(ic_path: Path, labels_path: Path) -> dict[str, np.ndarray | float]:
    with h5py.File(labels_path, "r") as labels_file:
        body_id = np.asarray(labels_file["BodyID"])

    with h5py.File(ic_path, "r") as f:
        units = f["Units"].attrs
        unit_l = scalar_attr(units["Unit length in cgs (U_L)"]) * 1.0e-2
        unit_m = scalar_attr(units["Unit mass in cgs (U_M)"]) * 1.0e-3
        unit_t = scalar_attr(units["Unit time in cgs (U_t)"])
        group = f["PartType0"]
        pos = np.asarray(group["Coordinates"], dtype=float) * unit_l
        vel = np.asarray(group["Velocities"], dtype=float) * unit_l / unit_t
        mass = np.asarray(group["Masses"], dtype=float) * unit_m
        earth_radius = scalar_attr(f.attrs["EffectiveEarthRadius_m"])
        mars_radius = scalar_attr(f.attrs["EffectiveMarsRadius_m"])

    if len(body_id) != len(mass):
        raise ValueError("Body-label and IC particle counts differ")

    result: dict[str, np.ndarray | float] = {
        "earth_radius": earth_radius,
        "mars_radius": mars_radius,
    }
    for name, value in (("earth", 1), ("mars", 2)):
        keep = body_id == value
        body_mass = float(np.sum(mass[keep]))
        result[f"{name}_mass"] = body_mass
        result[f"{name}_pos"] = np.sum(pos[keep] * mass[keep, None], axis=0) / body_mass
        result[f"{name}_vel"] = np.sum(vel[keep] * mass[keep, None], axis=0) / body_mass
    return result


def propagate_relative(
    r0: np.ndarray,
    v0: np.ndarray,
    mu: float,
    sample_times_s: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    def rhs(_time: float, state: np.ndarray) -> np.ndarray:
        r = state[:3]
        radius = np.linalg.norm(r)
        return np.r_[state[3:], -mu * r / radius**3]

    backward = sample_times_s[sample_times_s < 0.0]
    forward = sample_times_s[sample_times_s >= 0.0]
    state0 = np.r_[r0, v0]
    output = np.empty((len(sample_times_s), 6), dtype=float)

    if len(backward):
        solution = solve_ivp(
            rhs,
            (0.0, float(np.min(backward))),
            state0,
            rtol=2.0e-12,
            atol=1.0e-5,
            dense_output=True,
            max_step=900.0,
        )
        if not solution.success:
            raise RuntimeError(solution.message)
        output[sample_times_s < 0.0] = solution.sol(backward).T
    if len(forward):
        solution = solve_ivp(
            rhs,
            (0.0, float(np.max(forward))),
            state0,
            rtol=2.0e-12,
            atol=1.0e-5,
            dense_output=True,
            max_step=600.0,
        )
        if not solution.success:
            raise RuntimeError(solution.message)
        output[sample_times_s >= 0.0] = solution.sol(forward).T
    return output[:, :3], output[:, 3:]


def camera_basis(azimuth_deg: float = 110.0, elevation_deg: float = 30.0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    azimuth = np.deg2rad(azimuth_deg)
    elevation = np.deg2rad(elevation_deg)
    view = np.array(
        [np.cos(elevation) * np.cos(azimuth), np.cos(elevation) * np.sin(azimuth), np.sin(elevation)]
    )
    screen_x = np.array([-np.sin(azimuth), np.cos(azimuth), 0.0])
    screen_y = np.cross(view, screen_x)
    return screen_x, screen_y, view


def project(points: np.ndarray, screen_x: np.ndarray, screen_y: np.ndarray) -> np.ndarray:
    points = np.asarray(points)
    return np.column_stack((points @ screen_x, points @ screen_y))


def lon_lat_vectors(lon_deg: np.ndarray, lat_deg: np.ndarray, spin_angle_rad: float) -> np.ndarray:
    lon = np.deg2rad(np.asarray(lon_deg)) + spin_angle_rad
    lat = np.deg2rad(np.asarray(lat_deg))
    cos_lat = np.cos(lat)
    return np.column_stack((cos_lat * np.cos(lon), cos_lat * np.sin(lon), np.sin(lat)))


def visible_runs(points: np.ndarray, visible: np.ndarray) -> list[np.ndarray]:
    runs: list[np.ndarray] = []
    start: int | None = None
    for index, is_visible in enumerate(visible):
        if is_visible and start is None:
            start = index
        if start is not None and (not is_visible or index == len(visible) - 1):
            stop = index + 1 if is_visible else index
            if stop - start >= 2:
                runs.append(points[start:stop])
            start = None
    return runs


def plot_spherical_line(
    ax: plt.Axes,
    lon_deg: np.ndarray,
    lat_deg: np.ndarray,
    center_xy: np.ndarray,
    radius_plot: float,
    spin_angle_rad: float,
    basis: tuple[np.ndarray, np.ndarray, np.ndarray],
    **plot_kwargs: object,
) -> None:
    screen_x, screen_y, view = basis
    normals = lon_lat_vectors(lon_deg, lat_deg, spin_angle_rad)
    xy = center_xy + radius_plot * project(normals, screen_x, screen_y)
    visible = normals @ view >= -2.0e-3
    for run in visible_runs(xy, visible):
        ax.plot(run[:, 0], run[:, 1], **plot_kwargs)


def draw_graticule(
    ax: plt.Axes,
    center_xy: np.ndarray,
    radius_plot: float,
    spin_angle_rad: float,
    basis: tuple[np.ndarray, np.ndarray, np.ndarray],
    color: str,
) -> None:
    dense_lon = np.linspace(-180.0, 180.0, 721)
    dense_lat = np.linspace(-90.0, 90.0, 361)
    for latitude in (-60, 0, 60):
        plot_spherical_line(
            ax,
            dense_lon,
            np.full_like(dense_lon, latitude),
            center_xy,
            radius_plot,
            spin_angle_rad,
            basis,
            color=color,
            lw=0.22 if latitude else 0.34,
            alpha=0.38 if latitude else 0.56,
            zorder=8,
        )
    for longitude in range(-120, 181, 60):
        plot_spherical_line(
            ax,
            np.full_like(dense_lat, longitude),
            dense_lat,
            center_xy,
            radius_plot,
            spin_angle_rad,
            basis,
            color=color,
            lw=0.22 if longitude else 0.34,
            alpha=0.38 if longitude else 0.56,
            zorder=8,
        )


def draw_earth_continents(
    ax: plt.Axes,
    shapefile_path: Path,
    center_xy: np.ndarray,
    radius_plot: float,
    spin_angle_rad: float,
    basis: tuple[np.ndarray, np.ndarray, np.ndarray],
) -> None:
    reader = shapefile.Reader(str(shapefile_path))
    for shape in reader.iterShapes():
        points = np.asarray(shape.points, dtype=float)
        parts = list(shape.parts) + [len(points)]
        for begin, end in zip(parts[:-1], parts[1:]):
            ring = points[begin:end]
            if len(ring) < 2:
                continue
            plot_spherical_line(
                ax,
                ring[:, 0],
                ring[:, 1],
                center_xy,
                radius_plot,
                spin_angle_rad,
                basis,
                color="#0759a5",
                lw=0.30,
                alpha=0.88,
                zorder=10,
            )


def feature_outline(feature: tuple[str, float, float, float, float, float, float]) -> tuple[np.ndarray, np.ndarray]:
    _name, center_lon, center_lat, min_lon, max_lon, min_lat, max_lat = feature
    # Normalize the footprint around its stated centre before constructing a
    # compact oval in lon/lat.  This handles 0/360-degree wrapping.
    def near_center(longitude: float) -> float:
        return center_lon + ((longitude - center_lon + 180.0) % 360.0 - 180.0)

    lon_min = near_center(min_lon)
    lon_max = near_center(max_lon)
    if lon_max < lon_min:
        lon_max += 360.0
    center_for_span = center_lon
    while center_for_span < lon_min:
        center_for_span += 360.0
    while center_for_span > lon_max:
        center_for_span -= 360.0
    half_lon = max(center_for_span - lon_min, lon_max - center_for_span)
    half_lat = max(center_lat - min_lat, max_lat - center_lat)
    angle = np.linspace(0.0, 2.0 * np.pi, 181)
    return center_lon + half_lon * np.cos(angle), center_lat + half_lat * np.sin(angle)


def draw_mars_features(
    ax: plt.Axes,
    center_xy: np.ndarray,
    radius_plot: float,
    spin_angle_rad: float,
    basis: tuple[np.ndarray, np.ndarray, np.ndarray],
) -> None:
    for feature in MARS_FEATURES:
        if feature[0] not in {"Arabia Terra", "Syrtis Major", "Hellas", "Utopia", "Valles Marineris"}:
            continue
        lon, lat = feature_outline(feature)
        plot_spherical_line(
            ax,
            lon,
            lat,
            center_xy,
            radius_plot,
            spin_angle_rad,
            basis,
            color="#9c351f",
            lw=0.30,
            alpha=0.86,
            zorder=10,
        )


def draw_planet(
    ax: plt.Axes,
    center_xy: np.ndarray,
    physical_radius_km: float,
    display_scale: float,
    spin_angle_rad: float,
    basis: tuple[np.ndarray, np.ndarray, np.ndarray],
    kind: str,
    continents: Path,
) -> None:
    radius_plot = physical_radius_km * display_scale
    edge_color = "#074b87" if kind == "earth" else "#8b2e1c"
    fill_color = "#f8fbff" if kind == "earth" else "#fff8f3"
    disk = Circle(center_xy, radius_plot, facecolor=fill_color, edgecolor=edge_color, lw=0.62, zorder=6)
    ax.add_patch(disk)
    draw_graticule(ax, center_xy, radius_plot, spin_angle_rad, basis, edge_color)
    if kind == "earth":
        draw_earth_continents(ax, continents, center_xy, radius_plot, spin_angle_rad, basis)
    else:
        draw_mars_features(ax, center_xy, radius_plot, spin_angle_rad, basis)
    ax.add_patch(Circle(center_xy, radius_plot, facecolor="none", edgecolor=edge_color, lw=0.62, zorder=14))


def orbital_invariants(r: np.ndarray, v: np.ndarray, mu: float) -> tuple[float, float, float]:
    radius = float(np.linalg.norm(r))
    speed2 = float(v @ v)
    energy = 0.5 * speed2 - mu / radius
    angular_momentum = float(np.linalg.norm(np.cross(r, v)))
    eccentricity = float(np.sqrt(1.0 + 2.0 * energy * angular_momentum**2 / mu**2))
    pericenter = angular_momentum**2 / (mu * (1.0 + eccentricity))
    v_infinity = float(np.sqrt(max(0.0, 2.0 * energy)))
    return eccentricity, pericenter, v_infinity


def main() -> None:
    args = parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)

    initial = read_initial_state(args.ic, args.labels)
    earth_mass = float(initial["earth_mass"])
    mars_mass = float(initial["mars_mass"])
    total_mass = earth_mass + mars_mass
    mu = G_SI * total_mass
    earth_fraction = earth_mass / total_mass
    mars_fraction = mars_mass / total_mass
    r0 = np.asarray(initial["mars_pos"]) - np.asarray(initial["earth_pos"])
    v0 = np.asarray(initial["mars_vel"]) - np.asarray(initial["earth_vel"])

    trace_t_central_h = np.linspace(-160.0, 600.0, 6001)
    trace_t_ic_s = trace_t_central_h * 3600.0 + CENTRAL_TIME_S
    relative_pos, relative_vel = propagate_relative(r0, v0, mu, trace_t_ic_s)
    earth_pos = -mars_fraction * relative_pos / 1000.0
    mars_pos = earth_fraction * relative_pos / 1000.0

    frame_t_central_h = float(args.frame_time_central_h)
    frame_t_ic_s = CENTRAL_TIME_S + frame_t_central_h * 3600.0
    frame_r, frame_v = propagate_relative(r0, v0, mu, np.array([frame_t_ic_s]))
    frame_r = frame_r[0]
    frame_v = frame_v[0]
    earth_frame = -mars_fraction * frame_r / 1000.0
    mars_frame = earth_fraction * frame_r / 1000.0

    basis = camera_basis()
    screen_x, screen_y, _view = basis
    earth_xy = project(earth_pos, screen_x, screen_y)
    mars_xy = project(mars_pos, screen_x, screen_y)
    earth_frame_xy = project(earth_frame[None, :], screen_x, screen_y)[0]
    mars_frame_xy = project(mars_frame[None, :], screen_x, screen_y)[0]

    recent_trace_start_h = frame_t_central_h - 4.0
    past_continuation = trace_t_central_h < recent_trace_start_h
    before_frame = (
        (trace_t_central_h >= recent_trace_start_h)
        & (trace_t_central_h <= frame_t_central_h)
    )
    pre_sph = (
        (trace_t_central_h >= frame_t_central_h)
        & (trace_t_central_h <= -CENTRAL_TIME_S / 3600.0)
    )
    sph_reference = trace_t_central_h >= -CENTRAL_TIME_S / 3600.0

    fig, ax = plt.subplots(figsize=(8.2, 5.6), dpi=200, facecolor="white")
    ax.set_facecolor("white")
    for xy, color in ((earth_xy, "#0759a5"), (mars_xy, "#a43b23")):
        ax.plot(
            xy[past_continuation, 0],
            xy[past_continuation, 1],
            color=color,
            lw=0.68,
            ls=(0, (2, 3)),
            alpha=0.28,
            zorder=0,
        )
        ax.plot(xy[before_frame, 0], xy[before_frame, 1], color="#777777", lw=0.68, alpha=0.46, zorder=1)
        ax.plot(xy[pre_sph, 0], xy[pre_sph, 1], color=color, lw=0.82, alpha=0.66, zorder=2)
        ax.plot(
            xy[sph_reference, 0],
            xy[sph_reference, 1],
            color=color,
            lw=0.68,
            ls=(0, (2, 3)),
            alpha=0.30,
            zorder=1,
        )

    # Time ticks on the Mars barycentric path.
    tick_hours = (-36, -24, -12)
    for hour in tick_hours:
        index = int(np.argmin(np.abs(trace_t_central_h - hour)))
        xy = mars_xy[index]
        if abs(hour - frame_t_central_h) > 0.05:
            ax.plot(xy[0], xy[1], marker="o", ms=3.0, mfc="white", mec="#8c3b2a", mew=0.8, zorder=4)
            ax.annotate(f"{hour:g} h", xy, xytext=(5, 5), textcoords="offset points", fontsize=8.5, color="#555555", zorder=4)

    earth_radius_km = float(initial["earth_radius"]) / 1000.0
    mars_radius_km = float(initial["mars_radius"]) / 1000.0
    earth_spin = 2.0 * np.pi * frame_t_ic_s / (EARTH_SPIN_PERIOD_H * 3600.0)
    mars_spin = 2.0 * np.pi * frame_t_ic_s / (MARS_SPIN_PERIOD_H * 3600.0)

    moon_xy: np.ndarray | None = None
    if not args.hide_moon:
        # The SPH initial condition contains no Moon.  Show a mean-radius lunar
        # orbit in the encounter plane and choose a diagrammatic phase that keeps
        # the physically scaled Moon legible and clear of the incoming Mars track.
        lunar_angle = np.linspace(0.0, 2.0 * np.pi, 721)
        lunar_orbit_3d = earth_frame[None, :] + MEAN_LUNAR_DISTANCE_KM * np.column_stack(
            (np.cos(lunar_angle), np.sin(lunar_angle), np.zeros_like(lunar_angle))
        )
        lunar_orbit_xy = project(lunar_orbit_3d, screen_x, screen_y)
        ax.plot(
            lunar_orbit_xy[:, 0],
            lunar_orbit_xy[:, 1],
            color="#747474",
            lw=0.72,
            ls=(0, (5, 4)),
            alpha=0.72,
            zorder=0,
        )
        moon_phase = np.deg2rad(MOON_DIAGRAM_PHASE_DEG)
        moon_3d = earth_frame + MEAN_LUNAR_DISTANCE_KM * np.array(
            [np.cos(moon_phase), np.sin(moon_phase), 0.0]
        )
        moon_xy = project(moon_3d[None, :], screen_x, screen_y)[0]
        ax.add_patch(
            Circle(
                moon_xy,
                MOON_RADIUS_KM,
                facecolor="#f2f2f0",
                edgecolor="#3f3f3f",
                lw=0.75,
                zorder=7,
            )
        )
        ax.text(
            moon_xy[0],
            moon_xy[1] - MOON_RADIUS_KM - 3700.0,
            "MOON",
            fontsize=8.5,
            fontweight="bold",
            color="#3f3f3f",
            ha="center",
            va="top",
            zorder=15,
        )
        orbit_label_index = int(np.argmin(np.abs(lunar_angle - np.deg2rad(300.0))))
        ax.annotate(
            "LUNAR ORBIT",
            lunar_orbit_xy[orbit_label_index],
            xytext=(7, 6),
            textcoords="offset points",
            fontsize=8.5,
            color="#666666",
            ha="left",
            va="bottom",
            zorder=15,
        )

    draw_planet(
        ax,
        earth_frame_xy,
        earth_radius_km,
        args.display_scale,
        earth_spin,
        basis,
        "earth",
        args.continents,
    )
    draw_planet(
        ax,
        mars_frame_xy,
        mars_radius_km,
        args.display_scale,
        mars_spin,
        basis,
        "mars",
        args.continents,
    )

    ax.text(
        earth_frame_xy[0],
        earth_frame_xy[1] - earth_radius_km * args.display_scale - 4500,
        "EARTH",
        color="#074b87",
        fontsize=9.5,
        fontweight="bold",
        ha="center",
        va="top",
        zorder=20,
    )
    ax.annotate(
        "MARS",
        mars_frame_xy,
        xytext=(-7, -11),
        textcoords="offset points",
        color="#8b2e1c",
        fontsize=9.5,
        fontweight="bold",
        ha="right",
        va="top",
        zorder=20,
    )

    # Projected relative-velocity direction; arrow length is a display choice.
    projected_velocity = project(frame_v[None, :], screen_x, screen_y)[0]
    projected_velocity /= np.linalg.norm(projected_velocity)
    arrow_length = 26000.0
    arrow_start = mars_frame_xy + projected_velocity * mars_radius_km * args.display_scale * 1.10
    ax.annotate(
        "",
        xy=arrow_start + projected_velocity * arrow_length,
        xytext=arrow_start,
        arrowprops=dict(arrowstyle="-|>", color="#8b2e1c", lw=1.25, mutation_scale=10, alpha=0.44),
        zorder=16,
    )
    velocity_label_xy = mars_frame_xy + np.array([9000.0, 0.0])
    ax.text(
        *velocity_label_xy,
        f"$v_{{rel}}$ = {np.linalg.norm(frame_v) / 1000.0:.3f} km s$^{{-1}}$",
        fontsize=7.4,
        color="#713021",
        ha="left",
        va="center",
        zorder=18,
    )

    earth_velocity = -mars_fraction * frame_v
    projected_earth_velocity = project(earth_velocity[None, :], screen_x, screen_y)[0]
    projected_earth_velocity /= np.linalg.norm(projected_earth_velocity)
    earth_arrow_length = 13500.0
    earth_arrow_start = (
        earth_frame_xy
        + projected_earth_velocity * earth_radius_km * args.display_scale * 1.15
    )
    ax.annotate(
        "",
        xy=earth_arrow_start + projected_earth_velocity * earth_arrow_length,
        xytext=earth_arrow_start,
        arrowprops=dict(arrowstyle="-|>", color="#0759a5", lw=1.20, mutation_scale=9, alpha=0.44),
        zorder=16,
    )

    # Projected 100,000-km scale bar.
    extent_mask = (
        (trace_t_central_h >= recent_trace_start_h)
        & (trace_t_central_h <= 2.0)
    )
    extent_parts = [earth_xy[extent_mask], mars_xy[extent_mask]]
    if moon_xy is not None:
        extent_parts.append(moon_xy[None, :])
    all_xy = np.vstack(extent_parts)
    xmin, ymin = np.min(all_xy, axis=0)
    xmax, ymax = np.max(all_xy, axis=0)
    earth_display_radius = earth_radius_km * args.display_scale
    mars_display_radius = mars_radius_km * args.display_scale
    xmin = min(xmin, earth_frame_xy[0] - earth_display_radius, mars_frame_xy[0] - mars_display_radius)
    xmax = max(xmax, earth_frame_xy[0] + earth_display_radius, mars_frame_xy[0] + mars_display_radius)
    ymin = min(ymin, earth_frame_xy[1] - earth_display_radius, mars_frame_xy[1] - mars_display_radius)
    ymax = max(ymax, earth_frame_xy[1] + earth_display_radius, mars_frame_xy[1] + mars_display_radius)
    pad_x = 0.060 * (xmax - xmin)
    pad_y = 0.085 * max(ymax - ymin, 160000.0)
    ax.set_xlim(xmin - pad_x, xmax + pad_x)
    ax.set_ylim(ymin - pad_y, ymax + pad_y)
    bar_y = ax.get_ylim()[0] + 0.045 * (ax.get_ylim()[1] - ax.get_ylim()[0])
    bar_x0 = ax.get_xlim()[0] + 0.055 * (ax.get_xlim()[1] - ax.get_xlim()[0])
    ax.plot([bar_x0, bar_x0 + 100000.0], [bar_y, bar_y], color="#222222", lw=1.6, zorder=30)
    ax.plot([bar_x0, bar_x0], [bar_y - 4000, bar_y + 4000], color="#222222", lw=1.1, zorder=30)
    ax.plot([bar_x0 + 100000.0, bar_x0 + 100000.0], [bar_y - 4000, bar_y + 4000], color="#222222", lw=1.1, zorder=30)
    ax.text(bar_x0 + 50000.0, bar_y + 8000.0, "100,000 km", fontsize=8.0, ha="center", color="#222222")

    distance_km = float(np.linalg.norm(frame_r) / 1000.0)
    relative_speed_kms = float(np.linalg.norm(frame_v) / 1000.0)
    angular_diameter_deg = float(np.degrees(2.0 * np.arcsin(float(initial["mars_radius"]) / np.linalg.norm(frame_r))))
    eccentricity, pericenter_m, v_infinity = orbital_invariants(frame_r, frame_v, mu)

    state_text = (
        f"FRAME STATE\n"
        f"$t$   ${frame_t_central_h:.3f}$ h\n"
        f"$r_{{EM}}$   {distance_km:,.0f} km\n"
        f"$v_{{rel}}$   {relative_speed_kms:.3f} km s$^{{-1}}$\n"
        f"$\\delta_{{Mars}}$   {angular_diameter_deg:.3f}$^\\circ$\n"
        f"$q_{{PM}}$   {pericenter_m / 1000.0:,.0f} km"
    )
    ax.text(
        bar_x0,
        bar_y + 18000.0,
        state_text,
        fontsize=9.4,
        color="#2c2c2c",
        ha="left",
        va="bottom",
        linespacing=1.28,
        bbox=dict(boxstyle="round,pad=0.48", facecolor="white", edgecolor="#c9c9c9", linewidth=0.75),
        zorder=35,
    )

    ax.set_aspect("equal", adjustable="box")
    ax.axis("off")
    fig.subplots_adjust(left=0.020, right=0.980, bottom=0.025, top=0.965)

    for suffix in ("png", "svg", "pdf"):
        target = args.out.with_suffix(f".{suffix}")
        fig.savefig(target, dpi=220 if suffix == "png" else None, facecolor="white")
        print(f"Wrote {target}")
    plt.close(fig)

    metadata = {
        "frame_time_from_central_h": frame_t_central_h,
        "central_time_from_sph_ic_s": CENTRAL_TIME_S,
        "frame_time_from_sph_ic_s": frame_t_ic_s,
        "earth_mass_kg": earth_mass,
        "mars_mass_kg": mars_mass,
        "earth_effective_radius_km": earth_radius_km,
        "mars_effective_radius_km": mars_radius_km,
        "separation_km": distance_km,
        "relative_speed_km_s": relative_speed_kms,
        "mars_angular_diameter_deg": angular_diameter_deg,
        "hyperbolic_eccentricity": eccentricity,
        "point_mass_pericenter_km": pericenter_m / 1000.0,
        "v_infinity_km_s": v_infinity / 1000.0,
        "planet_display_scale": args.display_scale,
        "earth_spin_phase_deg_from_ic_prime_meridian": float(np.degrees(earth_spin) % 360.0),
        "mars_spin_phase_deg_from_ic_prime_meridian": float(np.degrees(mars_spin) % 360.0),
        "initial_condition": str(args.ic),
        "body_labels": str(args.labels),
        "continent_vectors": str(args.continents),
        "continent_vector_source": "Natural Earth 1:110m land polygons, public domain",
        "mars_vector_source": "USGS/IAU Gazetteer of Planetary Nomenclature region extents",
        "moon_shown": not args.hide_moon,
        "mean_lunar_distance_km": MEAN_LUNAR_DISTANCE_KM,
        "moon_radius_km": MOON_RADIUS_KM,
        "moon_diagram_phase_deg": MOON_DIAGRAM_PHASE_DEG,
        "moon_phase_note": "Diagrammatic; no lunar state is present in the SPH initial condition",
    }
    metadata_path = args.out.with_suffix(".json")
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n")
    print(f"Wrote {metadata_path}")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
