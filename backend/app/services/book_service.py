import uuid

from sqlalchemy.orm import Session

from app.models import Book, BookReaction


def get_books_by_isbn(db: Session, isbn_list: list[str]) -> list[Book]:
    return db.query(Book).filter(Book.isbn.in_(isbn_list)).all()


def set_reaction(db: Session, isbn: str, user_id: uuid.UUID, reaction: str) -> None:
    existing = db.get(BookReaction, {"user_id": user_id, "isbn": isbn})
    if existing is None:
        db.add(BookReaction(user_id=user_id, isbn=isbn, reaction=reaction))
    elif existing.reaction != reaction:
        existing.reaction = reaction
    db.commit()


def clear_reaction(db: Session, isbn: str, user_id: uuid.UUID) -> None:
    existing = db.get(BookReaction, {"user_id": user_id, "isbn": isbn})
    if existing is not None:
        db.delete(existing)
        db.commit()
