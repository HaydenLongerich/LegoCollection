# Security and privacy

BrickLedger is a local desktop application. Collection, sales, box, instruction,
and buyer data stays in the local SQLite database unless you explicitly export it.

## Private files

Never commit the following files to GitHub:

- `data/*` other than `data/.gitkeep`
- `exports/*` other than `exports/.gitkeep`
- SQLite databases and sidecar files (`*.db`, `*.sqlite*`, `*-wal`, `*-shm`)
- BrickEconomy, collection, sales, box, or instruction CSV exports
- `.env` files

The repository `.gitignore` blocks these files. Before every push, verify with:

```powershell
git status --short
git ls-files data exports
```

Only the two `.gitkeep` files should be listed by the second command.

## Import safety

Only import CSV or XLSX files you trust. BrickLedger limits import size, row count,
spreadsheet expansion, and internal worksheet paths, but files from unknown sources
should still be treated cautiously.

## Reporting a vulnerability

Do not open a public issue containing personal data. Contact the repository owner
privately with a description and the minimum reproduction needed.
