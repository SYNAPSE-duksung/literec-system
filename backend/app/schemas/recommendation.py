from pydantic import BaseModel


class RecommendationOut(BaseModel):
    bookId: str
    hookLine: str
    matchedTrait: str
    explanation: str


class SimilarReviewRecommendationOut(BaseModel):
    sourceReviewId: str
    bookId: str
    matchedReviewSnippet: str
    similarityReason: str
