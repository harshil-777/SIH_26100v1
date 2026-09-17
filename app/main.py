from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import bids, dashboard, tenders

app = FastAPI(title="GeM Bid Compliance Platform", version="0.1.0")

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
