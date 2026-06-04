from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable

from kb_agent.settings import Settings


class Neo4jClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_username, settings.neo4j_password),
        )

    def verify(self) -> bool:
        try:
            self.driver.verify_connectivity()
        except ServiceUnavailable:
            return False
        return True

    def close(self) -> None:
        self.driver.close()

