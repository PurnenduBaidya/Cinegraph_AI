from app.database.neo4j import driver, NEO4J_DATABASE

def get_collaborative_recommendations(user_id: str, limit: int = 10):

    check_query = """
    MATCH (u:User {userId: $user_id})
    RETURN u.name AS name
    """

    recommendation_query = """
    MATCH (target_user:User {userId: $user_id})-[:RATED]->(target_movie:Movie)
    WITH target_user, collect(target_movie) AS target_movies

    MATCH (other_user:User)-[:RATED]->(other_movie:Movie)
    WHERE other_user <> target_user AND NOT other_movie IN target_movies

    WITH target_user, other_user, other_movie,
         size([
             (target_user)-[:RATED]->(target_movie)<-[:RATED]-(other_user)
             | target_movie
         ]) AS common_movies_count

    WHERE common_movies_count > 0

    RETURN
        other_movie.movieKey AS movie_key,
        other_movie.title AS title,
        other_movie.year AS year,
        other_movie.imdbRating AS imdb_rating,
        common_movies_count

    ORDER BY common_movies_count DESC, imdb_rating DESC
    LIMIT $limit
    """

    with driver.session(database=NEO4J_DATABASE) as session:

        user = session.run(
            check_query,
            user_id=user_id
        ).single()

        if not user:
            raise ValueError(f"User with ID '{user_id}' not found.")

        recommendations = session.run(
            recommendation_query,
            user_id=user_id,
            limit=limit
        )

        recommended_movies = [record.data() for record in recommendations]

    return recommended_movies