#!/usr/bin/env python3
"""Generate a low-resolution Mars-Earth grazing-impact trial IC for SWIFT.

This is intentionally a first-pass trial generator for visual workflow testing.
For science-grade runs, relax the separate bodies first, then combine settled
snapshots at the desired impact geometry and run resolution/convergence tests.
"""

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
import seagen
import woma

# WoMa 1.5 may pass this keyword even when no miscellaneous material
# profiles are present; the cloned SEAGen constructor does not accept it.
_ORIG_GENSPHERE = seagen.GenSphere

def _gensphere_compat(*args, Di_param_A1_misc_prof=None, **kwargs):
    return _ORIG_GENSPHERE(*args, **kwargs)

seagen.GenSphere = _gensphere_compat

M_EARTH = 5.9724e24
R_EARTH = 6.3710e6
M_MARS = 6.4171e23
R_MARS = 3.3895e6
G_SI = 6.67430e-11

DEFAULT_CONTINENTS = Path(
    "/Users/greglaughlin/Projects/continents/models/muller2019/"
    "ContinentalPolygons/Global_PresentDay_ContPolygons_2019_v1.shp"
)


@dataclass(frozen=True)
class LabelData:
    body_id: np.ndarray
    surface_class: np.ndarray
    lon_deg: np.ndarray
    lat_deg: np.ndarray
    color_rgb: np.ndarray
    source: str


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--n-total", type=int, default=5000, help="Total SPH particles.")
    p.add_argument("--angle-deg", type=float, default=70.0, help="Impact angle from head-on; 90 deg is tangential.")
    p.add_argument("--v-escape-multiple", type=float, default=1.02, help="Contact speed in mutual escape-speed units.")
    p.add_argument("--start-hours", type=float, default=2.0, help="Start this many hours before first contact.")
    p.add_argument("--earth-core-fraction", type=float, default=0.30)
    p.add_argument("--mars-core-fraction", type=float, default=0.25)
    p.add_argument("--seed-earth", type=int, default=1202401)
    p.add_argument("--seed-mars", type=int, default=1202402)
    p.add_argument("--surface-radius-fraction", type=float, default=0.85)
    p.add_argument("--continent-shapefile", type=Path, default=DEFAULT_CONTINENTS)
    p.add_argument("--out", type=Path, default=None)
    p.add_argument("--label-out", type=Path, default=None)
    p.add_argument("--write-body-files", action=argparse.BooleanOptionalAction, default=True)
    return p.parse_args()


def make_profile(
    name: str,
    mass: float,
    radius: float,
    core_fraction: float,
    radius_min_factor: float,
    radius_max_factor: float,
) -> woma.Planet:
    planet = woma.Planet(
        name=name,
        A1_mat_layer=["ANEOS_Fe85Si15", "ANEOS_forsterite"],
        A1_T_rho_type=["adiabatic", "adiabatic"],
        M=mass,
        A1_M_layer=[mass * core_fraction, mass * (1.0 - core_fraction)],
        P_s=1e5,
        T_s=2000,
    )
    planet.gen_prof_L2_find_R_R1_given_M1_M2(
        R_min=radius_min_factor * radius,
        R_max=radius_max_factor * radius,
        verbosity=1,
    )
    return planet


def point_in_ring(lon: float, lat: float, ring: list[tuple[float, float]]) -> bool:
    inside = False
    n = len(ring)
    if n < 3:
        return False
    x, y = lon, lat
    x0, y0 = ring[-1]
    for x1, y1 in ring:
        if (y1 > y) != (y0 > y):
            x_cross = (x0 - x1) * (y - y1) / ((y0 - y1) + 1e-300) + x1
            if x < x_cross:
                inside = not inside
        x0, y0 = x1, y1
    return inside


def load_land_polygons(path: Path):
    import shapefile  # pyshp

    reader = shapefile.Reader(str(path))
    polygons = []
    for shape in reader.shapes():
        points = [(float(x), float(y)) for x, y in shape.points]
        parts = list(shape.parts) + [len(points)]
        rings = []
        for i0, i1 in zip(parts[:-1], parts[1:]):
            ring = points[i0:i1]
            if len(ring) >= 3:
                rings.append(ring)
        if not rings:
            continue
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        polygons.append((min(xs), min(ys), max(xs), max(ys), rings))
    return polygons


def classify_land(lon_deg: np.ndarray, lat_deg: np.ndarray, shapefile_path: Path) -> tuple[np.ndarray, str]:
    finite = np.isfinite(lon_deg) & np.isfinite(lat_deg)
    land = np.zeros(lon_deg.shape, dtype=bool)
    if shapefile_path.exists():
        try:
            polygons = load_land_polygons(shapefile_path)
            for idx in np.flatnonzero(finite):
                lon = float(lon_deg[idx])
                lat = float(lat_deg[idx])
                for xmin, ymin, xmax, ymax, rings in polygons:
                    if lon < xmin or lon > xmax or lat < ymin or lat > ymax:
                        continue
                    if any(point_in_ring(lon, lat, ring) for ring in rings):
                        land[idx] = True
                        break
            return land, f"continental polygons: {shapefile_path}"
        except Exception as exc:  # pragma: no cover - diagnostic fallback
            print(f"WARNING: land polygon read failed ({exc}); using procedural mask")

    # Fallback: broad visually recognizable blobs, not a real geography product.
    centers = [
        (-100, 45, 34, 20), (-60, -15, 22, 34), (20, 5, 42, 34),
        (75, 45, 58, 26), (135, -25, 22, 16), (-40, 72, 26, 10),
    ]
    for lon0, lat0, sig_lon, sig_lat in centers:
        dlon = ((lon_deg - lon0 + 180.0) % 360.0) - 180.0
        dlat = lat_deg - lat0
        land |= (dlon / sig_lon) ** 2 + (dlat / sig_lat) ** 2 < 1.0
    return land & finite, "procedural placeholder continent blobs"


def make_labels(
    ids: np.ndarray,
    n_earth: int,
    pos_earth_local: np.ndarray,
    pos_mars_local: np.ndarray,
    radius_earth: float,
    radius_mars: float,
    surface_radius_fraction: float,
    continent_shapefile: Path,
) -> LabelData:
    n_total = len(ids)
    body_id = np.zeros(n_total, dtype=np.uint8)
    body_id[:n_earth] = 1
    body_id[n_earth:] = 2

    surface_class = np.zeros(n_total, dtype=np.uint8)
    lon_deg = np.full(n_total, np.nan, dtype=np.float32)
    lat_deg = np.full(n_total, np.nan, dtype=np.float32)

    earth_idx = np.arange(n_earth)
    mars_idx = n_earth + np.arange(len(pos_mars_local))

    r_e = np.linalg.norm(pos_earth_local, axis=1)
    earth_surface = r_e >= surface_radius_fraction * radius_earth
    x, y, z = pos_earth_local.T
    safe = r_e > 0
    lon_deg[earth_idx[safe]] = np.degrees(np.arctan2(y[safe], x[safe])).astype(np.float32)
    lat_deg[earth_idx[safe]] = np.degrees(np.arcsin(np.clip(z[safe] / r_e[safe], -1.0, 1.0))).astype(np.float32)

    surface_class[earth_idx[earth_surface]] = 1  # ocean by default
    land, source = classify_land(lon_deg[:n_earth], lat_deg[:n_earth], continent_shapefile)
    surface_class[earth_idx[earth_surface & land]] = 2

    r_m = np.linalg.norm(pos_mars_local, axis=1)
    mars_surface = r_m >= surface_radius_fraction * radius_mars
    surface_class[mars_idx[mars_surface]] = 3

    color_rgb = np.zeros((n_total, 3), dtype=np.float32)
    color_rgb[:] = (0.18, 0.18, 0.20)          # unlabeled/interior
    color_rgb[surface_class == 1] = (0.03, 0.22, 0.62)  # ocean
    color_rgb[surface_class == 2] = (0.20, 0.55, 0.24)  # land
    color_rgb[surface_class == 3] = (0.73, 0.30, 0.13)  # Mars surface
    return LabelData(body_id, surface_class, lon_deg, lat_deg, color_rgb, source)


def write_labels(path: Path, ids: np.ndarray, labels: LabelData, args: argparse.Namespace) -> None:
    with h5py.File(path, "w") as f:
        f.create_dataset("ParticleIDs", data=ids)
        f.create_dataset("BodyID", data=labels.body_id)
        f.create_dataset("SurfaceClass", data=labels.surface_class)
        f.create_dataset("LongitudeDeg", data=labels.lon_deg)
        f.create_dataset("LatitudeDeg", data=labels.lat_deg)
        f.create_dataset("ColorRGB", data=labels.color_rgb)
        f.attrs["BodyID_1"] = "Earth target"
        f.attrs["BodyID_2"] = "Mars impactor"
        f.attrs["SurfaceClass_0"] = "interior or unlabeled"
        f.attrs["SurfaceClass_1"] = "Earth ocean surface"
        f.attrs["SurfaceClass_2"] = "Earth continental surface"
        f.attrs["SurfaceClass_3"] = "Mars surface"
        f.attrs["LabelSource"] = labels.source
        f.attrs["ImpactAngleDeg"] = args.angle_deg
        f.attrs["ContactSpeedMutualEscape"] = args.v_escape_multiple
        f.attrs["StartHoursBeforeContact"] = args.start_hours


def main() -> None:
    args = parse_args()
    if args.n_total < 1000:
        raise SystemExit("Use at least ~1000 particles; lower values make WoMa profiles very noisy.")

    n_earth = int(round(args.n_total * M_EARTH / (M_EARTH + M_MARS)))
    n_mars = args.n_total - n_earth
    label = f"n{args.n_total:05d}"
    out = args.out or Path(f"mars_earth_grazing_{label}.hdf5")
    label_out = args.label_out or Path(f"mars_earth_grazing_{label}_labels.hdf5")

    print("Loading ANEOS tables through WoMa...")
    woma.load_eos_tables(["ANEOS_Fe85Si15", "ANEOS_forsterite"])

    print("Generating differentiated Earth and Mars profiles...")
    earth_prof = make_profile("earth_target", M_EARTH, R_EARTH, args.earth_core_fraction, 1.02, 1.08)
    mars_prof = make_profile("mars_impactor", M_MARS, R_MARS, args.mars_core_fraction, 0.98, 1.02)
    earth_prof.save(f"earth_profile_{label}.hdf5")
    mars_prof.save(f"mars_profile_{label}.hdf5")

    print(f"Placing particles: Earth request={n_earth}, Mars request={n_mars}")
    earth = woma.ParticlePlanet(earth_prof, n_earth, seed=args.seed_earth)
    mars = woma.ParticlePlanet(mars_prof, n_mars, seed=args.seed_mars)
    n_earth = int(earth.N_particles)
    n_mars = int(mars.N_particles)
    n_total_actual = n_earth + n_mars
    print(f"Actual SEAGen particle counts: Earth={n_earth}, Mars={n_mars}, total={n_total_actual}")

    if args.write_body_files:
        file_to_SI = woma.Conversions(m=1e24, l=1e6, t=1)
        earth.save(f"earth_unrelaxed_{label}.hdf5", boxsize=10 * R_EARTH, file_to_SI=file_to_SI, do_entropies=True)
        mars.save(f"mars_unrelaxed_{label}.hdf5", boxsize=10 * R_EARTH, file_to_SI=file_to_SI, do_entropies=True)

    b = float(np.sin(np.deg2rad(args.angle_deg)))
    pos_earth_body = np.zeros(3)
    vel_earth_body = np.zeros(3)
    pos_mars_body, vel_mars_body = woma.impact_pos_vel_b_v_c_t(
        b=b,
        v_c=args.v_escape_multiple,
        units_v_c="v_esc",
        t=args.start_hours * 3600.0,
        R_t=earth_prof.R,
        R_i=mars_prof.R,
        M_t=M_EARTH,
        M_i=M_MARS,
    )

    m_earth = float(np.sum(earth.A1_m))
    m_mars = float(np.sum(mars.A1_m))
    pos_com = (m_earth * pos_earth_body + m_mars * pos_mars_body) / (m_earth + m_mars)
    vel_com = (m_earth * vel_earth_body + m_mars * vel_mars_body) / (m_earth + m_mars)
    pos_earth_body -= pos_com
    pos_mars_body -= pos_com
    vel_earth_body -= vel_com
    vel_mars_body -= vel_com

    if not hasattr(earth, "A1_s"):
        earth.calculate_entropies()
    if not hasattr(mars, "A1_s"):
        mars.calculate_entropies()

    pos_earth_local = np.array(earth.A2_pos, copy=True)
    pos_mars_local = np.array(mars.A2_pos, copy=True)
    pos = np.append(pos_earth_local + pos_earth_body, pos_mars_local + pos_mars_body, axis=0)
    vel = np.append(
        np.zeros_like(pos_earth_local) + vel_earth_body,
        np.zeros_like(pos_mars_local) + vel_mars_body,
        axis=0,
    )
    ids = np.arange(1, n_total_actual + 1, dtype=np.uint64)

    sep = float(np.linalg.norm(pos_mars_body - pos_earth_body))
    vrel = float(np.linalg.norm(vel_mars_body - vel_earth_body))
    vesc = float(np.sqrt(2.0 * G_SI * (M_EARTH + M_MARS) / (earth_prof.R + mars_prof.R)))
    print(f"Initial body separation: {sep / 1e6:.3f} Mm")
    print(f"Relative speed now:      {vrel / 1e3:.3f} km/s")
    print(f"Mutual escape at contact:{vesc / 1e3:.3f} km/s")

    file_to_SI = woma.Conversions(m=1e24, l=1e6, t=1)
    with h5py.File(out, "w") as f:
        woma.save_particle_data(
            f,
            A2_pos=pos,
            A2_vel=vel,
            A1_m=np.append(earth.A1_m, mars.A1_m),
            A1_h=np.append(earth.A1_h, mars.A1_h),
            A1_rho=np.append(earth.A1_rho, mars.A1_rho),
            A1_P=np.append(earth.A1_P, mars.A1_P),
            A1_u=np.append(earth.A1_u, mars.A1_u),
            A1_mat_id=np.append(earth.A1_mat_id, mars.A1_mat_id),
            A1_id=ids,
            A1_s=np.append(earth.A1_s, mars.A1_s),
            boxsize=100 * R_EARTH,
            file_to_SI=file_to_SI,
        )
        f.attrs["Target"] = "Earth-mass differentiated ANEOS Fe85Si15/forsterite body"
        f.attrs["Impactor"] = "Mars-mass differentiated ANEOS Fe85Si15/forsterite body"
        f.attrs["ImpactAngleDeg"] = args.angle_deg
        f.attrs["ContactSpeedMutualEscape"] = args.v_escape_multiple
        f.attrs["StartHoursBeforeContact"] = args.start_hours
        f.attrs["RequestedParticleCount"] = args.n_total
        f.attrs["ActualParticleCount"] = n_total_actual
        f.attrs["GeneratedEarthRadius_m"] = earth_prof.R
        f.attrs["GeneratedMarsRadius_m"] = mars_prof.R
        f.attrs["Warning"] = "Direct unrelaxed trial IC; relax bodies before science-grade production."

    labels = make_labels(
        ids,
        n_earth,
        pos_earth_local,
        pos_mars_local,
        earth_prof.R,
        mars_prof.R,
        args.surface_radius_fraction,
        args.continent_shapefile,
    )
    write_labels(label_out, ids, labels, args)
    print(f"Wrote {out}")
    print(f"Wrote {label_out}")
    print(f"Label source: {labels.source}")


if __name__ == "__main__":
    main()
