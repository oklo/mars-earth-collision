# Mars-Earth Collision Project Layout

This repository is a curated, GitHub-ready copy of the Mars-Earth grazing-collision work from:

`/Users/greglaughlin/Projects/earth-mars-swift/trial_mars_earth_grazing`

The original SWIFT working directory is intentionally left unchanged.

## Contents

- `src/`: initial-condition, analysis, rendering, label-refinement, and storyboard scripts.
- `configs/`: SWIFT/impact YAML configuration files used for relaxation and impact runs.
- `data/`: compact generated HDF5 inputs, profiles, labels, and restart/IC files.
- `outputs/movies/`: rendered MP4 products.
- `outputs/qc/`: still-frame quality-control extracts from rendered movies.
- `outputs/density_trials/`: trial density-layer render stills.
- `manifests/`: diagnostics, parameter inventories, logs, and snapshot manifests.

## Large Outputs

The multi-GB snapshot time-series directories are not copied into this GitHub-ready project. They are documented in `manifests/LARGE_ARTIFACTS.md` and remain in the original SWIFT working directory unless explicitly archived elsewhere.
