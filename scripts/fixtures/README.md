# Disposable upgrade fixtures

`legacy_aura_memory.sql` is the SQLite schema from the original AURA baseline
commit `f73e401c9f6bea2e6d2938cdd0f1d971d9294914`. The preview-install smoke
seeds this schema with synthetic memory, then starts the extracted app against
that temporary database to check that startup snapshots and migrations retain
the records. It never opens or modifies the owner's configured database.
