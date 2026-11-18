import pandas as pd
import re
from pathlib import Path


# =====================================
# PATH CONFIGURATION
# =====================================

ROOT_DIR = Path(__file__).resolve().parents[1]

INDIA_FILE = (
    ROOT_DIR / "data" / "raw" /
    "imdb_india" / "IMDb Movies India.csv"
)

IMDB_BASICS_FILE = (
    ROOT_DIR / "data" / "raw" /
    "imdb" / "title.basics.tsv.gz"
)

OUTPUT_DIR = (
    ROOT_DIR / "data" / "processed" / "india"
)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

CHUNK_SIZE = 200000


# =====================================
# DATA CLEANING FUNCTIONS
# =====================================

def clean(value):

    if pd.isna(value):
        return ""

    value = str(value).strip()

    if value in ["nan", "None", "\\N"]:
        return ""

    return value


def clean_year(value):

    value = clean(value)

    match = re.search(r"\d{4}", value)

    return match.group(0) if match else ""


def clean_duration(value):

    value = clean(value)

    match = re.search(r"\d+", value)

    return match.group(0) if match else ""


def normalize_name(name):

    return " ".join(clean(name).casefold().split())


def normalize_title(title):

    # Normalize case and whitespace.
    # Punctuation is intentionally preserved.

    return " ".join(clean(title).casefold().split())


# =====================================
# READ IMDb INDIA DATA
# =====================================

print("\nLoading IMDb India dataset...")

india_df = pd.read_csv(
    INDIA_FILE,
    encoding="latin-1",
    low_memory=False
)

print("Original records:", len(india_df))


# =====================================
# CLEAN MOVIE INFORMATION
# =====================================

india_df["Name"] = india_df["Name"].apply(clean)

skipped_rows = (india_df["Name"] == "").sum()

india_df = india_df[
    india_df["Name"] != ""
].copy()

india_df["year"] = india_df["Year"].apply(clean_year)

india_df["runtime"] = india_df["Duration"].apply(clean_duration)

india_df["genres"] = india_df["Genre"].apply(clean)

india_df["imdbRating"] = india_df["Rating"].apply(clean)

india_df["imdbVotes"] = india_df["Votes"].apply(clean)

india_df["match_title"] = india_df["Name"].apply(normalize_title)

india_df["match_year"] = india_df["year"]

# Preserve original row order
india_df = india_df.reset_index(drop=True)

india_df["_row_order"] = range(len(india_df))

# Generate internal movie IDs
india_df["movieKey"] = [
    f"india:{i:06d}"
    for i in range(1, len(india_df) + 1)
]


# =====================================
# BUILD IMDb TITLE INDEX
# =====================================

print("\nLoading IMDb title.basics dataset...")

if not IMDB_BASICS_FILE.exists():
    raise FileNotFoundError(
        f"IMDb title.basics file not found: {IMDB_BASICS_FILE}"
    )

# Key: (normalized title, year)
# Value: IMDb IDs and their matching information

imdb_index = {}

for chunk in pd.read_csv(
    IMDB_BASICS_FILE,
    sep="\t",
    compression="gzip",
    usecols=[
        "tconst",
        "titleType",
        "primaryTitle",
        "originalTitle",
        "startYear"
    ],
    dtype=str,
    keep_default_na=False,
    chunksize=CHUNK_SIZE
):

    # Only consider movies
    chunk = chunk[
        chunk["titleType"] == "movie"
    ]

    for row in chunk.itertuples(index=False):

        tconst = clean(row.tconst)
        year = clean_year(row.startYear)

        if not tconst or not year:
            continue

        titles = [
            (row.primaryTitle, "primaryTitle"),
            (row.originalTitle, "originalTitle")
        ]

        for title, match_field in titles:

            normalized = normalize_title(title)

            if not normalized:
                continue

            key = (normalized, year)

            if key not in imdb_index:
                imdb_index[key] = {}

            # Avoid counting the same tconst twice
            # if primaryTitle and originalTitle are identical.

            if tconst not in imdb_index[key]:

                imdb_index[key][tconst] = {
                    "imdb_title": clean(title),
                    "match_field": match_field
                }

print("IMDb title index created:", len(imdb_index))


# =====================================
# MATCH INDIAN MOVIES WITH IMDb
# =====================================

print("\nMatching Indian movies with IMDb...")

matched_movies = []
ambiguous_movies = []
unmatched_movies = []

for row in india_df.to_dict("records"):

    key = (
        row["match_title"],
        row["match_year"]
    )

    candidates = imdb_index.get(key, {})

    # Exactly one IMDb match
    if len(candidates) == 1:

        tconst, match_info = next(iter(candidates.items()))

        movie = row.copy()

        movie["tconst"] = tconst
        movie["imdb_title"] = match_info["imdb_title"]
        movie["match_field"] = match_info["match_field"]

        matched_movies.append(movie)

    # Multiple IMDb matches
    elif len(candidates) > 1:

        for tconst, match_info in candidates.items():

            movie = row.copy()

            movie["tconst"] = tconst
            movie["imdb_title"] = match_info["imdb_title"]
            movie["match_field"] = match_info["match_field"]

            ambiguous_movies.append(movie)

    # No IMDb match
    else:

        movie = row.copy()

        movie["tconst"] = ""
        movie["imdb_title"] = ""
        movie["match_field"] = ""

        unmatched_movies.append(movie)


matched_df = pd.DataFrame(matched_movies)

ambiguous_df = pd.DataFrame(ambiguous_movies)

unmatched_df = pd.DataFrame(unmatched_movies)

print("Matched records:", len(matched_df))
print("Ambiguous candidate records:", len(ambiguous_df))
print("Unmatched records:", len(unmatched_df))


# =====================================
# REMOVE DUPLICATE MATCHED MOVIES
# =====================================

print("\nRemoving duplicate matched movies...")

if not matched_df.empty:

    # Prefer the Indian record with more complete information
    completeness_columns = [
        "Director",
        "Actor 1",
        "Actor 2",
        "Actor 3",
        "Genre",
        "Duration",
        "Rating",
        "Votes"
    ]

    matched_df["_completeness"] = (
        matched_df[completeness_columns]
        .apply(lambda col: col.map(clean).ne(""))
        .sum(axis=1)
    )

    matched_df = matched_df.sort_values(
        by=["_completeness", "_row_order"],
        ascending=[False, True]
    )

    # One Indian record per IMDb movie ID
    matched_df = matched_df.drop_duplicates(
        subset=["tconst"],
        keep="first"
    )

    matched_df = matched_df.sort_values("_row_order")

    matched_df = matched_df.drop(
        columns=["_completeness"]
    )

print("Unique matched movies:", len(matched_df))


# =====================================
# REMOVE DUPLICATE UNMATCHED MOVIES
# =====================================

print("\nRemoving duplicate unmatched movies...")

if not unmatched_df.empty:

    unmatched_df = unmatched_df.drop_duplicates(
        subset=["match_title", "match_year"],
        keep="first"
    )

    unmatched_df = unmatched_df.sort_values("_row_order")

print("Unique unmatched movies:", len(unmatched_df))


# =====================================
# REMOVE DUPLICATE AMBIGUOUS ENTRIES
# =====================================

if not ambiguous_df.empty:

    ambiguous_df = ambiguous_df.drop_duplicates(
        subset=["movieKey", "tconst"],
        keep="first"
    )


# =====================================
# CREATE FINAL UNIQUE MOVIE DATASET
# =====================================

print("\nCreating final movie dataset...")

# Only verified matched movies and unmatched movies
# are included in the main dataset.
# Ambiguous movies are kept separately.

movies_all = pd.concat(
    [matched_df, unmatched_df],
    ignore_index=True
)

movies_all = movies_all.sort_values(
    "_row_order"
).reset_index(drop=True)

# Select movie properties
movie_columns = [
    "movieKey",
    "source",
    "title",
    "originalTitle",
    "year",
    "runtime",
    "genres",
    "imdbRating",
    "imdbVotes",
    "tconst"
]

movies = pd.DataFrame({
    "movieKey": movies_all["movieKey"],
    "source": "imdb_india",
    "title": movies_all["Name"],
    "originalTitle": movies_all["Name"],
    "year": movies_all["year"],
    "runtime": movies_all["runtime"],
    "genres": movies_all["genres"],
    "imdbRating": movies_all["imdbRating"],
    "imdbVotes": movies_all["imdbVotes"],
    "tconst": movies_all["tconst"]
})

# Ensure no duplicate movie identities
assert movies["movieKey"].is_unique

matched_ids = movies["tconst"].loc[
    movies["tconst"] != ""
]

assert matched_ids.is_unique


# =====================================
# EXTRACT UNIQUE PEOPLE
# =====================================

print("\nProcessing actors and directors...")

people = {}

movie_people = []


def add_person(movie_key, name, role):

    name = clean(name)

    if not name:
        return

    normalized = normalize_name(name)

    if not normalized:
        return

    if normalized not in people:

        people[normalized] = {
            "name": name
        }

    movie_people.append({

        "movieKey": movie_key,

        "personKey": normalized,

        "role": role

    })


for row in movies_all.to_dict("records"):

    movie_key = row["movieKey"]

    # Director
    add_person(
        movie_key,
        row.get("Director"),
        "director"
    )

    # Actors
    for actor_column in [
        "Actor 1",
        "Actor 2",
        "Actor 3"
    ]:

        add_person(
            movie_key,
            row.get(actor_column),
            "actor"
        )


# =====================================
# CREATE PEOPLE DATAFRAME
# =====================================

people_df = pd.DataFrame(
    [
        {
            "personId": f"india_person_{i:06d}",
            "name": person["name"]
        }
        for i, person in enumerate(
            people.values(),
            start=1
        )
    ],
    columns=["personId", "name"]
)

# Map normalized person names to unique person IDs
person_id_map = {
    normalized: f"india_person_{i:06d}"
    for i, normalized in enumerate(
        people.keys(),
        start=1
    )
}


# =====================================
# CREATE UNIQUE RELATIONSHIPS
# =====================================

movie_people_df = pd.DataFrame(
    movie_people,
    columns=[
        "movieKey",
        "personKey",
        "role"
    ]
)

if not movie_people_df.empty:

    movie_people_df["personId"] = (
        movie_people_df["personKey"]
        .map(person_id_map)
    )

    movie_people_df = movie_people_df[
        [
            "movieKey",
            "personId",
            "role"
        ]
    ]

    movie_people_df = movie_people_df.drop_duplicates(
        subset=[
            "movieKey",
            "personId",
            "role"
        ]
    )

else:

    movie_people_df = pd.DataFrame(
        columns=[
            "movieKey",
            "personId",
            "role"
        ]
    )


# =====================================
# EXPORT ALL DATASETS
# =====================================

print("\nExporting processed datasets...")

matched_df.to_csv(
    OUTPUT_DIR / "matched_india_movies.csv",
    index=False,
    encoding="utf-8"
)

ambiguous_df.to_csv(
    OUTPUT_DIR / "ambiguous_india_movies.csv",
    index=False,
    encoding="utf-8"
)

unmatched_df.to_csv(
    OUTPUT_DIR / "unmatched_india_movies.csv",
    index=False,
    encoding="utf-8"
)

movies.to_csv(
    OUTPUT_DIR / "movies.csv",
    index=False,
    encoding="utf-8"
)

people_df.to_csv(
    OUTPUT_DIR / "people.csv",
    index=False,
    encoding="utf-8"
)

movie_people_df.to_csv(
    OUTPUT_DIR / "movie_people.csv",
    index=False,
    encoding="utf-8"
)


# =====================================
# FINAL VALIDATION
# =====================================

print("\n" + "=" * 45)
print("IMDb INDIA PROCESSING COMPLETED")
print("=" * 45)

print("Original records:", len(india_df) + skipped_rows)
print("Skipped records:", skipped_rows)

print("\nMatching results:")

print("Unique matched movies:", len(matched_df))
print("Ambiguous candidate records:", len(ambiguous_df))
print("Unique unmatched movies:", len(unmatched_df))

print("\nFinal datasets:")

print("Total unique movies:", len(movies))
print("Unique people:", len(people_df))
print("Unique relationships:", len(movie_people_df))

print("\nValidation:")

print("Duplicate movieKey:", movies["movieKey"].duplicated().sum())

print(
    "Duplicate matched tconst:",
    movies.loc[
        movies["tconst"] != "",
        "tconst"
    ].duplicated().sum()
)

print("Duplicate personId:", people_df["personId"].duplicated().sum())

print(
    "Duplicate relationships:",
    movie_people_df.duplicated().sum()
)

print("\nFiles saved in:", OUTPUT_DIR)
