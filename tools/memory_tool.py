"""
Vector Memory Tool using ChromaDB and Sentence-Transformers.

Provides long-term semantic memory storage, retrieval, listing, and management
for JarvisLite. Inherits from LangChain's BaseTool.
"""

import os
import uuid
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool

import chromadb
from chromadb.utils import embedding_functions


# Lazy module-level cache for embedding function and ChromaDB client
_EF_CACHE = None
_CLIENT_CACHE = None


def _get_embedding_function():
    global _EF_CACHE
    if _EF_CACHE is None:
        _EF_CACHE = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
    return _EF_CACHE


def _get_chroma_client() -> chromadb.PersistentClient:
    global _CLIENT_CACHE
    os.makedirs("memory", exist_ok=True)
    if _CLIENT_CACHE is None:
        _CLIENT_CACHE = chromadb.PersistentClient(path="memory/chroma_db")
    return _CLIENT_CACHE


def get_memory_collection():
    """
    Returns the ChromaDB collection named 'jarvis_memory'.
    Handles collection creation and existing collection lookup gracefully.
    """
    client = _get_chroma_client()
    ef = _get_embedding_function()
    try:
        collection = client.get_or_create_collection(
            name="jarvis_memory",
            embedding_function=ef
        )
    except Exception:
        collection = client.get_collection(
            name="jarvis_memory",
            embedding_function=ef
        )
    return client, collection


class MemoryInput(BaseModel):
    action: str = Field(description="Action to perform: 'save', 'recall', 'list', or 'clear'.")
    content: str = Field(default="", description="Content to save or search query for recall.")
    topic: str = Field(default="general", description="Category label like 'personal', 'work', 'general'.")


class MemoryTool(BaseTool):
    name: str = "memory"
    description: str = (
        "Saves and recalls information across conversations using semantic vector search. "
        "action must be one of: save, recall, list, clear. "
        "content is what to save or search for. "
        "topic is a category label like 'personal', 'work', 'general'."
    )
    args_schema: type[BaseModel] = MemoryInput

    def _run(self, action: str, content: str = "", topic: str = "general") -> str:
        """
        Executes the memory action: save, recall, list, or clear.
        """
        client, collection = get_memory_collection()
        action = action.lower().strip()

        if action == "save":
            if not content:
                return "Error: No content to save."
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            entry_id = str(uuid.uuid4())
            metadata = {
                "topic": topic,
                "timestamp": timestamp,
                "content": content
            }
            collection.add(
                ids=[entry_id],
                documents=[content],
                metadatas=[metadata]
            )
            return f"Saved to memory under topic '{topic}'."

        elif action == "recall":
            if collection.count() == 0:
                return "No memories found."
            if not content:
                return "Error: No query provided for recall."

            n_results = min(5, collection.count())
            results = collection.query(
                query_texts=[content],
                n_results=n_results
            )

            docs = results.get("documents", [[]])[0]
            metas = results.get("metadatas", [[]])[0]

            if not docs:
                return f"No memories found matching '{content}'."

            result_str = f"Found {len(docs)} memories matching '{content}':\n\n"
            for doc, meta in zip(docs, metas):
                ts = meta.get("timestamp", "unknown")
                t = meta.get("topic", "general")
                result_str += f"[{ts}] {t}: {doc}\n"
            return result_str.strip()

        elif action == "list":
            if collection.count() == 0:
                return "Memory is empty."

            all_data = collection.get(include=["documents", "metadatas"])
            docs = all_data.get("documents", [])
            metas = all_data.get("metadatas", [])

            items = list(zip(docs, metas))
            # Return up to the 10 most recent entries
            recent = items[-10:]

            result_str = f"All memories ({len(items)} total):\n\n"
            for doc, meta in recent:
                ts = meta.get("timestamp", "unknown")
                t = meta.get("topic", "general")
                result_str += f"[{ts}] {t}: {doc}\n"
            return result_str.strip()

        elif action == "clear":
            try:
                client.delete_collection("jarvis_memory")
            except Exception:
                pass
            ef = _get_embedding_function()
            client.get_or_create_collection(
                name="jarvis_memory",
                embedding_function=ef
            )
            return "All memories cleared."

        return "Error: Invalid action. Use save, recall, list, or clear."