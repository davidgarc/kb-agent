import hashlib
import re
from pathlib import Path

from kb_agent.ingestion.normalizers import NormalizedDependency, NormalizedDocChunk
from kb_agent.retrieval.embeddings import DeterministicEmbeddingProvider


SECTION_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
DEPENDENCY_HINTS = {
    "database": re.compile(r"\b([a-z0-9-]+-db(?:-[a-z0-9]+)?)\b", re.IGNORECASE),
    "queue": re.compile(r"\b([a-z0-9-]+-events(?:-[a-z0-9]+)?)\b", re.IGNORECASE),
    "REST API": re.compile(r"\b([a-z0-9-]+-api)\b", re.IGNORECASE),
    "external SaaS": re.compile(r"\b([A-Z][A-Za-z]+Pay Gateway)\b"),
}


def load_markdown_docs(root: Path, embedder: DeterministicEmbeddingProvider) -> tuple[list[NormalizedDocChunk], list[NormalizedDependency]]:
    chunks: list[NormalizedDocChunk] = []
    dependencies: dict[str, NormalizedDependency] = {}
    for app_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        app_id = app_dir.name.upper()
        for file_path in sorted(app_dir.glob("*.md")):
            file_chunks = _chunk_markdown(file_path, app_id, embedder)
            chunks.extend(file_chunks)
            for chunk in file_chunks:
                for kind, pattern in DEPENDENCY_HINTS.items():
                    for match in pattern.findall(chunk.text):
                        name = match.strip()
                        dependency_id = f"dep-{_slug(name)}"
                        dependencies.setdefault(
                            dependency_id,
                            NormalizedDependency(
                                dependency_id=dependency_id,
                                app_id=app_id,
                                name=name,
                                kind=kind,
                                direction="downstream",
                                source_ref=f"{file_path}:{chunk.heading_path}",
                            ),
                        )
    return chunks, list(dependencies.values())


def _chunk_markdown(file_path: Path, app_id: str, embedder: DeterministicEmbeddingProvider) -> list[NormalizedDocChunk]:
    lines = file_path.read_text(encoding="utf-8").splitlines()
    current_headings: list[tuple[int, str]] = []
    sections: list[tuple[str, list[str], int]] = []
    section_lines: list[str] = []
    heading_path = "Document"
    start_line = 1

    for index, line in enumerate(lines, start=1):
        match = SECTION_PATTERN.match(line)
        if match:
            if section_lines:
                sections.append((heading_path, section_lines, start_line))
            level = len(match.group(1))
            title = match.group(2).strip()
            current_headings = [(lvl, text) for lvl, text in current_headings if lvl < level]
            current_headings.append((level, title))
            heading_path = " > ".join(text for _, text in current_headings)
            section_lines = [line]
            start_line = index
        else:
            section_lines.append(line)
    if section_lines:
        sections.append((heading_path, section_lines, start_line))

    chunks: list[NormalizedDocChunk] = []
    for heading, body_lines, line_number in sections:
        body = "\n".join(body_lines).strip()
        if not body:
            continue
        for part_index, text in enumerate(_split_long_section(body), start=1):
            fingerprint = hashlib.sha1(f"{app_id}:{file_path}:{heading}:{part_index}:{text}".encode("utf-8")).hexdigest()[:16]
            chunk_id = f"doc-{app_id}-{fingerprint}"
            chunks.append(
                NormalizedDocChunk(
                    chunk_id=chunk_id,
                    app_id=app_id,
                    source_file=str(file_path),
                    heading_path=f"{heading} (line {line_number}, part {part_index})",
                    text=text,
                    source_type="docs",
                    embedding=embedder.embed_query(text),
                )
            )
    return chunks


def _split_long_section(text: str, max_words: int = 180) -> list[str]:
    words = text.split()
    if len(words) <= max_words:
        return [text]
    parts = []
    for index in range(0, len(words), max_words):
        parts.append(" ".join(words[index : index + max_words]))
    return parts


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
