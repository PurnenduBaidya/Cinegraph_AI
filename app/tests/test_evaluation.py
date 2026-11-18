from app.recommender.content_based import get_content_recommendations

from app.recommender.evaluation import (
    precision_at_k,
    recall_at_k,
    f1_score,
    ndcg_at_k
)


# Movie used as the recommendation source
MOVIE_KEY = "tt0468569"  # The Dark Knight

# Number of recommendations to evaluate
K = 5

# Manually selected relevant movies
# Review these independently for The Dark Knight.
RELEVANT_MOVIES = [
    "tt1345836",  # The Dark Knight Rises
    "tt0372784",  # Batman Begins
    "tt0133093",  # The Matrix
    "tt0110912"   # Pulp Fiction
]


def test_content_recommendations():

    # Get actual recommendations from Neo4j
    result = get_content_recommendations(
        movie_key=MOVIE_KEY,
        limit=K
    )

    if result is None:
        print("Source movie not found.")
        return

    # Extract movie keys from recommendation results
    recommended_movies = [
        movie["movie_key"]
        for movie in result["recommendations"]
    ]

    print("\nRecommended Movie Details:")

    for index, movie in enumerate(result["recommendations"], start=1):

        print(f"\n{index}. {movie['title']}")

        print(f"   Movie Key: {movie['movie_key']}")
        print(f"   Year: {movie.get('year')}")
        print(f"   IMDb Rating: {movie.get('imdb_rating')}")
        print(f"   Similarity: {movie.get('similarity_percentage')}%")

        print(f"   Genre Overlap: {movie.get('genre_overlap')}")
        print(f"   Actor Overlap: {movie.get('actor_overlap')}")
        print(f"   Director Overlap: {movie.get('director_overlap')}")

    # Calculate evaluation metrics
    precision = precision_at_k(
        recommended_movies,
        RELEVANT_MOVIES,
        K
    )

    recall = recall_at_k(
        recommended_movies,
        RELEVANT_MOVIES,
        K
    )

    f1 = f1_score(precision, recall)

    ndcg = ndcg_at_k(
        recommended_movies,
        RELEVANT_MOVIES,
        K
    )

    print("\nContent-Based Recommendation Evaluation")

    print(f"Source Movie: {MOVIE_KEY}")
    print(f"Recommendations: {recommended_movies}")

    print(f"\nPrecision@{K}: {precision:.2%}")
    print(f"Recall@{K}: {recall:.2%}")
    print(f"F1-score: {f1:.2%}")
    print(f"NDCG@{K}: {ndcg:.2%}")


if __name__ == "__main__":
    test_content_recommendations()
