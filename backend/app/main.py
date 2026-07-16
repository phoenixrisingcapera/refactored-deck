from fastapi import FastAPI
from app.api.v1 import router as v1_router
from app.db import engine, Base

app = FastAPI(title="Refactored Deck AI Stack")
app.include_router(v1_router, prefix="/api/v1")

# For simplicity in this initial setup
Base.metadata.create_all(bind=engine)
