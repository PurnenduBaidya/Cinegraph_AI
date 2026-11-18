
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

PEOPLE_FILE = INTEGRATED_DIR / "people.csv"
MOVIE_PEOPLE_FILE = INTEGRATED_DIR / "movie_people.csv"

BATCH_SIZE = 1000


# =====================================
# CREATE CONSTRAINTS
# =====================================

def create_constraints(session):

    query = """
    CREATE CONSTRAINT person_id_unique IF NOT EXISTS
    FOR (p:Person)
    REQUIRE p.personId IS UNIQUE
    """

    session.run(query).consume()

    print("Person constraint created successfully!")


# =====================================
# IMPORT PEOPLE
# =====================================

def import_people(session):

    query = """

    UNWIND $rows AS row

    MERGE (p:Person {
        personId: row.personId
    })

    SET
        p.name = row.name,
        p.birthYear = toInteger(nullif(row.birthYear, '')),
        p.deathYear = toInteger(nullif(row.deathYear, ''))

    RETURN count(p) AS count

    """

    # Read people CSV
    df = pd.read_csv(
        PEOPLE_FILE,
        dtype=str,
        keep_default_na=False
    )

    # Remove empty IDs
    df = df[df["personId"].str.strip() != ""]

    # Remove duplicate people
    df = df.drop_duplicates(
        subset=["personId"],
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

        print(f"People processed: {total}")

    print(f"\nTotal people processed: {total}")


# =====================================
# IMPORT ACTORS
# =====================================

def import_actors(session, rows):

    query = """

    UNWIND $rows AS row

    MATCH (m:Movie {
        movieKey: row.movieKey
    })

    MATCH (p:Person {
        personId: row.personId
    })

    MERGE (m)-[:HAS_ACTOR]->(p)

    RETURN count(*) AS count

    """

    result = session.run(
        query,
        rows=rows
    ).single()

    return result["count"]


# =====================================
# IMPORT DIRECTORS
# =====================================

def import_directors(session, rows):

    query = """

    UNWIND $rows AS row

    MATCH (m:Movie {
        movieKey: row.movieKey
    })

    MATCH (p:Person {
        personId: row.personId
    })

    MERGE (m)-[:DIRECTED_BY]->(p)

    RETURN count(*) AS count

    """

    result = session.run(
        query,
        rows=rows
    ).single()

    return result["count"]


# =====================================
# IMPORT MOVIE-PEOPLE RELATIONSHIPS
# =====================================

def import_movie_people(session):

    # Read relationship CSV
    df = pd.read_csv(
        MOVIE_PEOPLE_FILE,
        dtype=str,
        keep_default_na=False
    )

    # Remove invalid rows
    df = df[
        (df["movieKey"].str.strip() != "") &
        (df["personId"].str.strip() != "") &
        (df["role"].str.strip() != "")
    ]

    # Remove duplicate relationships
    df = df.drop_duplicates(
        subset=["movieKey", "personId", "role"],
        keep="first"
    )

    # Normalize role names
    df["role"] = df["role"].str.strip().str.lower()

    # Separate actors and directors
    actors_df = df[df["role"] == "actor"]

    directors_df = df[df["role"] == "director"]

    total_actors = 0
    total_directors = 0

    # Import actor relationships
    for start in range(0, len(actors_df), BATCH_SIZE):

        batch_df = actors_df.iloc[start:start + BATCH_SIZE]

        batch = batch_df.to_dict(orient="records")

        total_actors += import_actors(session, batch)

        print(f"Actor relationships processed: {total_actors}")

    # Import director relationships
    for start in range(0, len(directors_df), BATCH_SIZE):

        batch_df = directors_df.iloc[start:start + BATCH_SIZE]

        batch = batch_df.to_dict(orient="records")

        total_directors += import_directors(session, batch)

        print(f"Director relationships processed: {total_directors}")

    print("\nActor relationships:", total_actors)

    print("Director relationships:", total_directors)


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

            print("\nImporting Person nodes...")

            import_people(session)

            print("\nImporting Movie-Person relationships...")

            import_movie_people(session)

        print("\nPerson graph imported successfully!")

    finally:

        driver.close()


if __name__ == "__main__":
    main()
