from threading import Lock

from neo4j import GraphDatabase

from kb_agent.agent.graph_agent import GraphTroubleshootingAgent
from kb_agent.agent.tools import TroubleshootingTools
from kb_agent.graph.repositories import GraphRepository, InMemoryGraphRepository, Neo4jGraphRepository
from kb_agent.ingestion.pipeline import IngestionPipeline
from kb_agent.retrieval.embeddings import DeterministicEmbeddingProvider
from kb_agent.settings import Settings, get_settings


class AppContainer:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.embedder = DeterministicEmbeddingProvider(settings.embedding_dimensions)
        self.repository, self.graph_mode, self.neo4j_connected = self._build_repository()
        self.pipeline = IngestionPipeline(
            repository=self.repository,
            data_dir=settings.data_dir,
            embedder=self.embedder,
            embedding_dimensions=settings.embedding_dimensions,
        )
        self.tools = TroubleshootingTools(self.repository, self.embedder)
        self.agent = GraphTroubleshootingAgent(self.tools, settings)

    def _build_repository(self) -> tuple[GraphRepository, str, bool]:
        if self.settings.mock_mode:
            return InMemoryGraphRepository(), "memory", False
        try:
            driver = GraphDatabase.driver(
                self.settings.neo4j_uri,
                auth=(self.settings.neo4j_username, self.settings.neo4j_password),
            )
            driver.verify_connectivity()
            return Neo4jGraphRepository(driver, self.settings.neo4j_database), "neo4j", True
        except Exception:
            return InMemoryGraphRepository(), "memory-fallback", False


_container: AppContainer | None = None
_container_lock = Lock()


def get_container() -> AppContainer:
    global _container
    if _container is None:
        with _container_lock:
            if _container is None:
                _container = AppContainer(get_settings())
    return _container
