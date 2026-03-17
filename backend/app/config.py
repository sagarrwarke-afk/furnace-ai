import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:Swa%402026@localhost:5432/furnace_ai",
)
