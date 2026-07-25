#!/usr/bin/env python3
"""Quick 2-D preview for the Mars-Earth grazing-impact IC and labels."""

from __future__ import annotations

import argparse
from pathlib import Path

import h5py
import matplotlib.pyplot as plt
import numpy as np


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("ic", type=Path, nargs="?", default=Path("mars_earth_grazing_n05000.hdf5"))
    p.add_argument("labels", type=Path, nargs="?", default=Path("mars_earth_grazing_n05000_labels.hdf5"))
    p.add_argument("--out", type=Path, default=Path("mars_earth_grazing_n05000_preview.png"))
    return p.parse_args()


def main() -> None:
    args = parse_args()
    with h5py.File(args.ic, "r") as f:
        coords = np.array(f["PartType0/Coordinates"])
        box = float(f["Header"].attrs["BoxSize"][0] if np.ndim(f["Header"].attrs["BoxSize"]) else f["Header"].attrs["BoxSize"])
    with h5py.File(args.labels, "r") as f:
        colors = np.array(f["ColorRGB"])
        surface = np.array(f["SurfaceClass"])

    xyz = coords - 0.5 * box
    order = np.argsort(surface)
    fig, ax = plt.subplots(figsize=(10, 6), constrained_layout=True)
    ax.scatter(xyz[order, 0], xyz[order, 1], s=np.where(surface[order] > 0, 5, 1), c=colors[order], alpha=0.88, linewidths=0)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("x [1000 km]")
    ax.set_ylabel("y [1000 km]")
    ax.set_title("Mars-Earth grazing-impact trial IC")
    ax.set_facecolor("#05070a")
    fig.patch.set_facecolor("white")
    fig.savefig(args.out, dpi=220)
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
