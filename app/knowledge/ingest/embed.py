"""Thin embedding wrapper so ingestion + retrieval always use the same model."""
import os
import ollama

EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")


def embed_text(text: str) -> list[float]:
    client = ollama.Client(host=os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434"))
    result = client.embeddings(model=EMBED_MODEL, prompt=text)
    return result["embedding"]
