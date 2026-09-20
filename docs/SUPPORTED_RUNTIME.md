# Supported production runtime

JOLT is currently certified as a local-first, single-user Windows application. Production-ready claims apply only to the runtime matrix below until another platform is explicitly validated.

## Supported matrix

| Component | Supported production range | Enforcement |
|---|---|---|
| Operating system | Windows 10 22H2 or Windows 11, x64 | operator preflight; clean-install acceptance |
| PowerShell | 7.4 or later | `tools/assert-jolt-runtime.ps1` |
| Git | 2.40 or later | `tools/assert-jolt-runtime.ps1` |
| uv | >= 0.5.14 and < 1.0.0 | `tools/assert-jolt-runtime.ps1` |
| Python | CPython 3.12.x | `backend/pyproject.toml`; installed/selected by uv |
| Node.js | 22.x | `tools/assert-jolt-runtime.ps1`; CI |
| npm | 10.x or 11.x | `tools/assert-jolt-runtime.ps1` |
| Browser automation | Playwright-managed Chromium | backend dependency lock + acceptance workflows |

Python 3.13 is intentionally unsupported because the backend declares `requires-python = ">=3.12,<3.13"`.

Node.js 23+ is intentionally not part of the production matrix even if the frontend happens to build there. JOLT's production evidence is based on Node 22.

## Operator preflight

From the repository root:

```powershell
.\tools\assert-jolt-runtime.ps1
```

A successful run prints machine-readable JSON containing the detected versions. A failed requirement stops startup before JOLT modifies the database or launches services.

`tools/start-jolt.ps1` runs the same preflight automatically and then explicitly ensures CPython 3.12 is available through uv before syncing backend dependencies.

## Certification boundary

A runtime can be called **supported** only when:

1. it satisfies the matrix above;
2. JOLT completes a clean install from documented prerequisites;
3. migrations succeed on a new database;
4. backend and frontend start and pass health checks;
5. CI, Playwright acceptance, and full-cycle certification are green on the exact release commit.

Other Windows versions, ARM64, macOS, Linux, Windows PowerShell 5.1, Python 3.13+, and non-Node-22 runtimes may work but are not production-certified.
