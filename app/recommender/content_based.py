from app.database.neo4j import driver, NEO4J_DATABASE

def get_content_recommendations(movie_key: str, limit: int = 10):

    check_query = """
    MATCH (m:Movie {movieKey: $movie_key})
    RETURN m.title AS title
    """

    recommendation_query = """
        MATCH (source:Movie {movieKey: $movie_key})
        MATCH (candidate:Movie)
        WHERE candidate <> source

        // Count all movies for actor rarity calculation
        CALL () {
            MATCH (m:Movie)
            RETURN count(m) AS total_movies
        }

        WITH source, candidate, total_movies,

            [(source)-[:HAS_GENRE]->(g:Genre) | g] AS source_genres,
            [(candidate)-[:HAS_GENRE]->(g:Genre) | g] AS candidate_genres,

            [(source)-[:HAS_ACTOR]->(p:Person) | p] AS source_actors,
            [(candidate)-[:HAS_ACTOR]->(p:Person) | p] AS candidate_actors,

            [(source)-[:DIRECTED_BY]->(d:Person) | d] AS source_directors,
            [(candidate)-[:DIRECTED_BY]->(d:Person) | d] AS candidate_directors

        WITH source, candidate, total_movies,
            source_genres, candidate_genres,
            source_actors, candidate_actors,
            source_directors, candidate_directors,

            [g IN source_genres WHERE g IN candidate_genres] AS shared_genres,
            [p IN source_actors WHERE p IN candidate_actors] AS shared_actors,
            [d IN source_directors WHERE d IN candidate_directors] AS shared_directors

        WITH source, candidate, total_movies,
            source_genres, candidate_genres,
            source_actors, candidate_actors,
            source_directors, candidate_directors,
            shared_genres, shared_actors, shared_directors,

            // Genre Jaccard similarity
            CASE
                WHEN size(source_genres) + size(candidate_genres) - size(shared_genres) = 0
                THEN 0.0
                ELSE toFloat(size(shared_genres)) /
                    (size(source_genres) + size(candidate_genres) - size(shared_genres))
            END AS genre_similarity,

            // IDF weight of all source actors
            reduce(total = 0.0, p IN source_actors |
                total + log(
                    1.0 + toFloat(total_movies) /
                    size([(p)<-[:HAS_ACTOR]-(m:Movie) | m])
                )
            ) AS source_actor_weight,

            // IDF weight of all candidate actors
            reduce(total = 0.0, p IN candidate_actors |
                total + log(
                    1.0 + toFloat(total_movies) /
                    size([(p)<-[:HAS_ACTOR]-(m:Movie) | m])
                )
            ) AS candidate_actor_weight,

            // IDF weight of shared actors
            reduce(total = 0.0, p IN shared_actors |
                total + log(
                    1.0 + toFloat(total_movies) /
                    size([(p)<-[:HAS_ACTOR]-(m:Movie) | m])
                )
            ) AS shared_actor_weight,

            // Director Jaccard similarity
            CASE
                WHEN size(source_directors) + size(candidate_directors) - size(shared_directors) = 0
                THEN 0.0
                ELSE toFloat(size(shared_directors)) /
                    (size(source_directors) + size(candidate_directors) - size(shared_directors))
            END AS director_similarity

        WITH source, candidate,
            shared_genres, shared_actors, shared_directors,
            genre_similarity, director_similarity,
            source_actor_weight,
            candidate_actor_weight,
            shared_actor_weight,

            // IDF-weighted actor Jaccard similarity
            CASE
                WHEN source_actor_weight + candidate_actor_weight - shared_actor_weight = 0
                THEN 0.0
                ELSE shared_actor_weight /
                    (source_actor_weight + candidate_actor_weight - shared_actor_weight)
            END AS actor_similarity

        WITH candidate,
            size(shared_genres) AS genre_overlap,
            size(shared_actors) AS actor_overlap,
            size(shared_directors) AS director_overlap,
            genre_similarity,
            actor_similarity,
            director_similarity,

            (
                genre_similarity * 0.5 +
                actor_similarity * 0.3 +
                director_similarity * 0.2
            ) AS similarity_score

        // Keep your existing candidate filter
        WHERE similarity_score > 0
        AND (
            actor_overlap >= 2
            OR director_overlap > 0
        )

        RETURN
            candidate.movieKey AS movie_key,
            candidate.title AS title,
            candidate.year AS year,
            candidate.imdbRating AS imdb_rating,
            genre_overlap,
            actor_overlap,
            director_overlap,
            round(genre_similarity * 100, 2) AS genre_similarity_percentage,
            round(actor_similarity * 100, 2) AS actor_similarity_percentage,
            round(similarity_score * 100, 2) AS similarity_percentage

        ORDER BY similarity_score DESC, imdb_rating DESC
        LIMIT $limit
    """

    with driver.session(database=NEO4J_DATABASE) as session:

        movie = session.run(
            check_query,
            movie_key=movie_key
        ).single()

        if not movie:
            return None

        records = session.run(
            recommendation_query,
            movie_key=movie_key,
            limit=limit
        )

        recommendations = [
            record.data()
            for record in records
        ]

    return {
        "movie_key": movie_key,
        "movie_title": movie["title"],
        "total_recommendations": len(recommendations),
        "recommendations": recommendations
    }
