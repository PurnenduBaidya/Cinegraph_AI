import csv
from pathlib import Path
import re
import unicodedata


# =====================================
# PATH CONFIGURATION
# =====================================

ROOT_DIR = Path(__file__).resolve().parents[1]

IMDB_DIR = ROOT_DIR / "data" / "processed" / "imdb"
INDIA_DIR = ROOT_DIR / "data" / "processed" / "india"

OUTPUT_DIR = ROOT_DIR / "data" / "processed" / "integrated"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# =====================================
# CSV READER
# =====================================

def read_csv(path):

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    with open(
        path,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as file:

        return list(csv.DictReader(file))


# =====================================
# CSV WRITER
# =====================================

def write_csv(filename, records, fields):

    path = OUTPUT_DIR / filename

    with open(
        path,
        "w",
        encoding="utf-8",
        newline=""
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fields,
            extrasaction="ignore"
        )

        writer.writeheader()
        writer.writerows(records)

    print(f"Saved: {path}")


# =====================================
# HELPER FUNCTIONS
# =====================================

def clean(value):

    if value is None:
        return ""

    return str(value).strip()


def normalize_name(name):

    if not name:
        return ""

    name = unicodedata.normalize("NFKD", name)

    name = "".join(
        char for char in name
        if not unicodedata.combining(char)
    )

    return " ".join(name.casefold().split())


def normalize_genre(genre):

    return normalize_name(genre)


def split_genres(value):

    if not value:
        return []

    return [
        genre.strip()
        for genre in value.split(",")
        if genre.strip()
    ]


def first_nonempty(*values):

    for value in values:

        value = clean(value)

        if value:
            return value

    return ""


# =====================================
# READ ALL SOURCE DATASETS
# =====================================

print("\nLoading source datasets...")

imdb_movies = read_csv(IMDB_DIR / "movies.csv")
india_movies = read_csv(INDIA_DIR / "movies.csv")

imdb_people = read_csv(IMDB_DIR / "people.csv")
india_people = read_csv(INDIA_DIR / "people.csv")

imdb_movie_people = read_csv(
    IMDB_DIR / "movie_people.csv"
)

india_movie_people = read_csv(
    INDIA_DIR / "movie_people.csv"
)

print("IMDb movies:", len(imdb_movies))
print("IMDb India movies:", len(india_movies))

print("IMDb people:", len(imdb_people))
print("IMDb India people:", len(india_people))


# =====================================
# 1. INTEGRATE MOVIES
# =====================================

print("\nIntegrating movies...")

movies = {}

# Maps IMDb tconst to canonical movieKey
imdb_movie_key_map = {}

# Maps Indian movieKey to canonical movieKey
india_movie_key_map = {}


def add_movie(row, source, movie_key, tconst=""):

    if movie_key not in movies:

        movies[movie_key] = {
            "movieKey": movie_key,
            "tconst": tconst,
            "movieId": "",
            "title": "",
            "originalTitle": "",
            "year": "",
            "runtime": "",
            "genres": "",
            "imdbRating": "",
            "imdbVotes": "",
            "_sources": set()
        }

    movie = movies[movie_key]

    movie["_sources"].add(source)

    # Keep the first nonempty value.
    # IMDb is imported first, so its values have priority.

    for field in [
        "title",
        "originalTitle",
        "year",
        "runtime",
        "genres",
        "imdbRating",
        "imdbVotes",
        "movieId"
    ]:

        movie[field] = first_nonempty(
            movie[field],
            row.get(field)
        )

    if tconst:
        movie["tconst"] = tconst

    return movie


# -------------------------------------
# IMPORT IMDb MOVIES
# -------------------------------------

print("\nImporting IMDb movies...")

for row in imdb_movies:

    tconst = clean(row.get("tconst"))

    if not tconst:
        continue

    # One movie node per IMDb ID
    movie_key = tconst

    imdb_movie_key_map[tconst] = movie_key

    add_movie(
        row=row,
        source="imdb",
        movie_key=movie_key,
        tconst=tconst
    )


# -------------------------------------
# IMPORT IMDb INDIA MOVIES
# -------------------------------------

print("\nIntegrating IMDb India movies...")

matched_india = 0
unmatched_india = 0

for row in india_movies:

    india_key = clean(row.get("movieKey"))
    tconst = clean(row.get("tconst"))

    if not india_key:
        continue

    # If tconst exists, reuse the IMDb movie identity.
    # Otherwise, use the independent Indian movieKey.

    if tconst:

        movie_key = tconst

        matched_india += 1

    else:

        movie_key = india_key

        unmatched_india += 1

    india_movie_key_map[india_key] = movie_key

    add_movie(
        row=row,
        source="imdb_india",
        movie_key=movie_key,
        tconst=tconst
    )


# -------------------------------------
# EXPORT MOVIES
# -------------------------------------

movie_fields = [
    "movieKey",
    "tconst",
    "movieId",
    "source",
    "title",
    "originalTitle",
    "year",
    "runtime",
    "genres",
    "imdbRating",
    "imdbVotes"
]

movie_records = []

for movie in movies.values():

    record = movie.copy()

    record["source"] = ",".join(
        sorted(movie["_sources"])
    )

    del record["_sources"]

    movie_records.append(record)


write_csv(
    "movies.csv",
    movie_records,
    movie_fields
)

print("\nMovie integration summary")
print("-" * 40)

print("IMDb movies:", len(imdb_movies))
print("IMDb India movies:", len(india_movies))
print("Indian movies with tconst:", matched_india)
print("Indian movies without tconst:", unmatched_india)
print("Integrated unique movies:", len(movie_records))



# =====================================
# 2. INTEGRATE PEOPLE USING IMDb nconst
# =====================================

print("\nIntegrating people using IMDb nconst...")

people = {}

imdb_person_key_map = {}
india_person_key_map = {}


# -------------------------------------
# BUILD IMDb PERSON LOOKUP
# -------------------------------------

imdb_people_by_id = {
    clean(row.get("personId")): row
    for row in imdb_people
    if clean(row.get("personId"))
}


# -------------------------------------
# BUILD IMDb MOVIE-PERSON INDEX
# -------------------------------------

# Key:
# (movieKey, role, normalized person name)
#
# Value:
# Set of IMDb nconst IDs

imdb_credit_index = {}

for row in imdb_movie_people:

    tconst = clean(row.get("tconst"))
    person_id = clean(row.get("personId"))
    role = clean(row.get("role")).casefold()

    movie_key = imdb_movie_key_map.get(tconst)

    person = imdb_people_by_id.get(person_id)

    if not movie_key or not person:
        continue

    if role not in ["actor", "director"]:
        continue

    name = normalize_name(clean(person.get("name")))

    if not name:
        continue

    key = (movie_key, role, name)

    imdb_credit_index.setdefault(key, set()).add(person_id)


print("IMDb person-credit index:", len(imdb_credit_index))


# -------------------------------------
# FIND IMDb IDs FOR INDIA PEOPLE
# -------------------------------------

india_people_by_id = {
    clean(row.get("personId")): row
    for row in india_people
    if clean(row.get("personId"))
}

india_match_candidates = {}

for row in india_movie_people:

    india_movie_key = clean(row.get("movieKey"))
    india_person_id = clean(row.get("personId"))
    role = clean(row.get("role")).casefold()

    movie_key = india_movie_key_map.get(india_movie_key)

    person = india_people_by_id.get(india_person_id)

    if not movie_key or not person:
        continue

    if role not in ["actor", "director"]:
        continue

    name = normalize_name(clean(person.get("name")))

    if not name:
        continue

    key = (movie_key, role, name)

    candidates = imdb_credit_index.get(key, set())

    if candidates:

        india_match_candidates.setdefault(
            india_person_id, set()
        ).update(candidates)


# Only accept a match when exactly one IMDb nconst
# is identified for that Indian person.

india_person_matches = {}

for india_person_id, candidates in india_match_candidates.items():

    if len(candidates) == 1:

        india_person_matches[india_person_id] = next(
            iter(candidates)
        )


print(
    "IMDb India people matched to IMDb:",
    len(india_person_matches)
)

print(
    "IMDb India people without reliable match:",
    len(india_people) - len(india_person_matches)
)


# -------------------------------------
# ADD CANONICAL PEOPLE
# -------------------------------------

def add_person(person_id, row, source):

    name = clean(row.get("name"))

    if not person_id or not name:
        return ""

    if person_id not in people:

        people[person_id] = {
            "personId": person_id,
            "name": name,
            "birthYear": clean(row.get("birthYear")),
            "deathYear": clean(row.get("deathYear")),
            "_sources": set()
        }

    person = people[person_id]

    person["_sources"].add(source)

    person["birthYear"] = first_nonempty(
        person["birthYear"],
        row.get("birthYear")
    )

    person["deathYear"] = first_nonempty(
        person["deathYear"],
        row.get("deathYear")
    )

    return person_id


# -------------------------------------
# IMPORT IMDb PEOPLE
# -------------------------------------

for row in imdb_people:

    original_id = clean(row.get("personId"))

    if not original_id:
        continue

    # IMDb nconst is the canonical person ID.
    person_key = add_person(
        original_id,
        row,
        "imdb"
    )

    if person_key:

        imdb_person_key_map[original_id] = person_key


# -------------------------------------
# IMPORT IMDb INDIA PEOPLE
# -------------------------------------

for row in india_people:

    original_id = clean(row.get("personId"))

    if not original_id:
        continue

    # Use IMDb nconst when a reliable match exists.
    # Otherwise retain the India-specific ID.

    if original_id in india_person_matches:

        person_key = india_person_matches[original_id]

    else:

        person_key = f"imdb_india:{original_id}"

    canonical_id = add_person(
        person_key,
        row,
        "imdb_india"
    )

    if canonical_id:

        india_person_key_map[original_id] = canonical_id


# -------------------------------------
# EXPORT PEOPLE
# -------------------------------------

people_records = []

for person in people.values():

    record = person.copy()

    record["source"] = ",".join(
        sorted(person["_sources"])
    )

    del record["_sources"]

    people_records.append(record)


people_fields = [
    "personId",
    "name",
    "birthYear",
    "deathYear",
    "source"
]

write_csv(
    "people.csv",
    people_records,
    people_fields
)

print("Integrated unique people:", len(people_records))


# =====================================
# 3. INTEGRATE GENRES
# =====================================

print("\nIntegrating genres...")

genres = {}
movie_genres = []

genre_relationship_keys = set()


def add_movie_genres(movie_key, genre_string):

    for genre_name in split_genres(genre_string):

        genre_key = normalize_genre(genre_name)

        if not genre_key:
            continue

        if genre_key not in genres:

            genres[genre_key] = {
                "genreId": genre_key,
                "name": genre_name
            }

        relationship = (
            movie_key,
            genre_key
        )

        if relationship in genre_relationship_keys:
            continue

        movie_genres.append({
            "movieKey": movie_key,
            "genreId": genre_key
        })

        genre_relationship_keys.add(relationship)


for movie in movie_records:

    add_movie_genres(
        movie["movieKey"],
        movie["genres"]
    )


genre_records = list(genres.values())

genre_fields = [
    "genreId",
    "name"
]

movie_genre_fields = [
    "movieKey",
    "genreId"
]

write_csv(
    "genres.csv",
    genre_records,
    genre_fields
)

write_csv(
    "movie_genres.csv",
    movie_genres,
    movie_genre_fields
)

print("Unique genres:", len(genre_records))
print("Movie-genre relationships:", len(movie_genres))


# =====================================
# 4. INTEGRATE MOVIE-PEOPLE RELATIONSHIPS
# =====================================

print("\nIntegrating movie-person relationships...")

movie_people = []

relationship_keys = set()


def add_movie_person(movie_key, person_id, role):

    if not movie_key or not person_id or not role:
        return

    # Do not create relationships to missing nodes.

    if movie_key not in movies:
        return

    if person_id not in people:
        return

    role = role.strip().casefold()

    if role not in ["actor", "director"]:
        return

    relationship = (
        movie_key,
        person_id,
        role
    )

    if relationship in relationship_keys:
        return

    movie_people.append({
        "movieKey": movie_key,
        "personId": person_id,
        "role": role
    })

    relationship_keys.add(relationship)


# -------------------------------------
# IMDb RELATIONSHIPS
# -------------------------------------

for row in imdb_movie_people:

    tconst = clean(row.get("tconst"))
    original_person_id = clean(row.get("personId"))

    movie_key = imdb_movie_key_map.get(tconst)

    person_id = imdb_person_key_map.get(
        original_person_id
    )

    add_movie_person(
        movie_key,
        person_id,
        row.get("role")
    )


# -------------------------------------
# IMDb INDIA RELATIONSHIPS
# -------------------------------------

for row in india_movie_people:

    india_key = clean(row.get("movieKey"))
    original_person_id = clean(row.get("personId"))

    movie_key = india_movie_key_map.get(india_key)

    person_id = india_person_key_map.get(
        original_person_id
    )

    add_movie_person(
        movie_key,
        person_id,
        row.get("role")
    )


movie_people_fields = [
    "movieKey",
    "personId",
    "role"
]

write_csv(
    "movie_people.csv",
    movie_people,
    movie_people_fields
)

print("Unique movie-person relationships:", len(movie_people))


# =====================================
# 5. FINAL VALIDATION
# =====================================

print("\n" + "=" * 55)
print("INTEGRATION COMPLETED")
print("=" * 55)

# Movie validation
duplicate_movie_keys = len(movie_records) - len({
    row["movieKey"] for row in movie_records
})

duplicate_tconsts = len([
    row["tconst"]
    for row in movie_records
    if row["tconst"]
]) - len({
    row["tconst"]
    for row in movie_records
    if row["tconst"]
})

# People validation
duplicate_person_ids = len(people_records) - len({
    row["personId"] for row in people_records
})

# Genre validation
duplicate_genre_ids = len(genre_records) - len({
    row["genreId"] for row in genre_records
})

# Relationship validation
duplicate_movie_people = len(movie_people) - len({
    (
        row["movieKey"],
        row["personId"],
        row["role"]
    )
    for row in movie_people
})

duplicate_movie_genres = len(movie_genres) - len({
    (
        row["movieKey"],
        row["genreId"]
    )
    for row in movie_genres
})

print("\nFINAL COUNTS")

print("Movies:", len(movie_records))
print("People:", len(people_records))
print("Genres:", len(genre_records))
print("Movie-People relationships:", len(movie_people))
print("Movie-Genre relationships:", len(movie_genres))

print("\nDUPLICATE VALIDATION")

print("Duplicate movieKey:", duplicate_movie_keys)
print("Duplicate tconst:", duplicate_tconsts)
print("Duplicate personId:", duplicate_person_ids)
print("Duplicate genreId:", duplicate_genre_ids)
print("Duplicate movie-person relationships:", duplicate_movie_people)
print("Duplicate movie-genre relationships:", duplicate_movie_genres)

# Referential integrity
invalid_movie_people = sum(
    1 for row in movie_people
    if row["movieKey"] not in movies
    or row["personId"] not in people
)

invalid_movie_genres = sum(
    1 for row in movie_genres
    if row["movieKey"] not in movies
    or row["genreId"] not in genres
)

print("\nREFERENCE VALIDATION")

print("Invalid movie-person references:", invalid_movie_people)
print("Invalid movie-genre references:", invalid_movie_genres)

if any([
    duplicate_movie_keys,
    duplicate_tconsts,
    duplicate_person_ids,
    duplicate_genre_ids,
    duplicate_movie_people,
    duplicate_movie_genres,
    invalid_movie_people,
    invalid_movie_genres
]):

    raise ValueError(
        "Validation failed! Check the integrated datasets."
    )

print("\nAll duplicate and reference checks passed!")

print("\nOutput directory:", OUTPUT_DIR)
