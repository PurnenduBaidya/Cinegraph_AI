from app.database.neo4j import driver, NEO4J_DATABASE

def get_friend_recommendations(
    user_id: str,
    limit: int = 10,
    min_rating: float = 3.5,
    min_common_movies: int = 2
):

    if limit < 1 or limit > 100:
        raise ValueError("Limit must be between 1 and 100")

    if not 0.5 <= min_rating <= 5:
        raise ValueError("Minimum rating must be between 0.5 and 5")

    if min_common_movies < 1:
        raise ValueError("Minimum common movies must be at least 1")

    check_query = """
    MATCH (u:User {userId: $user_id})
    RETURN u.name AS name
    """

    recommendation_query = """

    // Find friends and compare their ratings with the current user
    MATCH (me:User {userId: $user_id})-[:FRIENDS]-(friend:User)

    MATCH (me)-[myRating:RATED]->(common:Movie)
          <-[friendRating:RATED]-(friend)

    // Calculate rating similarity between users
    WITH
        me,
        friend,
        count(common) AS common_movies,
        avg(abs(
            toFloat(myRating.rating) -
            toFloat(friendRating.rating)
        )) AS avg_difference

    WHERE common_movies >= $min_common_movies

    // Convert average rating difference into similarity
    WITH
        me,
        friend,
        common_movies,
        1.0 - (avg_difference / 4.5) AS similarity

    WHERE similarity > 0

    // Find movies liked by similar friends
    MATCH (friend)-[candidateRating:RATED]->(candidate:Movie)

    WHERE candidateRating.rating >= $min_rating

    // Exclude movies already rated by the current user
    AND NOT EXISTS {
        MATCH (me)-[:RATED]->(candidate)
    }

    // Calculate weighted recommendation score
    WITH
        candidate,
        friend,
        similarity,
        common_movies,
        toFloat(candidateRating.rating) AS friend_rating

    WITH
        candidate,
        sum(similarity * friend_rating) / sum(similarity)
            AS recommendation_score,
        count(DISTINCT friend) AS friends_who_liked,
        collect(DISTINCT friend.name) AS recommended_by,
        max(common_movies) AS common_movies

    RETURN
        candidate.movieKey AS movie_key,
        candidate.title AS title,
        candidate.year AS year,
        candidate.imdbRating AS imdb_rating,
        round(recommendation_score * 100) / 100.0
            AS recommendation_score,
        friends_who_liked,
        recommended_by,
        common_movies

    ORDER BY
        recommendation_score DESC,
        friends_who_liked DESC

    LIMIT $limit

    """

    with driver.session(database=NEO4J_DATABASE) as session:

        user = session.run(
            check_query,
            user_id=user_id
        ).single()

        if not user:
            return None

        records = session.run(
            recommendation_query,
            user_id=user_id,
            limit=limit,
            min_rating=min_rating,
            min_common_movies=min_common_movies
        )

        recommendations = [
            record.data()
            for record in records
        ]

    return {
        "user_id": user_id,
        "user_name": user["name"],
        "total_recommendations": len(recommendations),
        "recommendations": recommendations
    }
