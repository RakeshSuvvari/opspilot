from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KnowledgeHit:
    title: str
    source_path: str
    document_type: str
    service: str | None
    chunk_index: int
    heading: str | None
    content: str
    similarity: float

    def as_dict(self) -> dict[str, object]:
        return {
            "title": self.title,
            "source_path": self.source_path,
            "document_type": self.document_type,
            "service": self.service,
            "chunk_index": self.chunk_index,
            "heading": self.heading,
            "content": self.content,
            "similarity": round(self.similarity, 4),
        }
