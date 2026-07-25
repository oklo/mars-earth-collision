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

## Immediate Next Task

First priority: extend the headline 200k-particle simulation by another
10 simulated hours, from the current 9-hour endpoint to 19 hours.

Scientific question: does the departing Mars-rich remnant reconsolidate, remain
a disrupted elongated body, or form a large bound satellite/secondary companion
of its own?

Expected work:

1. Work in the original SWIFT working directory:

   ```bash
   cd /Users/greglaughlin/Projects/earth-mars-swift/trial_mars_earth_grazing
   ```

2. Identify the last 9-hour snapshot:

   ```text
   snapshots_settled_n200000_9h_continuation/mars_earth_grazing_settled_n200000_9h_continuation_0180.hdf5
   ```

   The 6-to-9-hour continuation config runs from `time_begin: 21600` to
   `time_end: 32400` seconds with snapshots every 60 seconds.  A 10-hour
   extension should run to `68400` seconds.

3. Create a new continuation initial-condition file from the 9-hour final
   snapshot.  Use the same basic pattern as the prior 6-to-9-hour continuation:
   a standalone HDF5 IC loaded at `time_begin: 32400`.  If the existing scripts
   already provide a robust copy/box/metadata path, use them.  Otherwise inspect
   the previous `mars_earth_grazing_settled_n200000_6h_to_9h_ic.hdf5` and
   reproduce the minimal required snapshot-to-IC structure without changing
   particle IDs.

4. Add a config such as:

   ```text
   mars_earth_grazing_settled_n200000_9h_to_19h.yml
   ```

   Use:

   ```yaml
   InitialConditions:
       file_name:  mars_earth_grazing_settled_n200000_9h_to_19h_ic.hdf5
       periodic:   0

   TimeIntegration:
       time_begin:     32400
       time_end:       68400
       dt_min:         0.000001
       dt_max:         30

   Snapshots:
       subdir:             snapshots_settled_n200000_9h_to_19h
       basename:           mars_earth_grazing_settled_n200000_9h_to_19h
       time_first:         32400
       delta_time:         60

   Statistics:
       time_first: 32400
       delta_time: 120
   ```

   Keep the SPH, gravity, units, and EOS settings consistent with
   `configs/mars_earth_grazing_settled_n200000_9h_continuation.yml`.

5. Run with the entropy-evolving impact SWIFT binary:

   ```bash
   DYLD_LIBRARY_PATH=/Users/greglaughlin/Projects/earth-mars-swift/.conda-swift/lib \
   /Users/greglaughlin/Projects/earth-mars-swift/swift-impact/swift \
     --hydro --self-gravity --threads=12 \
     mars_earth_grazing_settled_n200000_9h_to_19h.yml
   ```

   Adjust thread count conservatively if the machine is under load.  Capture
   stdout/stderr to a log under `logs/`.

6. After completion, build a combined 19-hour snapshot view, preferably by
   symlinking the existing 0-to-6-hour, 6-to-9-hour, and 9-to-19-hour snapshots
   into a new continuous directory:

   ```text
   snapshots_settled_n200000_19h_combined/
   ```

   Use a continuous basename such as:

   ```text
   mars_earth_grazing_settled_n200000_19h_combined_0000.hdf5
   ```

7. Render at least one updated direct inertial-frame movie and one diagnostic
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

8. Analyze the Mars remnant and possible satellite:

   - Identify Mars-origin particles using `BodyID == 2`.
   - Find bound clumps in the Mars-origin material at late times.
   - Compute mass, COM, velocity, angular momentum, and approximate binding
     energy of the main Mars remnant and any secondary clump.
   - Check whether a candidate companion is bound to the Mars remnant and
     whether it lies outside the remnant's Roche-like disruption region.
   - Compare to Earth binding as well: distinguish a true Mars satellite from
     a transient fragment, Earth-bound debris, or unbound ejecta.
   - Produce a short note with caveats about resolution and SPH clump finding.

9. Update the GitHub-ready project after the extension:

   - Copy new scripts/configs/compact products/rendered movies/QC frames into
     `/Users/greglaughlin/Projects/mars-earth-collision`.
   - Do not commit multi-GB snapshot directories to Git.
   - Update `manifests/LARGE_ARTIFACTS.md` with the new 9-to-19-hour snapshot
     directory size and location.
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
