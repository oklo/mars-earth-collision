# Mars-Earth Grazing-Impact SWIFT Trial

This directory is a local first-pass setup for a visually useful Mars-Earth grazing encounter in SWIFT.
It is built for workflow validation and animation prototyping, not yet for quantitative claims.

## What is here

- `make_mars_earth_ic.py`: builds differentiated ANEOS Fe85Si15/forsterite Earth- and Mars-mass SPH bodies with WoMa, combines them on a grazing trajectory, and writes a SWIFT HDF5 IC.
- `mars_earth_grazing_smoke.yml`: 120 s SWIFT smoke test.
- `mars_earth_grazing_4h.yml`: several-hour parameter file for a low-resolution animation trial.
- `plot_initial_conditions.py`: makes a quick XY preview PNG.
- `*_labels.hdf5`: visualization sidecar keyed by `ParticleIDs`, with `BodyID`, `SurfaceClass`, longitude/latitude, and RGB colors.
- The default `--n-total 5000` request currently becomes 7,421 actual particles because SEAGen adjusts shell populations.

## Current physical assumptions

- Target is Earth mass/radius; impactor is Mars mass/radius.
- Both are differentiated iron-silicate bodies using SWIFT/WoMa ANEOS Fe85Si15 and forsterite tables.
- Default geometry is a 70 degree impact angle from head-on, with contact speed 1.02 times mutual escape speed, initialized 2 hours before contact.
- The initial combined impact file is generated directly from unrelaxed particle planets. This is useful for a first visual run, but production runs should relax Earth and Mars separately before impact assembly.
- With the hot adiabatic ANEOS setup, the generated Earth analog is mildly inflated at about 1.034 Earth radii; Mars is close to present Mars radius.

## Commands

From this directory:

```bash
/Users/greglaughlin/Projects/earth-mars-swift/.venv/bin/python make_mars_earth_ic.py --n-total 5000
/Users/greglaughlin/Projects/earth-mars-swift/.venv/bin/python plot_initial_conditions.py
DYLD_LIBRARY_PATH=/Users/greglaughlin/Projects/earth-mars-swift/.conda-swift/lib /Users/greglaughlin/Projects/earth-mars-swift/swift/swift --hydro --self-gravity --threads=12 mars_earth_grazing_smoke.yml
```

or:

```bash
THREADS=12 ./run_smoke.sh
```

For a longer low-resolution animation trial:

```bash
DYLD_LIBRARY_PATH=/Users/greglaughlin/Projects/earth-mars-swift/.conda-swift/lib /Users/greglaughlin/Projects/earth-mars-swift/swift/swift --hydro --self-gravity --threads=12 mars_earth_grazing_4h.yml
```


## Refined settled-body workflow

Two SWIFT builds are now present:

- `/Users/greglaughlin/Projects/earth-mars-swift/swift/swift`: fixed-entropy build for body relaxation only.
- `/Users/greglaughlin/Projects/earth-mars-swift/swift-impact/swift`: entropy-evolving build for impact runs.

Low-resolution settled workflow:

```bash
THREADS=12 ./run_relax_lowres.sh
/Users/greglaughlin/Projects/earth-mars-swift/.venv/bin/python analyze_body_snapshot.py snapshots_relax_earth/earth_relax_n05000_0004.hdf5
/Users/greglaughlin/Projects/earth-mars-swift/.venv/bin/python analyze_body_snapshot.py snapshots_relax_mars/mars_relax_n05000_0004.hdf5
THREADS=12 ./run_settled_smoke.sh
```

Current relaxed-body diagnostics at 20,000 s:

- Earth: 6,427 particles, mass `5.9580e24 kg`, `r_99.5 = 6.170e6 m`, radial velocity RMS `20.99 m/s`.
- Mars: 994 particles, mass `6.3937e23 kg`, `r_99.5 = 3.061e6 m`, radial velocity RMS `7.05 m/s`.

The settled impact IC is `mars_earth_grazing_settled_n05000.hdf5`; its sidecar labels are `mars_earth_grazing_settled_n05000_labels.hdf5`. The 120 s settled-impact smoke test completed with the entropy-evolving build and wrote `snapshots_settled_smoke/`.

See `REPRODUCIBILITY.md` for configure lines, run products, and checksums.

## Resolution ladder status

Completed settled-body ladder rungs so far:

| label | requested `n_total` | actual particles | impact snapshots | snapshot storage | MP4 |
|---|---:|---:|---:|---:|---|
| `n20000` | 20,000 | 23,749 | 49 | 115 MB | `mars_earth_grazing_settled_n20000_30s.mp4` |
| `n50000` | 50,000 | 57,089 | 49 | 257 MB | `mars_earth_grazing_settled_n50000_30s.mp4` |
| `n100000` | 100,000 | 112,486 | 49 | 507 MB | `mars_earth_grazing_settled_n100000_30s.mp4` |

Each completed MP4 is 1920x1080, 24 fps, 30.0 s, 720 frames. Verification midframes are written as `mars_earth_grazing_settled_<label>_30s_midframe.png`.

The wrapper that runs a rung and immediately renders/verifies the animation is:

```bash
THREADS=12 ./run_ladder_with_animation.sh 50000 100000
```

It calls `run_ladder_case.sh` for each requested `n_total`, then renders with `render_impact_animation.py`, runs `ffprobe`, and extracts a midframe. To rerender an existing rung without rerunning SWIFT:

```bash
FORCE_RENDER=1 ./run_ladder_with_animation.sh 100000
```

Current relaxed-body diagnostics at 20,000 s:

| label | body | particles | mass kg | r_99.5 m | radial RMS m/s | tangential RMS m/s |
|---|---|---:|---:|---:|---:|---:|
| `n20000` | Earth | 21,805 | `5.95833581e24` | `6.30594445e6` | 21.31 | 6.23 |
| `n20000` | Mars | 1,944 | `6.39455447e23` | `3.11802703e6` | 4.83 | 14.63 |
| `n50000` | Earth | 51,738 | `5.95849318e24` | `6.37615996e6` | 21.26 | 5.00 |
| `n50000` | Mars | 5,351 | `6.39487224e23` | `3.19738690e6` | 8.22 | 7.13 |
| `n100000` | Earth | 101,120 | `5.95858541e24` | `6.41789842e6` | 22.28 | 3.67 |
| `n100000` | Mars | 11,366 | `6.39535791e23` | `3.24292878e6` | 12.55 | 4.20 |


### Refined render pass

The current renderer now keeps full 3D particle positions and draws two visual layers: a dim body-base layer plus a depth-sorted, observer-facing surface layer. Marker sizes scale down with particle count, and Earth surface colors use the existing present-day continent labels with a cleaner land/ocean palette. The refined high-resolution animations use an oblique view vector `0,-0.55,0.84`:

- `mars_earth_grazing_settled_n50000_30s_refined.mp4`
- `mars_earth_grazing_settled_n100000_30s_refined.mp4`

Render command pattern:

```bash
env -u DYLD_LIBRARY_PATH /Users/greglaughlin/Projects/earth-mars-swift/.venv/bin/python render_impact_animation.py \
  --snapshot-dir snapshots_settled_n100000_4h \
  --basename mars_earth_grazing_settled_n100000_4h \
  --labels mars_earth_grazing_settled_n100000_labels.hdf5 \
  --out mars_earth_grazing_settled_n100000_30s_refined.mp4 \
  --duration 30 --fps 24 --width 1920 --height 1080 \
  --view-vector 0,-0.55,0.84
```

The next practical local rung is likely `n200000`, but that should be treated as an overnight-style run rather than an interactive quick rung. The current movies are scientifically informed visualization prototypes using differentiated ANEOS bodies and advected surface-color tracers; they are not yet convergence-tested publication results.

## Publication-quality next steps

1. Relax separate Earth and Mars bodies for multiple dynamical times and verify stable radius, density profile, angular momentum, energy drift, and low residual velocities.
2. Combine the settled snapshots, not the direct unrelaxed particles, at the chosen geometry.
3. Run a resolution ladder and geometry ladder: particle count, angle, velocity, core fraction, impactor spin, and thermal state.
4. Improve the render pipeline with camera choreography, depth cues, higher-resolution particle renders, and optional compositing while preserving `ParticleIDs` plus sidecar labels so Earth-surface colors advect with material particles.
5. Track conservation diagnostics per run and archive the exact SWIFT configure line, git commits, parameter files, and EOS table checksums.
