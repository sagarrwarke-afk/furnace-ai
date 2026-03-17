from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import upload, fleet, optimize, whatif
from app.routers import training, sensitivity, config

app = FastAPI(title="Furnace Fleet Optimization API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:4173",
        "http://localhost:4174",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router)
app.include_router(fleet.router)
app.include_router(optimize.router)
app.include_router(whatif.router)
app.include_router(training.router)
app.include_router(sensitivity.router)
app.include_router(config.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
