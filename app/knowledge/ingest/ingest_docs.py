"""
CLI: chunk + embed a business's source documents (FAQ, pricing, policies,
service area, call scripts) into its knowledge namespace.

Usage:
    python -m app.knowledge.ingest.ingest_docs \\
        --business kb_plumbing --path config/businesses/docs/plumbing/
"""
import argparse
import os
import psycopg
from pathlib import Path

from app.knowledge.ingest.embed import embed_text

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    chunks, start = [], 0
    while start < len(text):
        chunks.append(text[start:start + size])
        start += size - overlap
    return chunks


def ingest(business_namespace: str, source_dir: Path, source_type: str = "doc") -> int:
    inserted = 0
    with psycopg.connect(os.environ["POSTGRES_URL"]) as conn:
        for file in source_dir.glob("**/*.*"):
            if file.suffix not in (".txt", ".md"):
                continue
            for chunk in chunk_text(file.read_text(errors="ignore")):
                vec = embed_text(chunk)
                conn.execute(
                    """
                    INSERT INTO knowledge_chunks
                        (namespace, content, embedding, source_file, source_type)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (business_namespace, chunk, vec, str(file), source_type),
                )
                inserted += 1
        conn.commit()
    return inserted


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--business", required=True, help="knowledge namespace, e.g. kb_plumbing")
    parser.add_argument("--path", required=True, help="directory of source docs")
    parser.add_argument("--type", default="doc")
    args = parser.parse_args()
    count = ingest(args.business, Path(args.path), args.type)
    print(f"Ingested {count} chunks into {args.business}")
