from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import os
from pathlib import Path
import time
from typing import Dict, List

from neo4j import GraphDatabase
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams


VECTOR_COLLECTION = "people_snippets"
QUERY_TEXT = "Python engineer who worked with Alice on a Neo4j project"
QUERY_VECTOR = [1.0, 1.0, 1.0, 1.0, 1.0]
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")
NEO4J_QUERY_PATH = Path(__file__).with_name("neo4j_query.cypher")


@dataclass(frozen=True)
class Snippet:
    point_id: int
    owner: str | None
    text: str
    vector: List[float]


def build_snippets() -> List[Snippet]:
    """Hand-authored, relation-blind vectors keep the demo deterministic."""
    return [
        Snippet(
            point_id=1,
            owner="Bob",
            text="Bob is a Python engineer.",
            vector=[1.0, 1.0, 0.15, 0.05, 0.05],
        ),
        Snippet(
            point_id=2,
            owner="Bob",
            text="Bob worked with Alice on BillingAI.",
            vector=[0.10, 0.10, 1.0, 0.05, 0.05],
        ),
        Snippet(
            point_id=3,
            owner="Bob",
            text="Bob built the Neo4j FraudMonitor project.",
            vector=[0.05, 0.05, 0.05, 1.0, 1.0],
        ),
        Snippet(
            point_id=4,
            owner="Carol",
            text="Carol is a Python engineer.",
            vector=[1.0, 1.0, 0.05, 0.00, 0.00],
        ),
        Snippet(
            point_id=5,
            owner="Carol",
            text="Carol worked with Alice on KnowledgeGraph.",
            vector=[0.05, 0.05, 1.0, 0.00, 0.20],
        ),
        Snippet(
            point_id=6,
            owner=None,
            text="KnowledgeGraph uses Neo4j.",
            vector=[0.00, 0.00, 0.00, 1.0, 0.20],
        ),
    ]


def create_qdrant_client() -> QdrantClient:
    return QdrantClient(url=QDRANT_URL)


def wait_for_qdrant(timeout_seconds: int = 60) -> QdrantClient:
    deadline = time.time() + timeout_seconds
    last_error = None

    while time.time() < deadline:
        client = create_qdrant_client()
        try:
            client.get_collections()
            return client
        except Exception as exc:  # pragma: no cover - network timing dependent
            last_error = exc
            time.sleep(1)

    raise RuntimeError(f"Qdrant was not ready at {QDRANT_URL}: {last_error}")


def seed_qdrant(client: QdrantClient) -> None:
    if client.collection_exists(VECTOR_COLLECTION):
        client.delete_collection(VECTOR_COLLECTION)

    client.create_collection(
        collection_name=VECTOR_COLLECTION,
        vectors_config=VectorParams(size=len(QUERY_VECTOR), distance=Distance.COSINE),
    )
    client.upsert(
        collection_name=VECTOR_COLLECTION,
        points=[
            PointStruct(
                id=snippet.point_id,
                vector=snippet.vector,
                payload={"owner": snippet.owner, "text": snippet.text},
            )
            for snippet in build_snippets()
        ],
    )


def run_vector_search(client: QdrantClient, limit: int = 5) -> Dict[str, object]:
    hits = client.query_points(
        collection_name=VECTOR_COLLECTION,
        query=QUERY_VECTOR,
        limit=limit,
        with_payload=True,
    ).points

    candidate_scores: Dict[str, float] = defaultdict(float)
    readable_hits = []

    for hit in hits:
        owner = hit.payload.get("owner")
        text = hit.payload["text"]
        if owner:
            candidate_scores[owner] += hit.score

        readable_hits.append(
            {
                "owner": owner or "project fact",
                "score": round(hit.score, 3),
                "text": text,
            }
        )

    ranking = sorted(candidate_scores.items(), key=lambda item: item[1], reverse=True)
    naive_answer = ranking[0][0] if ranking else None

    return {
        "query": QUERY_TEXT,
        "hits": readable_hits,
        "candidate_scores": [(name, round(score, 3)) for name, score in ranking],
        "naive_answer": naive_answer,
    }


def create_neo4j_driver():
    return GraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USER, NEO4J_PASSWORD),
    )


def wait_for_neo4j(timeout_seconds: int = 60):
    deadline = time.time() + timeout_seconds
    last_error = None

    while time.time() < deadline:
        driver = create_neo4j_driver()
        try:
            driver.verify_connectivity()
            return driver
        except Exception as exc:  # pragma: no cover - network timing dependent
            last_error = exc
            driver.close()
            time.sleep(1)

    raise RuntimeError(f"Neo4j was not ready at {NEO4J_URI}: {last_error}")


def seed_neo4j(driver) -> None:
    people = ["Alice", "Bob", "Carol"]
    projects = ["BillingAI", "FraudMonitor", "KnowledgeGraph"]
    skills = ["Python"]
    technologies = ["Neo4j", "Postgres"]
    worked_on = [
        {"person": "Alice", "project": "BillingAI"},
        {"person": "Alice", "project": "KnowledgeGraph"},
        {"person": "Bob", "project": "BillingAI"},
        {"person": "Bob", "project": "FraudMonitor"},
        {"person": "Carol", "project": "KnowledgeGraph"},
    ]
    has_skill = [
        {"person": "Bob", "skill": "Python"},
        {"person": "Carol", "skill": "Python"},
    ]
    uses = [
        {"project": "BillingAI", "technology": "Postgres"},
        {"project": "FraudMonitor", "technology": "Neo4j"},
        {"project": "KnowledgeGraph", "technology": "Neo4j"},
    ]

    with driver.session(database=NEO4J_DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n").consume()

        session.run(
            "UNWIND $people AS name MERGE (:Person {name: name})",
            people=people,
        ).consume()
        session.run(
            "UNWIND $projects AS name MERGE (:Project {name: name})",
            projects=projects,
        ).consume()
        session.run(
            "UNWIND $skills AS name MERGE (:Skill {name: name})",
            skills=skills,
        ).consume()
        session.run(
            "UNWIND $technologies AS name MERGE (:Technology {name: name})",
            technologies=technologies,
        ).consume()
        session.run(
            """
            UNWIND $worked_on AS row
            MATCH (person:Person {name: row.person})
            MATCH (project:Project {name: row.project})
            MERGE (person)-[:WORKED_ON]->(project)
            """,
            worked_on=worked_on,
        ).consume()
        session.run(
            """
            UNWIND $has_skill AS row
            MATCH (person:Person {name: row.person})
            MATCH (skill:Skill {name: row.skill})
            MERGE (person)-[:HAS_SKILL]->(skill)
            """,
            has_skill=has_skill,
        ).consume()
        session.run(
            """
            UNWIND $uses AS row
            MATCH (project:Project {name: row.project})
            MATCH (technology:Technology {name: row.technology})
            MERGE (project)-[:USES]->(technology)
            """,
            uses=uses,
        ).consume()


def load_neo4j_query() -> str:
    return NEO4J_QUERY_PATH.read_text()


def run_graph_search(driver) -> Dict[str, object]:
    query = load_neo4j_query()

    with driver.session(database=NEO4J_DATABASE) as session:
        records = session.run(query).data()

    matches = [
        {
            "candidate": record["candidate"],
            "project": record["project"],
            "proof": (
                f"{record['candidate']} -[:WORKED_ON]-> {record['project']} "
                f"<-[:WORKED_ON]- Alice and {record['project']} -[:USES]-> Neo4j"
            ),
        }
        for record in records
    ]

    return {
        "query": QUERY_TEXT,
        "matches": matches,
        "answer": matches[0]["candidate"] if matches else None,
    }


def format_vector_section(vector_result: Dict[str, object]) -> str:
    lines = [
        "1. Qdrant vector search over flattened snippets",
        f"   Query: {vector_result['query']}",
        "   Top hits:",
    ]
    for index, hit in enumerate(vector_result["hits"], start=1):
        lines.append(
            f"   {index}. {hit['score']:.3f} | {hit['owner']:<12} | {hit['text']}"
        )

    lines.append("   Aggregated person scores:")
    for name, score in vector_result["candidate_scores"]:
        lines.append(f"   - {name}: {score:.3f}")

    lines.append(f"   Naive vector-only answer: {vector_result['naive_answer']}")
    return "\n".join(lines)


def format_graph_section(graph_result: Dict[str, object]) -> str:
    lines = [
        "2. Graph traversal over explicit relations",
        f"   Query: {graph_result['query']}",
    ]

    if not graph_result["matches"]:
        lines.append("   No matches found.")
        return "\n".join(lines)

    for match in graph_result["matches"]:
        lines.append(f"   Match: {match['candidate']} on {match['project']}")
        lines.append(f"   Proof: {match['proof']}")

    lines.append(f"   Graph answer: {graph_result['answer']}")
    return "\n".join(lines)


def main() -> None:
    qdrant_client = wait_for_qdrant()
    neo4j_driver = wait_for_neo4j()

    try:
        seed_qdrant(qdrant_client)
        seed_neo4j(neo4j_driver)

        vector_result = run_vector_search(qdrant_client)
        graph_result = run_graph_search(neo4j_driver)
    finally:
        neo4j_driver.close()

    print("Demo: why graph search can beat vector-only retrieval on multi-hop queries")
    print()
    print(f"Qdrant URL: {QDRANT_URL}")
    print(f"Neo4j URI: {NEO4J_URI}")
    print()
    print(format_vector_section(vector_result))
    print()
    print(format_graph_section(graph_result))
    print()
    print("Takeaway:")
    print(
        "Vector search finds snippets that mention Python, Alice, and Neo4j, "
        "but it does not enforce that those facts belong to one connected path."
    )
    print(
        "Graph search returns Carol because it can require the exact pattern "
        "Person -> Project <- Alice and Project -> Neo4j."
    )


if __name__ == "__main__":
    main()
