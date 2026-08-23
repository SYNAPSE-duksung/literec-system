from typing import Literal

from pydantic import BaseModel


class ReviewOut(BaseModel):
    id: str
    bookId: str
    userId: str
    userName: str
    content: str
    liked: list[str]
    disliked: list[str]
    emotion: list[str]
    likeCount: int
    createdAt: str


class ReviewCreate(BaseModel):
    isbn: str
    content: str
    emotion: list[str] = []
    liked: list[str] = []
    disliked: list[str] = []


class ReviewUpdate(BaseModel):
    # 어떤 책에 대한 기록인지(isbn)는 수정 대상이 아니다 — 내용만 고칠 수 있다.
    content: str
    emotion: list[str] = []
    liked: list[str] = []
    disliked: list[str] = []


class ReviewReactionRequest(BaseModel):
    reaction: Literal["like", "dislike"]
