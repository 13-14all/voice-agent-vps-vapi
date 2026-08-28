"""
Per-business knowledge retrieval over Postgres+pgvector. Each business gets a
`knowledge_namespace` (e.g. kb_plumbing, kb_salon, kb_personal) so one table
serves every tenant with row-level isolation instead of N separate DBs.
"""
import os
import psycopg
from app.knowledge.ingest.embed import embed_text


def retrieve_context(namespace: str, query: str, top_k: int = 4) -> str:
    query_vec = embed_text(query)
    with psycopg.connect(os.environ["POSTGRES_URL"]) as conn:
        rows = conn.execute(
            """
            SELECT content FROM knowledge_chunks
            WHERE namespace = %s
            ORDER BY embedding <-> %s
            LIMIT %s
            """,
            (namespace, query_vec, top_k),
        ).fetchall()
    return "\n---\n".join(r[0] for r in rows)
