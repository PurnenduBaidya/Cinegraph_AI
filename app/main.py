from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from app.routes.movie_routes import router as movie_router
from app.routes.ai_routes import router as ai_router
# python -m uvicorn app.main:app --reload

from app.database.neo4j import (
    verify_connection,
    close_connection
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting CineGraph AI service...")
    yield
    print("Closing Neo4j connection...")
    close_connection()

app = FastAPI(
    title="CineGraph AI",
    description="AI-powered Movie Recommendation System",
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(movie_router)
app.include_router(ai_router)

@app.get("/")
def home():
    return {
        "message": "Welcome to CineGraph AI",
        "status": "running"
    }

@app.get("/database")
def database_check():
    try:
        verify_connection()
        return {
            "status": "running",
            "database": "connected"
        }
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Neo4j connection failed"
        )