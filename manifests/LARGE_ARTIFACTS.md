# Large Artifacts Not Copied

These directories were deliberately left out of the GitHub-ready project because they are large generated snapshot time series. The source copies currently remain under:

`/Users/greglaughlin/Projects/earth-mars-swift/trial_mars_earth_grazing`

| Directory | Approx. size | Notes |
|---|---:|---|
| `snapshots_settled_n200000_6h/` | 7.0 GB | Primary 200k-particle 6-hour run snapshots. |
| `snapshots_settled_n200000_9h_continuation/` | 3.5 GB | Continuation snapshots from 6 to 9 hours. |
| `snapshots_settled_n200000_9h_to_19h/` | 12 GB | Completed continuation snapshots from 9 to 19 hours. |
| `snapshots_settled_n200000_19h_to_36h/` | 20 GB | Completed continuation snapshots from 19 to 36 hours. |
| `snapshots_settled_n200000_36h_to_72h/` | 52 GB | Completed hero continuation from 36 to 72 hours; 2,700 snapshots. |
| `snapshots_settled_n200000_72h_to_92h/` | 21 GB | Completed hero continuation from 72 to 92 hours; 1,080 snapshots. |
| `snapshots_settled_n100000_4h/` | 506 MB | 100k resolution ladder run. |
| `snapshots_settled_n50000_4h/` | 257 MB | 50k resolution ladder run. |
| `snapshots_settled_n20000_4h/` | 115 MB | 20k resolution ladder run. |
| `snapshots_relax_earth_n200000/` | 92 MB | Earth relaxation snapshots. |
| `snapshots_relax_mars_n200000/` | 12 MB | Mars relaxation snapshots. |

Smaller relaxation and smoke-test directories also remain in the working tree:

| Directory group | Approx. combined size | Notes |
|---|---:|---|
| `snapshots_relax_earth{,_n20000,_n50000,_n100000}/` | 90 MB | Low-resolution through 100k Earth relaxation products. |
| `snapshots_relax_mars{,_n20000,_n50000,_n100000}/` | 14 MB | Low-resolution through 100k Mars relaxation products. |
| `snapshots_smoke/`, `snapshots_settled_smoke/` | 5 MB | Initial workflow validation runs. |

The combined snapshot directories in the original working tree are symlink-based and report as near-zero disk usage locally:

`snapshots_settled_n200000_9h_combined/`

`snapshots_settled_n200000_36h_combined/`

There is no materialized 0--92-hour combined directory.  The later global-view
render was assembled from the stage directories while retaining the persistent
particle-ID intersection.  The current presentation cut reaches roughly 89
hours; the simulation itself finishes at 92 hours in
`snapshots_settled_n200000_72h_to_92h/` snapshot `1079`.

If this project needs full reproducibility on another machine, archive the snapshot directories separately, or use Git LFS/DVC/object storage rather than ordinary Git blobs.
