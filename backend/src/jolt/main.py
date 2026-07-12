from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="JOLT API", version="0.1.0")

    @app.get("/api/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "jolt-backend", "version": "0.1.0"}

    return app


app = create_app()
