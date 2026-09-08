from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class MarkdownChunk:
    index: int
    heading: str | None
    content: str


def parse_front_matter(markdown: str) -> tuple[dict[str, str], str]:
    lines = markdown.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, markdown

    metadata: dict[str, str] = {}
    end = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end = index
            break
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip().lower()
        value = value.strip()
        if key and value:
            metadata[key] = value

    if end is None:
        return {}, markdown
    body = "\n".join(lines[end + 1 :]).lstrip()
    return metadata, body


def extract_title(markdown: str, fallback: str) -> str:
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            title = stripped[2:].strip()
            if title:
                return title
    return fallback


def _sections(markdown: str) -> list[tuple[str | None, str]]:
    sections: list[tuple[str | None, str]] = []
    heading: str | None = None
    body: list[str] = []

    def flush() -> None:
        nonlocal body
        text = "\n".join(body).strip()
        if text:
            sections.append((heading, text))
        body = []

    for line in markdown.splitlines():
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if match:
            flush()
            heading = match.group(2).strip()
            continue
        body.append(line)

    flush()
    return sections


def _split_text(text: str, max_chars: int, overlap_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text.strip()] if text.strip() else []

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            paragraph_break = text.rfind("\n\n", start, end)
            sentence_break = text.rfind(". ", start, end)
            split_at = max(paragraph_break, sentence_break)
            if split_at > start + max_chars // 2:
                end = split_at + (2 if split_at == paragraph_break else 1)

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(end - overlap_chars, start + 1)

    return chunks


def chunk_markdown(
    markdown: str,
    *,
    max_chars: int = 1600,
    overlap_chars: int = 200,
) -> list[MarkdownChunk]:
    if max_chars < 200:
        raise ValueError("max_chars must be >= 200")
    if overlap_chars < 0 or overlap_chars >= max_chars:
        raise ValueError("overlap_chars must be >= 0 and smaller than max_chars")

    chunks: list[MarkdownChunk] = []
    for heading, body in _sections(markdown):
        for piece in _split_text(body, max_chars, overlap_chars):
            chunks.append(
                MarkdownChunk(
                    index=len(chunks),
                    heading=heading,
                    content=piece,
                )
            )

    if not chunks and markdown.strip():
        chunks.append(MarkdownChunk(index=0, heading=None, content=markdown.strip()))
    return chunks
