#!/usr/bin/env python3
"""Print basic relaxation diagnostics for a SWIFT planetary body snapshot."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SEAGEN_ROOT = PROJECT_ROOT / "seagen"
if str(SEAGEN_ROOT) not in sys.path:
    sys.path.insert(0, str(SEAGEN_ROOT))

import h5py
import numpy as np
import woma


def attr_scalar(value):
    return float(np.asarray(value).reshape(-1)[0])

def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("snapshot", type=Path)
    return p.parse_args()


def units(f):
    return woma.Conversions(
        m=attr_scalar(f["Units"].attrs["Unit mass in cgs (U_M)"]) * 1e-3,
        l=attr_scalar(f["Units"].attrs["Unit length in cgs (U_L)"]) * 1e-2,
        t=attr_scalar(f["Units"].attrs["Unit time in cgs (U_t)"]),
    )


def main():
    args = parse_args()
    with h5py.File(args.snapshot, "r") as f:
        c = units(f)
        g = f["PartType0"]
        box = np.array(f["Header"].attrs["BoxSize"], dtype=float)
        if box.ndim == 0:
            box = np.repeat(float(box), 3)
        pos = (np.array(g["Coordinates"]) - 0.5 * box) * c.l
        vel = np.array(g["Velocities"]) * c.v
        mass = np.array(g["Masses"]) * c.m
        rho = np.array(g["Densities"]) * c.rho
        t = attr_scalar(f["Header"].attrs.get("Time", np.nan)) * c.t
    m = mass.sum()
    rcom = (pos * mass[:, None]).sum(axis=0) / m
    vcom = (vel * mass[:, None]).sum(axis=0) / m
    x = pos - rcom
    v = vel - vcom
    r = np.linalg.norm(x, axis=1)
    vr = np.sum(x * v, axis=1) / np.maximum(r, 1e-300)
    vt = np.sqrt(np.maximum(np.sum(v * v, axis=1) - vr * vr, 0))
    print(f"snapshot={args.snapshot}")
    print(f"time_s={t:.6g}")
    print(f"particles={len(mass)} mass_kg={m:.8e}")
    print(f"com_offset_m={np.linalg.norm(rcom):.8e} com_speed_m_s={np.linalg.norm(vcom):.8e}")
    print("radius_m " + " ".join(f"q{int(q*1000):03d}={np.quantile(r,q):.8e}" for q in (0.5,0.9,0.99,0.995,1.0)))
    print(f"rho_kg_m3 min={rho.min():.8e} median={np.median(rho):.8e} max={rho.max():.8e}")
    print(f"v_r_rms_m_s={np.sqrt(np.mean(vr*vr)):.8e} v_t_rms_m_s={np.sqrt(np.mean(vt*vt)):.8e} v_r_p95_abs_m_s={np.quantile(np.abs(vr),0.95):.8e}")


if __name__ == "__main__":
    main()
