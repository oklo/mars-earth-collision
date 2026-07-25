# Large Artifacts Not Copied

These directories were deliberately left out of the GitHub-ready project because they are large generated snapshot time series. The source copies currently remain under:

`/Users/greglaughlin/Projects/earth-mars-swift/trial_mars_earth_grazing`

| Directory | Approx. size | Notes |
|---|---:|---|
| `snapshots_settled_n200000_6h/` | 7.0 GB | Primary 200k-particle 6-hour run snapshots. |
| `snapshots_settled_n200000_9h_continuation/` | 3.5 GB | Continuation snapshots from 6 to 9 hours. |
| `snapshots_settled_n200000_9h_to_19h/` | in progress; expected ~12 GB | Live continuation from 9 to 19 hours, launched 2026-07-25 under `launchd`/`caffeinate`. |
| `snapshots_settled_n100000_4h/` | 506 MB | 100k resolution ladder run. |
| `snapshots_settled_n50000_4h/` | 257 MB | 50k resolution ladder run. |
| `snapshots_settled_n20000_4h/` | 115 MB | 20k resolution ladder run. |
| `snapshots_relax_earth_n200000/` | 92 MB | Earth relaxation snapshots. |

The combined 9-hour snapshot directory in the original working tree is symlink-based and reports as zero disk usage locally:

`snapshots_settled_n200000_9h_combined/`

If this project needs full reproducibility on another machine, archive the snapshot directories separately, or use Git LFS/DVC/object storage rather than ordinary Git blobs.
