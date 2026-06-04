# Application Troubleshooting Knowledge Agent

Ask source-grounded troubleshooting questions by application ID.

Try:

- What are the most likely causes of APP001 checkout latency?
- Which dependencies could impact APP001 if the database is degraded?
- Do the architecture docs and deployed manifest disagree?
- Give me an executive incident briefing for APP001.

The Chainlit app is a thin desktop UI. FastAPI owns ingestion, retrieval, graph access, and agent orchestration.
