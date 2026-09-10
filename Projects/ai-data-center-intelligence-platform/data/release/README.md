# Portable synthetic dataset

`processed_dataset.zip` contains the 16 generated CSV tables needed to build
the local analytical database. The archive is intentionally included so a
fresh GitHub clone can run without committing duplicate raw, processed, and
SQLite files that would add hundreds of megabytes to the repository.

Run the following command from the repository root:

```powershell
python scripts\bootstrap_github.py
```

The bootstrap script validates archive member names, restores missing files to
`data/processed/`, and rebuilds `database/datacenter.db`. Those expanded files
remain local because they are ignored by Git.

All records are synthetic and are licensed with the rest of this project.
