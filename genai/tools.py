import json
from urllib import response
from langchain.tools import tool
from genai.llm import llm
from app.database.neo4j import driver, NEO4J_DATABASE
from app.recommender.content_based import (
    get_content_recommendations
)


@tool
def recommend_similar_movies(movie_key: str, limit: int = 5) -> str:
    """
    Find movies similar to a given movie using the Neo4j
    content-based recommendation engine.

    Args:
        movie_key: IMDb or internal movie identifier.
        limit: Number of recommendations to return.
    """

    if limit < 1 or limit > 50:
        return "Error: Limit must be between 1 and 50."

    result = get_content_recommendations(
        movie_key=movie_key,
        limit=limit
    )

    if result is None:
        return "Source movie not found."

    if not result["recommendations"]:
        return "No similar movies found."

    return json.dumps(
        result["recommendations"],
        indent=2,
        ensure_ascii=False
    )


@tool
def search_movie_by_title(title: str) -> str:
    """
    Search for movies in Neo4j using a movie title.
    Returns matching movie IDs, titles, release years and IMDb ratings.
    Useful when the user provides a movie name instead of an IMDb ID.
    """

    query = """
    MATCH (m:Movie)
    WHERE toLower(m.title) CONTAINS toLower($title)

    RETURN
        m.movieKey AS movie_key,
        m.title AS title,
        m.year AS year,
        m.imdbRating AS imdb_rating

    ORDER BY
        CASE
            WHEN toLower(m.title) = toLower($title) THEN 0
            ELSE 1
        END,
        m.year DESC

    LIMIT 10
    """

    with driver.session(database=NEO4J_DATABASE) as session:
        records = session.run(
            query,
            title=title
        )

        movies = [record.data() for record in records]

    if not movies:
        return "No movies found with that title."

    return json.dumps(
        movies,
        indent=2,
        ensure_ascii=False
    )


@tool
def get_movie_details(movie_key: str) -> str:
    """
    Get detailed information about a movie using its movie key.

    Returns the movie title, release year, runtime,
    IMDb rating and IMDb votes.
    """

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
        return "Movie not found."

    return json.dumps(
        record.data(),
        indent=2,
        ensure_ascii=False
    )


if __name__ == "__main__":
   tools=[
       recommend_similar_movies,
       search_movie_by_title,
       get_movie_details
   ]

   llm_with_tools = llm.bind_tools(tools)

   result = get_movie_details.invoke({
        "movie_key": "tt1375666"
    })

   print(result)
        
#    print("LLM Response:")
#    print(response)

#    print("\nTool Calls:")

#    for tool_call in response.tool_calls:
#         print(tool_call)
