from fastapi import FastAPI
from app.api import router

app = FastAPI(title="Refactored Deck AI Stack")
app.include_router(router)
