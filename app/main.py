"""ChamaCore FastAPI application entrypoint."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import AppError

settings = get_settings()

app = FastAPI(title=settings.app_name, version="1.0.0")


@app.exception_handler(AppError)
async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": {"code": exc.code, "message": exc.message}},
    )


app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Hello World"}