from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db import get_db
from app.models.deck import Deck
from app.schemas.deck import DeckCreate, Deck as DeckSchema

router = APIRouter()

@router.post("/", response_model=DeckSchema)
def create_deck(deck_in: DeckCreate, db: Session = Depends(get_db)):
    deck = Deck(**deck_in.model_dump(), user_id=1)
    db.add(deck)
    db.commit()
    db.refresh(deck)
    return deck

@router.get("/", response_model=list[DeckSchema])
def list_decks(db: Session = Depends(get_db)):
    return db.query(Deck).all()
