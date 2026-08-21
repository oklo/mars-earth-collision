# Mars-Earth Collision Project Layout

This repository is a curated, GitHub-ready copy of the Mars-Earth grazing-collision work from:

`/Users/greglaughlin/Projects/earth-mars-swift/trial_mars_earth_grazing`

The original SWIFT working directory is intentionally left unchanged.

## Contents

- `src/`: initial-condition, analysis, rendering, label-refinement, and storyboard scripts.
- `configs/`: provenance copies of the SWIFT/impact YAML files and output-time lists used for relaxation and impact runs.
- `data/`: compact generated HDF5 inputs, profiles, labels, and restart/IC files.
- `outputs/movies/`: curated rendered MP4 products; local intermediate renders belong in the ignored `outputs/movies/archive/` directory.
- `outputs/qc/`: still-frame quality-control extracts from rendered movies.
- `outputs/density_trials/`: trial density-layer render stills.
- `outputs/forward_tides/`: tables and figures from the 36-hour three-clump forward model.
- `docs/figures/`: direct-view, Toomre-style, and narrative figures plus generation metadata.
- `paper/`: the manuscript source and regenerated PDF describing the completed 92-hour calculation.
- `manifests/`: diagnostics, parameter inventories, logs, and snapshot manifests.
- `requirements.txt`: pinned Python dependencies from the archived environment.
- `LICENSE`: MIT license for this project; external software and data retain their own terms.

The YAML files intentionally preserve the absolute EOS paths used for the
original runs. Use `src/prepare_swift_run.py` to create a portable staged copy in
the ignored `runs/` directory; do not rewrite the provenance configuration in
place.

The names and recovery status of locally archived render checkpoints are listed
in `manifests/LOCAL_ARCHIVE.md`.

## Large Outputs

The multi-GB snapshot time-series directories are not copied into this GitHub-ready project. They are documented in `manifests/LARGE_ARTIFACTS.md` and remain in the original SWIFT working directory unless explicitly archived elsewhere.
