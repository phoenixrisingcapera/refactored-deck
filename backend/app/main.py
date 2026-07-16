from fastapi import FastAPI
from app.api.v1 import router as v1_router

app = FastAPI(title="Refactored Deck AI Stack")
app.include_router(v1_router, prefix="/api/v1")
