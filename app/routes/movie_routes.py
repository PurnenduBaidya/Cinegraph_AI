from fastapi import APIRouter, HTTPException
from app.database.neo4j import driver, NEO4J_DATABASE
from app.recommender.content_based import get_content_recommendations

router = APIRouter(
    prefix="/movies",
    tags=["Movies"]
)

@router.get("/")
def get_all_movies(limit: int = 20):

    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=400,
            detail="Limit must be between 1 and 100"
        )

    query = """
    MATCH (m:Movie)
    RETURN
        m.movieKey AS movie_key,
        m.title AS title,
        m.year AS year,
        m.imdbRating AS imdb_rating
    ORDER BY rand()
    LIMIT $limit
    """

    with driver.session(database=NEO4J_DATABASE) as session:
        records = session.run(
            query,
            limit=limit
        )

        movies = [record.data() for record in records]

    return {
        "total": len(movies),
        "movies": movies
    }


@router.get("/{movie_key}")
def get_movie(movie_key: str):
    query = """
    MATCH (m:Movie {movieKey: $movie_key})
    RETURN
        m.movieKey AS movie_key,
        m.title AS title,
        m.year AS year,
        m.runtime AS runtime,
        m.imdbRating AS imdb_rating,
        m.imdbVotes AS imdb_votes
    """
    with driver.session(database=NEO4J_DATABASE) as session:

        record = session.run(
            query,
            movie_key=movie_key
        ).single()

    if not record:
        raise HTTPException(
            status_code=404,
            detail="Movie not found"
        )

    return record.data()

@router.get("/{movie_key}/recommendations")
def get_recommendations(movie_key: str, limit: int = 10):
    if limit < 1 or limit > 50:
        raise HTTPException(
            status_code=400,
            detail="Limit must be between 1 and 50"
        )

    recommendations = get_content_recommendations(
        movie_key=movie_key,
        limit=limit
    )

    if not recommendations:
        raise HTTPException(
            status_code=404,
            detail="Movie not found or no recommendations available"
        )

    return recommendations