#!/usr/bin/env python3
"""Assemble a Mars-Earth impact IC from separately relaxed SWIFT snapshots."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SEAGEN_ROOT = PROJECT_ROOT / "seagen"
if str(SEAGEN_ROOT) not in sys.path:
    sys.path.insert(0, str(SEAGEN_ROOT))

import h5py
import numpy as np
import woma

from make_mars_earth_ic import DEFAULT_CONTINENTS, G_SI, classify_land, write_labels, LabelData


@dataclass
class Body:
    pos: np.ndarray
    vel: np.ndarray
    mass: np.ndarray
    h: np.ndarray
    rho: np.ndarray
    pressure: np.ndarray
    u: np.ndarray
    mat_id: np.ndarray
    entropy: np.ndarray | None

    @property
    def total_mass(self) -> float:
        return float(np.sum(self.mass))

    @property
    def radius_p995(self) -> float:
        r = np.linalg.norm(self.pos, axis=1)
        return float(np.quantile(r, 0.995))

    @property
    def radius_max(self) -> float:
        return float(np.max(np.linalg.norm(self.pos, axis=1)))


def attr_scalar(value):
    return float(np.asarray(value).reshape(-1)[0])


def parse_vector(text: str) -> np.ndarray:
    values = np.array([float(part.strip()) for part in text.split(",")], dtype=float)
    if values.shape != (3,) or not np.all(np.isfinite(values)):
        raise argparse.ArgumentTypeError("spin axis must contain three finite comma-separated numbers")
    norm = float(np.linalg.norm(values))
    if norm == 0.0:
        raise argparse.ArgumentTypeError("spin axis must be non-zero")
    return values / norm


def spin_velocity(pos: np.ndarray, mass: np.ndarray, period_hours: float, axis_text: str) -> tuple[np.ndarray, np.ndarray, float, float]:
    axis = parse_vector(axis_text)
    if period_hours == 0.0:
        return np.zeros_like(pos), axis, 0.0, 0.0
    if period_hours < 0.0:
        raise ValueError("spin periods must be non-negative; use a reversed axis for retrograde spin")
    omega_mag = 2.0 * np.pi / (period_hours * 3600.0)
    omega = omega_mag * axis
    vel = np.cross(omega[None, :], pos)
    # Keep the assembled two-body trajectory exactly on the requested COM path.
    v_com = np.sum(vel * mass[:, None], axis=0) / float(np.sum(mass))
    vel = vel - v_com
    radius = float(np.quantile(np.linalg.norm(pos, axis=1), 0.995))
    return vel, axis, omega_mag, omega_mag * radius


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--earth", type=Path, default=Path("snapshots_relax_earth/earth_relax_n05000_0004.hdf5"))
    p.add_argument("--mars", type=Path, default=Path("snapshots_relax_mars/mars_relax_n05000_0004.hdf5"))
    p.add_argument("--angle-deg", type=float, default=70.0)
    p.add_argument("--v-escape-multiple", type=float, default=1.02)
    p.add_argument("--start-hours", type=float, default=2.0)
    p.add_argument("--surface-radius-fraction", type=float, default=0.85)
    p.add_argument("--continent-shapefile", type=Path, default=DEFAULT_CONTINENTS)
    p.add_argument("--radius-mode", choices=["p995", "max"], default="p995")
    p.add_argument("--earth-spin-period-hours", type=float, default=0.0, help="Solid-body Earth spin period; 0 disables spin.")
    p.add_argument("--mars-spin-period-hours", type=float, default=0.0, help="Solid-body Mars spin period; 0 disables spin.")
    p.add_argument("--earth-spin-axis", default="0,0,1", help="Earth spin axis in simulation coordinates.")
    p.add_argument("--mars-spin-axis", default="0,0,1", help="Mars spin axis in simulation coordinates.")
    p.add_argument("--out", type=Path, default=Path("mars_earth_grazing_settled_n05000.hdf5"))
    p.add_argument("--label-out", type=Path, default=Path("mars_earth_grazing_settled_n05000_labels.hdf5"))
    return p.parse_args()


def units_from_file(f: h5py.File) -> woma.Conversions:
    return woma.Conversions(
        m=attr_scalar(f["Units"].attrs["Unit mass in cgs (U_M)"]) * 1e-3,
        l=attr_scalar(f["Units"].attrs["Unit length in cgs (U_L)"]) * 1e-2,
        t=attr_scalar(f["Units"].attrs["Unit time in cgs (U_t)"]),
    )


def read_dataset(group: h5py.Group, *names: str) -> np.ndarray | None:
    for name in names:
        if name in group:
            return np.array(group[name][()])
    return None


def load_body(path: Path) -> Body:
    with h5py.File(path, "r") as f:
        conv = units_from_file(f)
        g = f["PartType0"]
        box = np.array(f["Header"].attrs["BoxSize"], dtype=float)
        if box.ndim == 0:
            box = np.repeat(float(box), 3)
        pos = (np.array(g["Coordinates"][()]) - 0.5 * box) * conv.l
        vel = np.array(g["Velocities"][()]) * conv.v
        mass = np.array(g["Masses"][()]) * conv.m
        h = np.array(g["SmoothingLengths"][()]) * conv.l
        rho = np.array(g["Densities"][()]) * conv.rho
        pressure = np.array(g["Pressures"][()]) * conv.P
        u = np.array(g["InternalEnergies"][()]) * conv.u
        mat_id = read_dataset(g, "MaterialIDs", "MaterialIds")
        if mat_id is None:
            raise ValueError(f"No material ID dataset found in {path}")
        entropy = read_dataset(g, "Entropies")
        if entropy is not None:
            entropy = entropy * conv.s

    msum = float(np.sum(mass))
    pos_com = np.sum(pos * mass[:, None], axis=0) / msum
    vel_com = np.sum(vel * mass[:, None], axis=0) / msum
    return Body(pos - pos_com, vel - vel_com, mass, h, rho, pressure, u, mat_id, entropy)


def make_labels(ids: np.ndarray, earth: Body, mars: Body, r_earth: float, r_mars: float, frac: float, shapefile: Path) -> LabelData:
    n_earth = len(earth.mass)
    n_total = len(ids)
    body_id = np.zeros(n_total, dtype=np.uint8)
    body_id[:n_earth] = 1
    body_id[n_earth:] = 2
    surface_class = np.zeros(n_total, dtype=np.uint8)
    lon = np.full(n_total, np.nan, dtype=np.float32)
    lat = np.full(n_total, np.nan, dtype=np.float32)

    earth_idx = np.arange(n_earth)
    mars_idx = n_earth + np.arange(len(mars.mass))
    r_e = np.linalg.norm(earth.pos, axis=1)
    safe = r_e > 0
    x, y, z = earth.pos.T
    lon[earth_idx[safe]] = np.degrees(np.arctan2(y[safe], x[safe])).astype(np.float32)
    lat[earth_idx[safe]] = np.degrees(np.arcsin(np.clip(z[safe] / r_e[safe], -1, 1))).astype(np.float32)
    earth_surface = r_e >= frac * r_earth
    surface_class[earth_idx[earth_surface]] = 1
    land, source = classify_land(lon[:n_earth], lat[:n_earth], shapefile)
    surface_class[earth_idx[earth_surface & land]] = 2

    r_m = np.linalg.norm(mars.pos, axis=1)
    surface_class[mars_idx[r_m >= frac * r_mars]] = 3

    color = np.zeros((n_total, 3), dtype=np.float32)
    color[:] = (0.18, 0.18, 0.20)
    color[surface_class == 1] = (0.03, 0.22, 0.62)
    color[surface_class == 2] = (0.20, 0.55, 0.24)
    color[surface_class == 3] = (0.73, 0.30, 0.13)
    return LabelData(body_id, surface_class, lon, lat, color, source)


def main() -> None:
    args = parse_args()
    earth = load_body(args.earth)
    mars = load_body(args.mars)
    r_earth = earth.radius_p995 if args.radius_mode == "p995" else earth.radius_max
    r_mars = mars.radius_p995 if args.radius_mode == "p995" else mars.radius_max

    b = float(np.sin(np.deg2rad(args.angle_deg)))
    earth_body_pos = np.zeros(3)
    earth_body_vel = np.zeros(3)
    mars_body_pos, mars_body_vel = woma.impact_pos_vel_b_v_c_t(
        b=b,
        v_c=args.v_escape_multiple,
        units_v_c="v_esc",
        t=args.start_hours * 3600.0,
        R_t=r_earth,
        R_i=r_mars,
        M_t=earth.total_mass,
        M_i=mars.total_mass,
    )

    pos_com = (earth.total_mass * earth_body_pos + mars.total_mass * mars_body_pos) / (earth.total_mass + mars.total_mass)
    vel_com = (earth.total_mass * earth_body_vel + mars.total_mass * mars_body_vel) / (earth.total_mass + mars.total_mass)
    earth_body_pos -= pos_com
    mars_body_pos -= pos_com
    earth_body_vel -= vel_com
    mars_body_vel -= vel_com

    earth_spin_vel, earth_spin_axis, earth_omega, earth_spin_speed = spin_velocity(
        earth.pos, earth.mass, args.earth_spin_period_hours, args.earth_spin_axis
    )
    mars_spin_vel, mars_spin_axis, mars_omega, mars_spin_speed = spin_velocity(
        mars.pos, mars.mass, args.mars_spin_period_hours, args.mars_spin_axis
    )

    pos = np.append(earth.pos + earth_body_pos, mars.pos + mars_body_pos, axis=0)
    vel = np.append(earth.vel + earth_spin_vel + earth_body_vel, mars.vel + mars_spin_vel + mars_body_vel, axis=0)
    ids = np.arange(1, len(pos) + 1, dtype=np.uint64)
    entropy = None
    if earth.entropy is not None and mars.entropy is not None:
        entropy_candidate = np.append(earth.entropy, mars.entropy)
        if np.all(np.isfinite(entropy_candidate)) and np.nanmax(entropy_candidate) > 0.0:
            entropy = entropy_candidate
        else:
            print("Skipping non-positive Entropies field from relaxed snapshots; impact IC will use internal energies.")

    file_to_SI = woma.Conversions(m=1e24, l=1e6, t=1)
    with h5py.File(args.out, "w") as f:
        woma.save_particle_data(
            f,
            A2_pos=pos,
            A2_vel=vel,
            A1_m=np.append(earth.mass, mars.mass),
            A1_h=np.append(earth.h, mars.h),
            A1_rho=np.append(earth.rho, mars.rho),
            A1_P=np.append(earth.pressure, mars.pressure),
            A1_u=np.append(earth.u, mars.u),
            A1_mat_id=np.append(earth.mat_id, mars.mat_id),
            A1_id=ids,
            A1_s=entropy,
            boxsize=100 * 6.3710e6,
            file_to_SI=file_to_SI,
        )
        sep = float(np.linalg.norm(mars_body_pos - earth_body_pos))
        vrel = float(np.linalg.norm(mars_body_vel - earth_body_vel))
        vesc = float(np.sqrt(2.0 * G_SI * (earth.total_mass + mars.total_mass) / (r_earth + r_mars)))
        f.attrs["SourceEarthSnapshot"] = str(args.earth)
        f.attrs["SourceMarsSnapshot"] = str(args.mars)
        f.attrs["RadiusMode"] = args.radius_mode
        f.attrs["EffectiveEarthRadius_m"] = r_earth
        f.attrs["EffectiveMarsRadius_m"] = r_mars
        f.attrs["ImpactAngleDeg"] = args.angle_deg
        f.attrs["ContactSpeedMutualEscape"] = args.v_escape_multiple
        f.attrs["StartHoursBeforeContact"] = args.start_hours
        f.attrs["InitialBodySeparation_m"] = sep
        f.attrs["InitialRelativeSpeed_m_per_s"] = vrel
        f.attrs["MutualEscapeSpeedAtContact_m_per_s"] = vesc
        f.attrs["EarthSpinPeriodHours"] = args.earth_spin_period_hours
        f.attrs["MarsSpinPeriodHours"] = args.mars_spin_period_hours
        f.attrs["EarthSpinAxis"] = earth_spin_axis
        f.attrs["MarsSpinAxis"] = mars_spin_axis
        f.attrs["EarthSpinAngularSpeed_rad_s"] = earth_omega
        f.attrs["MarsSpinAngularSpeed_rad_s"] = mars_omega
        f.attrs["EarthSpinSpeedAtR995_m_per_s"] = earth_spin_speed
        f.attrs["MarsSpinSpeedAtR995_m_per_s"] = mars_spin_speed
        f.attrs["Warning"] = "Assembled from relaxed non-rotating snapshots; added solid-body spin velocities at impact assembly. Relax rotating bodies before spin-sensitive quantitative use."

    labels = make_labels(ids, earth, mars, r_earth, r_mars, args.surface_radius_fraction, args.continent_shapefile)
    write_labels(args.label_out, ids, labels, args)
    print(f"Earth mass={earth.total_mass:.6e} kg radius({args.radius_mode})={r_earth:.6e} m")
    print(f"Mars  mass={mars.total_mass:.6e} kg radius({args.radius_mode})={r_mars:.6e} m")
    print(f"Earth spin period={args.earth_spin_period_hours:.8g} hr axis={earth_spin_axis.tolist()} speed_r995={earth_spin_speed:.3f} m/s")
    print(f"Mars  spin period={args.mars_spin_period_hours:.8g} hr axis={mars_spin_axis.tolist()} speed_r995={mars_spin_speed:.3f} m/s")
    print(f"Wrote {args.out}")
    print(f"Wrote {args.label_out}")
    print(f"Label source: {labels.source}")


if __name__ == "__main__":
    main()
