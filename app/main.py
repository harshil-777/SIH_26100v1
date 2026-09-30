import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.routers import audit, bids, dashboard, marks, tenders
from app.services import ml_models

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Not awaited: the server starts answering (health checks, tender lists) immediately while
    # the models load in a worker thread, instead of the first "Run verification" click paying
    # for the whole download + load.
    app.state.ml_warm_up = asyncio.create_task(asyncio.to_thread(ml_models.warm_up))
    yield


app = FastAPI(title="Bid-Auth", version="0.1.0", lifespan=lifespan)


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


_extra_origins = [o.strip() for o in get_settings().cors_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", *_extra_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dashboard.router)
app.include_router(tenders.router)
app.include_router(bids.router)
app.include_router(audit.router)
app.include_router(marks.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
