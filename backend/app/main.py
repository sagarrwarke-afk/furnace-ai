from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import upload, fleet

app = FastAPI(title="Furnace Fleet Optimization API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router)
app.include_router(fleet.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
