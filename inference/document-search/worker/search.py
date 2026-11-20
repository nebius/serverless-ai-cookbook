"""Rank saved, normalized passage vectors against a normalized query."""
import re

QUERY_INSTRUCTION = "Given a question, retrieve relevant passages from the document collection that answer it"


def semantic_rank(records: list[dict], query: list[float], top_k: int) -> list[dict]:
    fields = ("id", "source", "chunk_index", "text", "source_url", "title")
    results = []
    for record in records:
        vector = record["vector"]
        if len(query) != len(vector):
            raise ValueError("Query and document embedding dimensions differ")
        score = sum(a * b for a, b in zip(query, vector))
        result = {key: record[key] for key in fields if key in record}
        result["similarity"] = max(-1.0, min(1.0, score))
        results.append(result)
    matches = sorted(results, key=lambda record: (-record["similarity"], record["id"]))[:top_k]
    for match in matches:
        # IDs use one-based lines in the pinned JSONL. The viewer uses zero-based rows.
        line = re.fullmatch(r"dolly-context-L([0-9]+)", match.get("source", ""))
        if line:
            row = int(line[1]) - 1
            match["viewer_url"] = f"https://huggingface.co/datasets/databricks/databricks-dolly-15k/viewer/default/train?row={row}"
    return matches
