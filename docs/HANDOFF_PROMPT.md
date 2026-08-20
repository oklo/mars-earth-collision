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

The headline run is the 200k-particle settled Mars-Earth grazing collision.
The simulation completed normally through 92 simulated hours on 2026-08-19.
The latest polished product is the 179-second global-view movie reaching about
89 hours, with an August 17 10:00 AM MDT civil-time clock.  The wider framing
keeps the main remnant in view through the second encounter and long debris
stream.  The 92-hour tail exists in the snapshots but is not included in that
presentation cut.

Important local artifacts in the original SWIFT working tree:

```text
snapshots_settled_n200000_6h/
snapshots_settled_n200000_9h_continuation/
snapshots_settled_n200000_9h_to_19h/
snapshots_settled_n200000_9h_combined/
snapshots_settled_n200000_36h_combined/
snapshots_settled_n200000_36h_to_72h/
snapshots_settled_n200000_72h_to_92h/
mars_earth_grazing_settled_n200000_6h_to_9h_ic.hdf5
mars_earth_grazing_settled_n200000_9h_to_19h_ic.hdf5
mars_earth_grazing_settled_n200000_19h_to_36h_ic.hdf5
mars_earth_grazing_settled_n200000_36h_to_72h_ic.hdf5
mars_earth_grazing_settled_n200000_72h_to_92h_ic.hdf5
mars_earth_grazing_settled_n200000_labels_coast_eroded.hdf5
mars_earth_grazing_settled_n200000_9h_direct_view_45s.mp4
mars_earth_grazing_settled_n200000_9h_storyboard_60s.mp4
mars_earth_grazing_settled_n200000_36h_direct_view_75s.mp4
logs/impact_72h_continuation_n200000.log
logs/impact_92h_continuation_n200000.log
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
grounded visualization and a starting point for quantitative analysis.  The
visible second passage is hydrodynamic, so the earlier three-point-mass/tidal
model must not be propagated through it.

## Completed 9-to-19h Continuation

The 9h-to-19h continuation completed normally.  It was launched on
2026-07-25 under a per-user macOS `launchd` job wrapped by `caffeinate`.

Original SWIFT working-tree artifacts:

```text
/Users/greglaughlin/Projects/earth-mars-swift/trial_mars_earth_grazing/mars_earth_grazing_settled_n200000_9h_to_19h.yml
/Users/greglaughlin/Projects/earth-mars-swift/trial_mars_earth_grazing/mars_earth_grazing_settled_n200000_9h_to_19h_ic.hdf5
/Users/greglaughlin/Projects/earth-mars-swift/trial_mars_earth_grazing/snapshots_settled_n200000_9h_to_19h/
/Users/greglaughlin/Projects/earth-mars-swift/trial_mars_earth_grazing/logs/impact_19h_continuation_n200000.log
```

Completion details:

```text
time_begin: 32400 s
time_end: 68400 s
snapshot count: 601
final snapshot: mars_earth_grazing_settled_n200000_9h_to_19h_0600.hdf5
final particle count: 218268 gas/SPH particles
snapshot directory size: about 12 GB
SWIFT final log line: main: done. Bye.
```

A first-pass diagnostic of the 19h final snapshot found a compact Mars-origin
secondary clump, but not yet a secure long-lived satellite:

```text
main Mars-rich remnant: about 5.29e23 kg of Mars-origin material
candidate secondary clump: about 2.10e22 kg, about 3.3% of original Mars-origin mass
candidate separation from remnant: about 21,400 km
candidate two-body period about remnant: about 18.4 hr
candidate pericenter about remnant: about 8,700 km
approximate instantaneous Mars-remnant Hill radius wrt Earth: about 42,300 km
```

Interpretation: the candidate is energetically bound to the Mars-rich remnant in
a two-body screen and lies inside the instantaneous Hill sphere, but its
pericenter is close enough to the disrupted remnant/Roche-scale region that it
may disrupt or re-accrete.  The Earth-Mars remnant pair also appears to remain
bound in a crude two-body estimate, so later evolution may include another close
encounter.  Treat this as a hypothesis pending final 36h clump analysis,
binding checks, conservation diagnostics, and resolution sensitivity.

## Completed 19-to-36h Continuation

The 19h-to-36h continuation completed normally.  It was launched on
2026-08-08 under a per-user macOS `launchd` job wrapped by `caffeinate`.

Original SWIFT working-tree artifacts:

```text
/Users/greglaughlin/Projects/earth-mars-swift/trial_mars_earth_grazing/mars_earth_grazing_settled_n200000_19h_to_36h.yml
/Users/greglaughlin/Projects/earth-mars-swift/trial_mars_earth_grazing/mars_earth_grazing_settled_n200000_19h_to_36h_ic.hdf5
/Users/greglaughlin/Projects/earth-mars-swift/trial_mars_earth_grazing/snapshots_settled_n200000_19h_to_36h/
/Users/greglaughlin/Projects/earth-mars-swift/trial_mars_earth_grazing/snapshots_settled_n200000_36h_combined/
/Users/greglaughlin/Projects/earth-mars-swift/trial_mars_earth_grazing/logs/impact_36h_continuation_n200000.log
```

Completion details:

```text
time_begin: 68400 s
time_end: 129600 s
snapshot count: 1021
final snapshot: mars_earth_grazing_settled_n200000_19h_to_36h_1020.hdf5
final particle count: 218257 gas/SPH particles
snapshot directory size: about 20 GB
SWIFT final log line: main: done. Bye.
```

The generated 36-hour combined snapshot view contains 2161 symlinks:

```text
snapshots_settled_n200000_36h_combined/mars_earth_grazing_settled_n200000_36h_combined_0000.hdf5
...
snapshots_settled_n200000_36h_combined/mars_earth_grazing_settled_n200000_36h_combined_2160.hdf5
```

The direct-view 36-hour movie has been rendered and copied into the GitHub
project:

```text
outputs/movies/mars_earth_grazing_settled_n200000_36h_direct_view_75s.mp4
outputs/qc/qc_n200000_36h_direct_view/frame_01.png
outputs/qc/qc_n200000_36h_direct_view/frame_02.png
outputs/qc/qc_n200000_36h_direct_view/frame_03.png
outputs/qc/qc_n200000_36h_direct_view/frame_04.png
outputs/qc/qc_n200000_36h_direct_view/frame_05.png
```

Render details:

```text
resolution: 1920 x 1080
fps: 24
duration: 75 s
frames: 1800
view: fixed inertial, z-axis view, final bodies horizontal
particle IDs used: 218257 persistent IDs across 2161 snapshots; 14 dropped particles omitted
```

`src/render_impact_animation.py` now explicitly intersects persistent
`ParticleIDs` across the selected snapshots before loading positions.  This is
required for the 36-hour sequence because SWIFT drops a very small number of
particles between the initial and final snapshots.

## Completed 36-to-92h Hero Continuation

The 36-to-72-hour stage completed normally with 2,700 snapshots.  Its final
state is exactly `259200 s` (72.0 h) and contains 218,251 particles.  The
72-to-92-hour stage also completed normally with 1,080 snapshots.  Its final
state is:

```text
snapshots_settled_n200000_72h_to_92h/
  mars_earth_grazing_settled_n200000_72h_to_92h_1079.hdf5
time: 331200 s = 92.0 h
particles: 215299
sha256: b3a241779f10ac12ef1fdf59a11186d6950cae60cba2d31170d09830d0474a9b
SWIFT final log line: main: done. Bye.
```

The larger particle loss during the last stage should be accounted for in any
mass budget and in the persistent-ID intersection used for rendering.  Do not
assume particles absent from the final HDF5 file are physically accreted
without checking SWIFT's removal criteria and the run statistics.

## Immediate Next Task

The next scientifically useful task is a quantitative 92-hour remnant and
debris census, not further secular-tide propagation.  The global-view movie
shows a serious second passage and long stream, but visual clumps alone do not
establish binding.

Recommended sequence:

1. Run conservation and particle-loss diagnostics across the 36--72 and
   72--92-hour stages.
2. Apply the 36-hour clump finder to the final snapshot and several preceding
   checkpoints, tracking memberships with persistent `ParticleIDs`.
3. Compute masses, source/material fractions, COM states, radii, spin/angular
   momentum, and binding hierarchies for every surviving compact clump.
4. Classify extended stream material relative to Earth, the Mars-origin
   remnant, and the system barycenter; report marginally bound material as an
   interval rather than a hard inventory.
5. Compare the measured first renewed contacts with the encounter ordering in
   `docs/forward_tides_note.md`, while making clear that the analytic model was
   invalid once finite-size hydrodynamics began.

The 92-hour calculation is one 200k-particle realization.  Merger, survival,
satellite, or escape claims still require resolution and initial-condition
sensitivity.

## Existing Render Products

Most useful current movies:

```text
outputs/movies/mars_earth_grazing_settled_n200000_89h_global_view_mdt_10am_179s.mp4
outputs/movies/mars_earth_first4h_standard_wide_mdt_10am_30s.mp4
outputs/movies/mars_earth_grazing_settled_n200000_36h_direct_view_75s.mp4
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
and caveats.  If the 92-hour snapshots suggest reconsolidation, a bound
companion, or escaping clumps, describe each as a hypothesis from this run
until binding, resolution sensitivity, and conservation diagnostics have been
checked.
