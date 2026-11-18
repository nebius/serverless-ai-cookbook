"""Rank saved, normalized passage vectors against a normalized query."""
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
    return sorted(results, key=lambda record: (-record["similarity"], record["id"]))[:top_k]
