import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.routers import bids, dashboard, tenders

logger = logging.getLogger(__name__)

app = FastAPI(title="GeM Bid Compliance Platform", version="0.1.0")


# Registered before CORSMiddleware so it sits *inside* it: an unhandled error then becomes a
# JSON 500 that still carries CORS headers. Otherwise Starlette's outermost error handler
# answers without them and the browser reports "network error" instead of the real failure.
@app.middleware("http")
async def json_500_on_unhandled_error(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Internal server error. Please try again."})


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dashboard.router)
app.include_router(tenders.router)
app.include_router(bids.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
