import pandas as pd
from pathlib import Path

# ==========================================
# PATH CONFIGURATION
# ==========================================

BASE_DIR = Path("data/raw")

IMDB_DIR = BASE_DIR / "imdb"
MOVIELENS_DIR = BASE_DIR / "ml-latest-small"

OUTPUT_DIR = Path("data/processed/imdb")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ==========================================
# 1. READ MOVIELENS LINKS
# ==========================================

print("\nLoading MovieLens IMDb links...")

links = pd.read_csv(
    MOVIELENS_DIR / "links.csv",
    dtype={"movieId": str, "imdbId": str}
)

# Remove missing and invalid IMDb IDs
links = links.dropna(subset=["imdbId"])

links = links[
    (links["imdbId"] != "0") &
    (links["imdbId"] != "")
].copy()

# Convert IMDb IDs into IMDb tconst format
links["tconst"] = (
    "tt" + links["imdbId"].str.zfill(7)
)

# Create IMDb ID to MovieLens ID mapping
imdb_ids = dict(
    zip(links["tconst"], links["movieId"])
)

matched_ids = set(imdb_ids.keys())

print("Matched IMDb IDs:", len(matched_ids))


# ==========================================
# 2. READ IMDb RATINGS
# ==========================================

print("\nLoading IMDb ratings...")

ratings = pd.read_csv(
    IMDB_DIR / "title.ratings.tsv.gz",
    sep="\t",
    compression="gzip",
    na_values=r"\N",
    dtype={"tconst": str}
)

# Keep only movies present in MovieLens links
ratings = ratings[
    ratings["tconst"].isin(matched_ids)
].copy()

ratings = ratings.rename(
    columns={
        "averageRating": "imdbRating",
        "numVotes": "imdbVotes"
    }
)

ratings = ratings[
    ["tconst", "imdbRating", "imdbVotes"]
]

print("Ratings found:", len(ratings))


# ==========================================
# 3. READ IMDb MOVIE INFORMATION
# ==========================================

print("\nLoading IMDb movie information...")

basics = pd.read_csv(
    IMDB_DIR / "title.basics.tsv.gz",
    sep="\t",
    compression="gzip",
    na_values=r"\N",
    low_memory=False,
    dtype={"tconst": str}
)

# Filter matched movies
movies = basics[
    (basics["tconst"].isin(matched_ids)) &
    (basics["titleType"] == "movie")
].copy()

# Select required columns
movies = movies[
    [
        "tconst",
        "primaryTitle",
        "originalTitle",
        "startYear",
        "runtimeMinutes",
        "genres"
    ]
]

# Rename columns
movies = movies.rename(
    columns={
        "primaryTitle": "title",
        "startYear": "year",
        "runtimeMinutes": "runtime"
    }
)

# Add MovieLens movieId
movies["movieId"] = movies["tconst"].map(imdb_ids)

# Merge IMDb ratings
movies = movies.merge(
    ratings,
    on="tconst",
    how="left"
)

# Reorder columns
movies = movies[
    [
        "tconst",
        "movieId",
        "title",
        "originalTitle",
        "year",
        "runtime",
        "genres",
        "imdbRating",
        "imdbVotes"
    ]
]

print("Movies found:", len(movies))


# ==========================================
# 4. READ IMDb DIRECTORS
# ==========================================

print("\nLoading IMDb crew information...")

crew = pd.read_csv(
    IMDB_DIR / "title.crew.tsv.gz",
    sep="\t",
    compression="gzip",
    na_values=r"\N",
    dtype={"tconst": str}
)

# Keep only processed movies
crew = crew[
    crew["tconst"].isin(movies["tconst"])
].copy()

# Extract directors
directors = crew[
    ["tconst", "directors"]
].dropna()

directors["personId"] = directors["directors"].str.split(",")

directors = directors.explode("personId")

directors["role"] = "director"

directors = directors[
    ["tconst", "personId", "role"]
]


# ==========================================
# 5. READ IMDb ACTORS
# ==========================================

print("\nLoading IMDb principal cast...")

principals = pd.read_csv(
    IMDB_DIR / "title.principals.tsv.gz",
    sep="\t",
    compression="gzip",
    na_values=r"\N",
    dtype={"tconst": str, "nconst": str}
)

# Keep only processed movies and actors
actors = principals[
    (principals["tconst"].isin(movies["tconst"])) &
    (principals["category"].isin(["actor", "actress"]))
].copy()

actors = actors.rename(
    columns={"nconst": "personId"}
)

actors["role"] = "actor"

actors = actors[
    ["tconst", "personId", "role"]
]


# ==========================================
# 6. COMBINE MOVIE-PERSON RELATIONSHIPS
# ==========================================

print("\nCombining actors and directors...")

movie_people = pd.concat(
    [directors, actors],
    ignore_index=True
)

# Remove duplicate relationships
movie_people = movie_people.drop_duplicates(
    subset=["tconst", "personId", "role"]
)

person_ids = set(movie_people["personId"].dropna())

print("People IDs found:", len(person_ids))


# ==========================================
# 7. READ IMDb PEOPLE INFORMATION
# ==========================================

print("\nLoading IMDb people information...")

people = pd.read_csv(
    IMDB_DIR / "name.basics.tsv.gz",
    sep="\t",
    compression="gzip",
    na_values=r"\N",
    dtype={"nconst": str}
)

# Keep only matching actors and directors
people = people[
    people["nconst"].isin(person_ids)
].copy()

people = people[
    [
        "nconst",
        "primaryName",
        "birthYear",
        "deathYear"
    ]
]

people = people.rename(
    columns={
        "nconst": "personId",
        "primaryName": "name"
    }
)

print("People records found:", len(people))


# ==========================================
# 8. EXPORT PROCESSED DATASETS
# ==========================================

print("\nExporting processed datasets...")

movies.to_csv(
    OUTPUT_DIR / "movies.csv",
    index=False
)

people.to_csv(
    OUTPUT_DIR / "people.csv",
    index=False
)

movie_people.to_csv(
    OUTPUT_DIR / "movie_people.csv",
    index=False
)

print("\nIMDb processing completed!")

print("Total processed movies:", len(movies))
print("Total processed people:", len(people))
print("Total movie-person relationships:", len(movie_people))
