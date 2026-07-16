from fastapi import APIRouter
from app.api.v1.decks import router as decks_router

router = APIRouter()
router.include_router(decks_router, prefix="/decks", tags=["decks"])
