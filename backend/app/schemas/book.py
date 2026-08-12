from typing import Literal

from pydantic import BaseModel


class IdentityVector(BaseModel):
    trait: str
    score: float
    keywords: list[str]


class BookOut(BaseModel):
    id: str
    title: str
    author: str
    publisher: str
    coverUrl: str | None
    synopsis: str | None
    identityVectors: list[IdentityVector]


class BookReactionRequest(BaseModel):
    reaction: Literal["like", "dislike"]


class BookReactionsOut(BaseModel):
    likedBookIds: list[str]
    dislikedBookIds: list[str]
