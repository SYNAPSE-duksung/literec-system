from pydantic import BaseModel


class UserProfileOut(BaseModel):
    userId: str
    preferredEmotions: list[str]
    avoidedTraits: list[str]


class UserProfileUpdate(BaseModel):
    preferredEmotions: list[str] | None = None
    avoidedTraits: list[str] | None = None
