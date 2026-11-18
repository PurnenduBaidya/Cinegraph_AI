from neo4j import GraphDatabase
from dotenv import load_dotenv
import os
load_dotenv()

NEO4J_URI=os.getenv("NEO4J_URI")
NEO4J_USERNAME=os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD=os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE=os.getenv("NEO4J_DATABASE")

driver = GraphDatabase.driver(
    NEO4J_URI,
    auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
)

def verify_connection():
    driver.verify_connectivity()
    print("Connection to Neo4j database verified successfully.")
    
def close_connection():
    driver.close()