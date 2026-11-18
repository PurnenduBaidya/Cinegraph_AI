from app.recommender.evaluation import (
    precision_at_k,
    recall_at_k,
    f1_score,
    ndcg_at_k
)

# Sample recommendation results
recommended_movies = [
    "tt1375666",
    "tt0816692",
    "tt0468569",
    "tt0133093",
    "tt0110912"
]

# Manually identified relevant movies
relevant_movies = [
    "tt1375666",
    "tt0468569",
    "tt0110912",
    "tt0109830"
]


def test_evaluation():

    k = 5

    precision = precision_at_k(
        recommended_movies,
        relevant_movies,
        k
    )

    recall = recall_at_k(
        recommended_movies,
        relevant_movies,
        k
    )

    f1 = f1_score(precision, recall)

    ndcg = ndcg_at_k(
    recommended_movies,
    relevant_movies,
    k
    )

    

    print("\nRecommendation Evaluation Results")

    print(f"Precision@{k}: {precision:.2%}")
    print(f"Recall@{k}: {recall:.2%}")
    print(f"F1-score: {f1:.2%}")
    print(f"NDCG@{k}: {ndcg:.2%}")


if __name__ == "__main__":
    test_evaluation()
