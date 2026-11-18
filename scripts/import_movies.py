import pandas as pd
from pathlib import Path

from app.database.neo4j import driver, NEO4J_DATABASE


# =====================================
# PATH CONFIGURATION
# =====================================

ROOT_DIR = Path(__file__).resolve().parents[1]

MOVIE_FILE = (
    ROOT_DIR / "data" / "processed" /
    "integrated" / "movies.csv"
)

BATCH_SIZE = 1000


# =====================================
# CREATE CONSTRAINTS
# =====================================

def create_constraints(session):

    queries = [

        """
        CREATE CONSTRAINT movie_key_unique IF NOT EXISTS
        FOR (m:Movie)
        REQUIRE m.movieKey IS UNIQUE
        """

    ]

    for query in queries:
        session.run(query).consume()

    print("Movie constraints created successfully!")


# =====================================
# IMPORT MOVIES
# =====================================

def import_movies(session):

    query = """

    UNWIND $rows AS row

    MERGE (m:Movie {movieKey: row.movieKey})

    SET
        m.imdbId = nullif(row.tconst, ''),
        m.movieId = toInteger(nullif(row.movieId, '')),
        m.source = row.source,
        m.title = row.title,
        m.originalTitle = row.originalTitle,
        m.year = toInteger(nullif(row.year, '')),
        m.runtime = toInteger(nullif(row.runtime, '')),
        m.genres = row.genres,
        m.imdbRating = toFloat(nullif(row.imdbRating, '')),
        m.imdbVotes = toInteger(nullif(row.imdbVotes, ''))

    RETURN count(m) AS count

    """

    # Read CSV using Pandas
    df = pd.read_csv(
        MOVIE_FILE,
        dtype=str,
        keep_default_na=False
    )

    # Remove rows without movieKey
    df = df[df["movieKey"].str.strip() != ""]

    # Remove duplicate movieKey records
    df = df.drop_duplicates(
        subset=["movieKey"],
        keep="first"
    )

    total = 0

    # Process data in batches
    for start in range(0, len(df), BATCH_SIZE):

        batch_df = df.iloc[start:start + BATCH_SIZE]

        batch = batch_df.to_dict(orient="records")

        result = session.run(
            query,
            rows=batch
        ).single()

        total += result["count"]

        print(f"Movies processed: {total}")

    print(f"\nTotal movies processed: {total}")


# =====================================
# MAIN
# =====================================

def main():

    print("Connecting to Neo4j...")

    try:

        driver.verify_connectivity()

        print("Neo4j connection successful!")

        with driver.session(
            database=NEO4J_DATABASE
        ) as session:

            create_constraints(session)

            import_movies(session)

        print("\nMovie import completed successfully!")

    finally:

        driver.close()


if __name__ == "__main__":
    main()
