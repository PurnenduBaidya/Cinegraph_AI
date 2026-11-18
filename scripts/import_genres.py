
import pandas as pd
from pathlib import Path

from app.database.neo4j import driver, NEO4J_DATABASE


# =====================================
# PATH CONFIGURATION
# =====================================

ROOT_DIR = Path(__file__).resolve().parents[1]

INTEGRATED_DIR = (
    ROOT_DIR / "data" / "processed" / "integrated"
)

GENRES_FILE = INTEGRATED_DIR / "genres.csv"
MOVIE_GENRES_FILE = INTEGRATED_DIR / "movie_genres.csv"

BATCH_SIZE = 1000


# =====================================
# CREATE CONSTRAINTS
# =====================================

def create_constraints(session):

    query = """
    CREATE CONSTRAINT genre_id_unique IF NOT EXISTS
    FOR (g:Genre)
    REQUIRE g.genreId IS UNIQUE
    """

    session.run(query).consume()

    print("Genre constraint created successfully!")


# =====================================
# IMPORT GENRE NODES
# =====================================

def import_genres(session):

    query = """

    UNWIND $rows AS row

    MERGE (g:Genre {
        genreId: row.genreId
    })

    SET
        g.name = row.name

    RETURN count(g) AS count

    """

    # Read genres CSV
    df = pd.read_csv(
        GENRES_FILE,
        dtype=str,
        keep_default_na=False
    )

    # Remove invalid records
    df = df[
        (df["genreId"].str.strip() != "") &
        (df["name"].str.strip() != "")
    ]

    # Remove duplicate genre IDs
    df = df.drop_duplicates(
        subset=["genreId"],
        keep="first"
    )

    total = 0

    # Batch processing
    for start in range(0, len(df), BATCH_SIZE):

        batch_df = df.iloc[start:start + BATCH_SIZE]

        batch = batch_df.to_dict(orient="records")

        result = session.run(
            query,
            rows=batch
        ).single()

        total += result["count"]

        print(f"Genres processed: {total}")

    print(f"\nTotal genres processed: {total}")


# =====================================
# IMPORT MOVIE-GENRE RELATIONSHIPS
# =====================================

def import_movie_genres(session):

    query = """

    UNWIND $rows AS row

    MATCH (m:Movie {
        movieKey: row.movieKey
    })

    MATCH (g:Genre {
        genreId: row.genreId
    })

    MERGE (m)-[:HAS_GENRE]->(g)

    RETURN count(*) AS count

    """

    # Read movie-genres CSV
    df = pd.read_csv(
        MOVIE_GENRES_FILE,
        dtype=str,
        keep_default_na=False
    )

    # Remove invalid records
    df = df[
        (df["movieKey"].str.strip() != "") &
        (df["genreId"].str.strip() != "")
    ]

    # Remove duplicate relationships
    df = df.drop_duplicates(
        subset=["movieKey", "genreId"],
        keep="first"
    )

    total = 0

    # Batch processing
    for start in range(0, len(df), BATCH_SIZE):

        batch_df = df.iloc[start:start + BATCH_SIZE]

        batch = batch_df.to_dict(orient="records")

        result = session.run(
            query,
            rows=batch
        ).single()

        total += result["count"]

        print(
            f"Movie-Genre relationships processed: {total}"
        )

    print(f"\nTotal Movie-Genre relationships: {total}")


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

            print("\nImporting Genre nodes...")

            import_genres(session)

            print("\nImporting Movie-Genre relationships...")

            import_movie_genres(session)

        print("\nGenre graph imported successfully!")

    finally:

        driver.close()


if __name__ == "__main__":
    main()
