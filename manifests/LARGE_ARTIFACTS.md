# Large Artifacts Not Copied

These directories were deliberately left out of the GitHub-ready project because they are large generated snapshot time series. The source copies currently remain under:

`/Users/greglaughlin/Projects/earth-mars-swift/trial_mars_earth_grazing`

| Directory | Approx. size | Notes |
|---|---:|---|
| `snapshots_settled_n200000_6h/` | 7.0 GB | Primary 200k-particle 6-hour run snapshots. |
| `snapshots_settled_n200000_9h_continuation/` | 3.5 GB | Continuation snapshots from 6 to 9 hours. |
| `snapshots_settled_n200000_9h_to_19h/` | 12 GB | Completed continuation snapshots from 9 to 19 hours. |
| `snapshots_settled_n200000_19h_to_36h/` | 20 GB | Completed continuation snapshots from 19 to 36 hours. |
| `snapshots_settled_n100000_4h/` | 506 MB | 100k resolution ladder run. |
| `snapshots_settled_n50000_4h/` | 257 MB | 50k resolution ladder run. |
| `snapshots_settled_n20000_4h/` | 115 MB | 20k resolution ladder run. |
| `snapshots_relax_earth_n200000/` | 92 MB | Earth relaxation snapshots. |

The combined snapshot directories in the original working tree are symlink-based and report as near-zero disk usage locally:

`snapshots_settled_n200000_9h_combined/`

`snapshots_settled_n200000_36h_combined/`

If this project needs full reproducibility on another machine, archive the snapshot directories separately, or use Git LFS/DVC/object storage rather than ordinary Git blobs.
