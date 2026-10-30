# Disposable upgrade fixtures

`legacy_aura_memory.sql` is the SQLite schema from commit
`3fa324e804267dcfd874844fc16b530e463809a5`, immediately before reminder
weekday schedules were added. It includes the earlier reminder table without
`days_of_week` and `acknowledged_on`. The preview-install smoke seeds this
schema with synthetic memory and a reminder, then starts the extracted app
against that temporary database to check that startup snapshots and migrations
retain the records. It never opens or modifies the owner's configured database.
