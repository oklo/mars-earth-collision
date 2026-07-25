# Handoff Prompt: Mars-Earth SPH Collision Work

You are taking over the Mars-Earth grazing-collision SPH visualization project.
Work autonomously, but preserve the distinction between presentation-quality
visualization and publication-quality scientific claims.

## Project Locations

GitHub-ready project:

```text
/Users/greglaughlin/Projects/mars-earth-collision
https://github.com/oklo/mars-earth-collision
```

Original SWIFT working tree with large snapshot time series:

```text
/Users/greglaughlin/Projects/earth-mars-swift/trial_mars_earth_grazing
```

The GitHub project intentionally excludes the multi-GB snapshot directories.
See:

```text
mars-earth-collision/manifests/LARGE_ARTIFACTS.md
```

Use the original SWIFT working tree for continuing simulations unless the large
artifacts have been separately restored into the GitHub-ready project.

## Current Headline Result

The headline run is the 200k-particle settled Mars-Earth grazing collision,
rendered through 9 simulated hours.

Important local artifacts in the original SWIFT working tree:

```text
snapshots_settled_n200000_6h/
snapshots_settled_n200000_9h_continuation/
snapshots_settled_n200000_9h_combined/
mars_earth_grazing_settled_n200000_6h_to_9h_ic.hdf5
mars_earth_grazing_settled_n200000_labels_coast_eroded.hdf5
mars_earth_grazing_settled_n200000_9h_direct_view_45s.mp4
mars_earth_grazing_settled_n200000_9h_storyboard_60s.mp4
```

The GitHub project contains curated code, configs, compact HDF5 products,
movies, QC frames, and paper draft:

```text
src/
configs/
data/
outputs/
docs/
paper/
manifests/
```

## Scientific Context

The current run is a visually compelling but not yet convergence-tested
simulation of a near-grazing Earth-Mars collision.  The model uses:

- SWIFT planetary SPH with self-gravity.
- WoMa/SEAGen differentiated Earth- and Mars-mass bodies.
- ANEOS Fe85Si15 and forsterite EOS tables.
- Settled-body initial conditions.
- A nominal impact angle of 70 degrees from head-on.
- A contact velocity of 1.02 times the mutual escape speed.
- Advected visualization labels keyed by `ParticleIDs`.

Do not present the current result as a robust physical boundary between merger,
hit-and-run, erosion, or satellite-forming regimes.  It is a scientifically
grounded visualization and a starting point for quantitative analysis.

## Live 9-to-19h Continuation

As of 2026-07-25 15:01 PDT, the headline 200k-particle run has been
extended from 9 simulated hours to 19 simulated hours.  It is running in the
original SWIFT working tree under a per-user macOS `launchd` job wrapped by
`caffeinate`, so ordinary terminal closure, display sleep, or screensaver state
should not stop the calculation.

Original SWIFT working-tree artifacts:

```text
/Users/greglaughlin/Projects/earth-mars-swift/trial_mars_earth_grazing/mars_earth_grazing_settled_n200000_9h_to_19h.yml
/Users/greglaughlin/Projects/earth-mars-swift/trial_mars_earth_grazing/mars_earth_grazing_settled_n200000_9h_to_19h_ic.hdf5
/Users/greglaughlin/Projects/earth-mars-swift/trial_mars_earth_grazing/snapshots_settled_n200000_9h_to_19h/
/Users/greglaughlin/Projects/earth-mars-swift/trial_mars_earth_grazing/logs/impact_19h_continuation_n200000.log
/Users/greglaughlin/Projects/earth-mars-swift/trial_mars_earth_grazing/logs/com.greglaughlin.mars-earth.19h.plist
```

The compact continuation config and IC have also been copied into the GitHub
project:

```text
configs/mars_earth_grazing_settled_n200000_9h_to_19h.yml
data/mars_earth_grazing_settled_n200000_9h_to_19h_ic.hdf5
```

Run details:

```text
launchd label: com.greglaughlin.mars-earth.19h
verified SWIFT PID at launch: 11084
time_begin: 32400 s
time_end: 68400 s
snapshot cadence: 60 s
expected final snapshot index: 0600
particles: 218271 gas/SPH particles
threads: 12
```

The continuation IC was copied from:

```text
snapshots_settled_n200000_9h_continuation/mars_earth_grazing_settled_n200000_9h_continuation_0180.hdf5
```

It preserves particle ordering and `ParticleIDs`, with the compatibility aliases
`Density`, `InternalEnergy`, and `SmoothingLength` added to match the previous
6-to-9-hour continuation IC.

Monitor the live run with:

```bash
cd /Users/greglaughlin/Projects/earth-mars-swift/trial_mars_earth_grazing
launchctl print gui/$(id -u)/com.greglaughlin.mars-earth.19h | grep -E 'state =|pid =|runs =|last exit code'
tail -f logs/impact_19h_continuation_n200000.log
find snapshots_settled_n200000_9h_to_19h -maxdepth 1 -name '*.hdf5' | wc -l
```

To stop the launchd job intentionally:

```bash
launchctl bootout gui/$(id -u) logs/com.greglaughlin.mars-earth.19h.plist
```

Do not stop it unless there is a clear reason: a SWIFT failure, runaway disk
use, thermal problem, or an explicit user request.

## Immediate Next Task

First priority: when the live 9-to-19-hour continuation completes, analyze the
late-time Mars-rich remnant.  The scientific question is whether the departing
Mars-rich body reconsolidates, remains a disrupted elongated remnant, or forms
a large bound satellite/secondary companion of its own.

Recommended sequence:

1. Confirm the run completed normally.  The expected final snapshot is:

   ```text
   snapshots_settled_n200000_9h_to_19h/mars_earth_grazing_settled_n200000_9h_to_19h_0600.hdf5
   ```

   Check the SWIFT log for normal termination and conservation diagnostics.

2. Build a combined 19-hour snapshot view by symlinking the existing 0-to-6-hour,
   6-to-9-hour, and 9-to-19-hour snapshots into a new continuous directory:

   ```text
   snapshots_settled_n200000_19h_combined/
   ```

   Use a continuous basename such as:

   ```text
   mars_earth_grazing_settled_n200000_19h_combined_0000.hdf5
   ```

3. Analyze the Mars remnant and possible satellite:

   - Identify Mars-origin particles using `BodyID == 2` from the label file.
   - Find bound clumps in the Mars-origin material at late times.
   - Compute mass, COM, velocity, angular momentum, and approximate binding
     energy of the main Mars remnant and any secondary clump.
   - Check whether a candidate companion is bound to the Mars remnant and
     whether it lies outside the remnant's Roche-like disruption region.
   - Compare to Earth binding as well: distinguish a true Mars satellite from
     a transient fragment, Earth-bound debris, or unbound ejecta.
   - Produce a short note with caveats about resolution, SPH clump finding, and
     the fact that this is one high-impact visualization run rather than a
     convergence-tested parameter survey.

4. Render at least one updated direct inertial-frame movie and one diagnostic
   final-state still.  Reuse:

   ```text
   src/render_impact_animation.py
   src/render_storyboard_animation.py
   src/render_density_trial_frames.py
   ```

   The current direct-view render style uses:

   ```bash
   env -u DYLD_LIBRARY_PATH /Users/greglaughlin/Projects/earth-mars-swift/.venv/bin/python \
     render_impact_animation.py \
     --snapshot-dir snapshots_settled_n200000_19h_combined \
     --basename mars_earth_grazing_settled_n200000_19h_combined \
     --labels mars_earth_grazing_settled_n200000_labels_coast_eroded.hdf5 \
     --out mars_earth_grazing_settled_n200000_19h_direct_view.mp4 \
     --duration 60 --fps 24 --width 1920 --height 1080 \
     --view-vector 0,0,1 \
     --align-final-bodies-horizontal \
     --bounds-mode final-bodies \
     --bounds-quantile 0.995 \
     --camera-padding 0.06 \
     --title-color '#b6bdc9' \
     --clock-color '#9aa3b0' \
     --title-fontsize 13 \
     --clock-fontsize 9.5
   ```

5. Update the GitHub-ready project after the extension:

   - Copy new scripts/configs/compact products/rendered movies/QC frames into
     `/Users/greglaughlin/Projects/mars-earth-collision`.
   - Do not commit multi-GB snapshot directories to Git.
   - Update `manifests/LARGE_ARTIFACTS.md` with the completed 9-to-19-hour
     snapshot directory size.
   - Commit and push to `https://github.com/oklo/mars-earth-collision`.

## Existing Render Products

Most useful current movies:

```text
outputs/movies/mars_earth_grazing_settled_n200000_9h_direct_view_45s.mp4
outputs/movies/mars_earth_grazing_settled_n200000_9h_storyboard_60s.mp4
```

Current README figure frames:

```text
docs/figures/direct_view_00_start.png
docs/figures/direct_view_01_approach.png
docs/figures/direct_view_02_contact.png
docs/figures/direct_view_03_departure.png
docs/figures/direct_view_04_final.png
```

Paper draft:

```text
paper/mars_earth_collision_apj.tex
paper/mars_earth_collision_apj.pdf
```

## Practical Constraints

- The laptop has previously been a MacBook M4 Max with 36 GB RAM.
- Network access may be restricted in agent environments; do not assume new
  package downloads are possible.
- Do not install global software, change shell profiles, or alter system
  configuration without explicit permission.
- Keep large generated snapshot outputs out of ordinary Git.
- Preserve particle IDs and sidecar labels; the render pipeline depends on
  `ParticleIDs`.
- Prefer small, coherent commits.

## Communication Style

Report results with concrete paths, exact simulated times, particle counts,
and caveats.  If the 19-hour run suggests Mars reconsolidation or a bound
companion, describe it as a hypothesis from this run until clump binding,
resolution sensitivity, and conservation diagnostics have been checked.
