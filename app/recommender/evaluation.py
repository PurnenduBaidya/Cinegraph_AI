def precision_at_k(recommended_movies, relevant_movies, k=10):

    if k <= 0:
        raise ValueError("k must be greater than 0")
    
    recommended = recommended_movies[:k]
    if not recommended:
        return 0.0

    relevant_count = len(
        set(recommended) & set(relevant_movies)
    )

    return relevant_count / len(recommended)

def recall_at_k(recommended_movies, relevant_movies, k=10):

    if k <= 0:
        raise ValueError("k must be greater than 0")

    relevant_movies = set(relevant_movies)

    if not relevant_movies:
        return 0.0

    recommended = set(recommended_movies[:k])

    relevant_count = len(
        recommended & relevant_movies
    )

    return relevant_count / len(relevant_movies)


def f1_score(precision, recall):

    if precision + recall == 0:
        return 0.0

    return (
        2 * precision * recall
    ) / (precision + recall)


import math


def ndcg_at_k(recommended_movies, relevant_movies, k=10):

    if k <= 0:
        raise ValueError("k must be greater than 0")

    if not relevant_movies:
        return 0.0

    recommended = recommended_movies[:k]

    # Calculate DCG
    dcg = 0.0

    for i, movie in enumerate(recommended):

        if movie in relevant_movies:
            relevance = 1
        else:
            relevance = 0

        dcg += relevance / math.log2(i + 2)

    # Calculate ideal DCG
    ideal_relevant_count = min(len(relevant_movies), k)

    idcg = sum(
        1 / math.log2(i + 2)
        for i in range(ideal_relevant_count)
    )

    if idcg == 0:
        return 0.0

    return dcg / idcg

