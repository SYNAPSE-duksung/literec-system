from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.models import Book, Review, User
from app.schemas.book import BookAspectsOut, BookOut, BookReactionRequest
from app.schemas.review import ReviewOut
from app.security import get_current_user
from app.services import book_service, review_service

router = APIRouter(prefix="/api/books", tags=["books"])


def _book_out(book: Book) -> BookOut:
    aspects = book.aspects
    return BookOut(
        id=book.isbn,
        title=book.title,
        author=book.author,
        publisher=book.publisher,
        coverUrl=book.cover_url,
        synopsis=book.synopsis,
        # book_aspects → identityVectors(RADAR_TRAITS) 매핑 규칙(스코어링) 미확정(브리프 §9.1) —
        # 이번 스코프에서는 빈 배열로 반환하기로 확정. 원본 축 텍스트는 aspects로 노출한다.
        identityVectors=[],
        aspects=BookAspectsOut(
            emotionExperience=aspects.emotion_experience if aspects else [],
            likedElements=aspects.liked_elements if aspects else [],
            dislikedElements=aspects.disliked_elements if aspects else [],
        ),
    )


@router.get("", response_model=list[BookOut])
def list_books(db: Session = Depends(get_db)) -> list[BookOut]:
    books = db.query(Book).options(joinedload(Book.aspects)).order_by(Book.title).all()
    return [_book_out(book) for book in books]


@router.get("/{isbn}", response_model=BookOut)
def get_book(isbn: str, db: Session = Depends(get_db)) -> BookOut:
    book = db.get(Book, isbn, options=[joinedload(Book.aspects)])
    if book is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "도서를 찾을 수 없습니다.")
    return _book_out(book)


@router.get("/{isbn}/reviews", response_model=list[ReviewOut])
def list_reviews_by_book(isbn: str, db: Session = Depends(get_db)) -> list[ReviewOut]:
    book = db.get(Book, isbn)
    if book is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "도서를 찾을 수 없습니다.")

    reviews = (
        db.query(Review)
        .options(joinedload(Review.author))
        .filter(Review.isbn == isbn)
        .order_by(Review.created_at.desc())
        .all()
    )
    return [review_service.to_review_out(r) for r in reviews]


@router.post("/{isbn}/reaction", status_code=status.HTTP_204_NO_CONTENT)
def set_book_reaction(
    isbn: str,
    payload: BookReactionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    book = db.get(Book, isbn)
    if book is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "도서를 찾을 수 없습니다.")
    book_service.set_reaction(db, isbn, current_user.id, payload.reaction)


@router.delete("/{isbn}/reaction", status_code=status.HTTP_204_NO_CONTENT)
def clear_book_reaction(
    isbn: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    book = db.get(Book, isbn)
    if book is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "도서를 찾을 수 없습니다.")
    book_service.clear_reaction(db, isbn, current_user.id)
