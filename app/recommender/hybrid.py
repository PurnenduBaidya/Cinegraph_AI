from collections import defaultdict
from app.database.neo4j import driver, NEO4J_DATABASE
from app.recommender.content_based import get_content_recommendations
from app.recommender.friend_based import get_friend_recommendations


def get_hybrid_recommendations(
    user_id: str,
    limit: int = 10,
    content_weight: float = 0.6,
    friend_weight: float = 0.4
):

    if limit < 1 or limit > 100:
        raise ValueError("Limit must be between 1 and 100")

    if content_weight < 0 or friend_weight < 0:
        raise ValueError("Weights cannot be negative")

    if content_weight + friend_weight == 0:
        raise ValueError("At least one recommendation weight must be positive")

    # Normalize weights
    total_weight = content_weight + friend_weight
    content_weight /= total_weight
    friend_weight /= total_weight

    # Get movies rated highly by the current user
    user_ratings_query = """
        MATCH (u:User {userId: $user_id})-[r:RATED]->(m:Movie)

        RETURN
            m.movieKey AS movie_key,
            r.rating AS rating

        ORDER BY r.rating DESC
    """

    with driver.session(database=NEO4J_DATABASE) as session:

        user = session.run(
            """
            MATCH (u:User {userId: $user_id})
            RETURN u.name AS name
            """,
            user_id=user_id
        ).single()

        if not user:
            return None

        records = session.run(
            user_ratings_query,
            user_id=user_id
        )

        user_ratings = [record.data() for record in records]

    # Store content-based recommendations
    content_movies = defaultdict(list)

    # Use highly rated movies as recommendation sources
    for item in user_ratings:

        if item["rating"] < 3.5:
            continue

        result = get_content_recommendations(
            item["movie_key"],
            limit=50
        )

        if not result:
            continue

        for movie in result["recommendations"]:

            movie_key = movie["movie_key"]

            # Weight content similarity using user's rating
            source_weight = float(item["rating"]) / 5.0

            content_score = (
                float(movie["similarity_percentage"])
                * source_weight
            )

            content_movies[movie_key].append({
                "movie": movie,
                "score": content_score
            })

    # Calculate aggregated content scores
    content_results = {}

    for movie_key, items in content_movies.items():

        total_score = sum(item["score"] for item in items)

        content_results[movie_key] = {
            "movie": items[0]["movie"],
            "score": total_score / len(items)
        }

    # Get friend-based recommendations
    friend_result = get_friend_recommendations(
        user_id=user_id,
        limit=100
    )

    friend_movies = {}

    if friend_result:
        for movie in friend_result["recommendations"]:

            friend_movies[movie["movie_key"]] = movie

    # Combine both recommendation sources
    all_movie_keys = (
        set(content_results.keys()) |
        set(friend_movies.keys())
    )

    hybrid_recommendations = []

    for movie_key in all_movie_keys:

        content_data = content_results.get(movie_key)
        friend_data = friend_movies.get(movie_key)

        content_score = (
            content_data["score"]
            if content_data else None
        )

        friend_score = (
            float(friend_data["recommendation_score"]) / 5.0 * 100
            if friend_data else None
        )

        # Use available scores when one source has no result
        if content_score is not None and friend_score is not None:

            final_score = (
                content_score * content_weight +
                friend_score * friend_weight
            )

        elif content_score is not None:
            final_score = content_score

        else:
            final_score = friend_score

        # Get movie information from either source
        movie_info = (
            content_data["movie"]
            if content_data
            else friend_data
        )

        hybrid_recommendations.append({
            "movie_key": movie_key,
            "title": movie_info["title"],
            "year": movie_info.get("year"),
            "imdb_rating": movie_info.get("imdb_rating"),

            "content_score": (
                round(content_score, 2)
                if content_score is not None else None
            ),

            "friend_score": (
                round(friend_score, 2)
                if friend_score is not None else None
            ),

            "hybrid_score": round(final_score, 2),

            "recommended_by": (
                friend_data.get("recommended_by", [])
                if friend_data else []
            ),

            "sources": [
                source
                for source, available in [
                    ("content_based", content_data),
                    ("friend_based", friend_data)
                ]
                if available is not None
            ]
        })

    # Sort by final recommendation score
    hybrid_recommendations.sort(
        key=lambda x: x["hybrid_score"],
        reverse=True
    )

    return {
        "user_id": user_id,
        "user_name": user["name"],
        "total_recommendations": min(
            len(hybrid_recommendations), limit
        ),
        "recommendations": hybrid_recommendations[:limit]
    }
