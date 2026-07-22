# Stale backend diagnostic

A frontend `404` from `/api/application-index` while the route exists in source indicates that the active backend process is older than the frontend.

Startup must verify frontend-critical OpenAPI routes, not only the semantic backend version.
