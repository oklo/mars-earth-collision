#!/usr/bin/env python3
"""Create SWIFT parameter files for one Mars-Earth resolution-ladder rung."""

from __future__ import annotations

import argparse
from pathlib import Path


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("n_total", type=int)
    p.add_argument("--relax-end", type=float, default=20000.0)
    p.add_argument("--relax-dt-max", type=float, default=1000.0)
    p.add_argument("--relax-snapshot-dt", type=float, default=5000.0)
    p.add_argument("--impact-end", type=float, default=14400.0)
    p.add_argument("--impact-dt-max", type=float, default=30.0)
    p.add_argument("--impact-snapshot-dt", type=float, default=300.0)
    p.add_argument("--impact-suffix", default="4h", help="Suffix for impact yml, snapshot directory, and basename.")
    return p.parse_args()


def fmt_num(x: float) -> str:
    return str(int(x)) if float(x).is_integer() else str(x)


def path_safe_suffix(value: str) -> str:
    suffix = value.strip()
    if not suffix or any(ch in suffix for ch in "/ \t\n"):
        raise SystemExit("--impact-suffix must be a non-empty path-safe token")
    return suffix


def write(path: Path, text: str) -> None:
    path.write_text(text)
    print(f"Wrote {path}")


def main() -> None:
    args = parse_args()
    label = f"n{args.n_total:05d}"
    impact_suffix = path_safe_suffix(args.impact_suffix)

    eos = """EoS:
    planetary_use_ANEOS_forsterite:   1
    planetary_use_ANEOS_Fe85Si15:     1
    planetary_ANEOS_forsterite_table_file:  /Users/greglaughlin/Projects/earth-mars-swift/swift/examples/Planetary/EoSTables/ANEOS_forsterite_S19.txt
    planetary_ANEOS_Fe85Si15_table_file:    /Users/greglaughlin/Projects/earth-mars-swift/swift/examples/Planetary/EoSTables/ANEOS_Fe85Si15_S20.txt
"""
    common_units = """InternalUnitSystem:
    UnitMass_in_cgs:        1e27
    UnitLength_in_cgs:      1e8
    UnitVelocity_in_cgs:    1e8
    UnitCurrent_in_cgs:     1
    UnitTemp_in_cgs:        1
"""
    sph = """SPH:
    resolution_eta:     1.2348
    delta_neighbours:   0.1
    CFL_condition:      0.2
    h_max:              2.0
    viscosity_alpha:    1.5
"""
    gravity = """Gravity:
    eta:                            0.025
    MAC:                            adaptive
    epsilon_fmm:                    0.001
    theta_cr:                       0.5
    max_physical_baryon_softening:  {softening}
"""

    relax_template = """# Fixed-entropy body relaxation for {body} at {label}.
{units}
InitialConditions:
    file_name:  {ic_file}
    periodic:   0

TimeIntegration:
    time_begin:     0
    time_end:       {time_end}
    dt_min:         0.000001
    dt_max:         {dt_max}

Snapshots:
    subdir:             {snapdir}
    basename:           {basename}
    time_first:         0
    delta_time:         {snap_dt}

Statistics:
    time_first: 0
    delta_time: 1000

Restarts:
    enable: 0

{sph}
{gravity}
{eos}"""
    write(
        Path(f"earth_relax_{label}.yml"),
        relax_template.format(
            body="Earth", label=label, units=common_units, ic_file=f"earth_unrelaxed_{label}.hdf5",
            time_end=fmt_num(args.relax_end), dt_max=fmt_num(args.relax_dt_max),
            snapdir=f"snapshots_relax_earth_{label}", basename=f"earth_relax_{label}",
            snap_dt=fmt_num(args.relax_snapshot_dt), sph=sph, gravity=gravity.format(softening="0.16"), eos=eos,
        ),
    )
    write(
        Path(f"mars_relax_{label}.yml"),
        relax_template.format(
            body="Mars", label=label, units=common_units, ic_file=f"mars_unrelaxed_{label}.hdf5",
            time_end=fmt_num(args.relax_end), dt_max=fmt_num(args.relax_dt_max),
            snapdir=f"snapshots_relax_mars_{label}", basename=f"mars_relax_{label}",
            snap_dt=fmt_num(args.relax_snapshot_dt), sph=sph, gravity=gravity.format(softening="0.10"), eos=eos,
        ),
    )

    impact_template = """# Entropy-evolving settled impact run for {label} ({impact_suffix}).
{units}
InitialConditions:
    file_name:  mars_earth_grazing_settled_{label}.hdf5
    periodic:   0

TimeIntegration:
    time_begin:     0
    time_end:       {time_end}
    dt_min:         0.000001
    dt_max:         {dt_max}

Snapshots:
    subdir:             snapshots_settled_{label}_{impact_suffix}
    basename:           mars_earth_grazing_settled_{label}_{impact_suffix}
    time_first:         0
    delta_time:         {snap_dt}

Statistics:
    time_first: 0
    delta_time: 120

Restarts:
    enable: 0

{sph}
{gravity}
{eos}"""
    write(
        Path(f"mars_earth_grazing_settled_{label}_{impact_suffix}.yml"),
        impact_template.format(
            label=label, impact_suffix=impact_suffix, units=common_units, time_end=fmt_num(args.impact_end),
            dt_max=fmt_num(args.impact_dt_max), snap_dt=fmt_num(args.impact_snapshot_dt),
            sph=sph, gravity=gravity.format(softening="0.25"), eos=eos,
        ),
    )


if __name__ == "__main__":
    main()
