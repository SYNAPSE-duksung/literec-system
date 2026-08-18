from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import auth, books, events, recommendations, reviews, users

app = FastAPI(title="LiteRec API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(books.router)
app.include_router(reviews.router)
app.include_router(recommendations.router)
app.include_router(events.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
