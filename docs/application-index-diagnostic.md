# Application index diagnostic

The Applications workspace depends on `GET /api/application-index`.

When the UI reports `Unable to load application opportunities`, inspect the endpoint directly before changing UI code:

```powershell
Invoke-WebRequest http://127.0.0.1:8000/api/application-index -UseBasicParsing
```

Capture the HTTP status and response body. A 404 indicates a stale backend process. A 500 indicates a backend serialization or database error and must be diagnosed from the backend log.