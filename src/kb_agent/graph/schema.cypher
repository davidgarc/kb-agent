CREATE CONSTRAINT application_app_id IF NOT EXISTS FOR (n:Application) REQUIRE n.app_id IS UNIQUE;
CREATE CONSTRAINT incident_incident_id IF NOT EXISTS FOR (n:Incident) REQUIRE n.incident_id IS UNIQUE;
CREATE CONSTRAINT component_component_id IF NOT EXISTS FOR (n:Component) REQUIRE n.component_id IS UNIQUE;
CREATE CONSTRAINT resource_resource_id IF NOT EXISTS FOR (n:InfrastructureResource) REQUIRE n.resource_id IS UNIQUE;
CREATE CONSTRAINT dependency_dependency_id IF NOT EXISTS FOR (n:Dependency) REQUIRE n.dependency_id IS UNIQUE;
CREATE CONSTRAINT doc_chunk_chunk_id IF NOT EXISTS FOR (n:DocChunk) REQUIRE n.chunk_id IS UNIQUE;
CREATE CONSTRAINT manifest_manifest_id IF NOT EXISTS FOR (n:Manifest) REQUIRE n.manifest_id IS UNIQUE;
CREATE CONSTRAINT ingestion_run_run_id IF NOT EXISTS FOR (n:IngestionRun) REQUIRE n.run_id IS UNIQUE;
CREATE FULLTEXT INDEX incident_text IF NOT EXISTS FOR (n:Incident) ON EACH [n.short_description, n.description, n.resolution_notes];
CREATE FULLTEXT INDEX docchunk_text IF NOT EXISTS FOR (n:DocChunk) ON EACH [n.text];

