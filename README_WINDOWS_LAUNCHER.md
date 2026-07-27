# Windows launcher

Use `START_JOLT.bat` or the `JOLT.lnk` desktop shortcut.

The main launcher starts two direct helper scripts:

- `START_JOLT_BACKEND.cmd`
- `START_JOLT_FRONTEND.cmd`

The helpers intentionally avoid nested `cmd.exe /k` command strings because Windows command quoting differs across shells and terminal hosts.
