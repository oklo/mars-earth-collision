#!/usr/bin/env python3
"""Create a render-only label file with a tighter Earth coastline mask."""

from __future__ import annotations

import argparse
from pathlib import Path

import h5py
import numpy as np
from scipy.spatial import cKDTree


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--labels", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument(
        "--coast-erosion-deg",
        type=float,
        default=2.2,
        help="Demote land particles within this angular distance of ocean particles.",
    )
    return p.parse_args()


def lonlat_to_unit(lon_deg: np.ndarray, lat_deg: np.ndarray) -> np.ndarray:
    lon = np.radians(lon_deg.astype(np.float64))
    lat = np.radians(lat_deg.astype(np.float64))
    clat = np.cos(lat)
    return np.column_stack((clat * np.cos(lon), clat * np.sin(lon), np.sin(lat)))


def main() -> None:
    args = parse_args()
    with h5py.File(args.labels, "r") as src, h5py.File(args.out, "w") as dst:
        for key in src.keys():
            dst.create_dataset(key, data=src[key][...])
        for key, value in src.attrs.items():
            dst.attrs[key] = value

        classes = dst["SurfaceClass"][:]
        body = dst["BodyID"][:]
        lon = dst["LongitudeDeg"][:]
        lat = dst["LatitudeDeg"][:]

        finite_earth = (body == 1) & np.isfinite(lon) & np.isfinite(lat)
        land = finite_earth & (classes == 2)
        ocean = finite_earth & (classes == 1)
        if not np.any(land) or not np.any(ocean):
            raise SystemExit("Need both Earth land and ocean surface labels for coastline erosion.")

        land_idx = np.flatnonzero(land)
        ocean_unit = lonlat_to_unit(lon[ocean], lat[ocean])
        land_unit = lonlat_to_unit(lon[land], lat[land])

        chord_threshold = 2.0 * np.sin(np.radians(args.coast_erosion_deg) / 2.0)
        distance, _ = cKDTree(ocean_unit).query(land_unit, k=1)
        demote = land_idx[distance <= chord_threshold]
        classes[demote] = 1
        dst["SurfaceClass"][:] = classes

        colors = dst["ColorRGB"][:]
        colors[demote] = (0.03, 0.22, 0.62)
        dst["ColorRGB"][:] = colors

        dst.attrs["RenderLabelRefinement"] = (
            "Earth continental-polygon labels eroded at coastlines; "
            "boundary land particles near ocean demoted to ocean for rendering."
        )
        dst.attrs["CoastErosionDeg"] = args.coast_erosion_deg
        dst.attrs["CoastErosionDemotedParticles"] = int(len(demote))
        print(f"Demoted {len(demote)} land particles to ocean using {args.coast_erosion_deg:g} deg erosion.")


if __name__ == "__main__":
    main()
