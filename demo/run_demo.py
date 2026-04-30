from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from qdrant_client import QdrantClient, models


TARIFF_COLLECTION = "case_9_tariff_negation"
SERVICE_COLLECTION = "case_4_service_alias"


@dataclass(frozen=True)
class DemoDocument:
    point_id: int
    text: str
    vector: list[float]
    payload: dict[str, Any]


@dataclass(frozen=True)
class SearchHit:
    score: float
    payload: dict[str, Any]


class SimpleKnowledgeGraph:
    """
    Minimal directed graph for lecture demo.

    Stores triples:

        source -[relation]-> target

    It is intentionally simple, so students can clearly see
    what graph search does before Qdrant search.
    """

    def __init__(self) -> None:
        self.nodes: dict[str, dict[str, Any]] = {}
        self.edges: list[tuple[str, str, str]] = []

    def add_node(self, node_id: str, **attrs: Any) -> None:
        self.nodes[node_id] = dict(attrs)

    def add_edge(self, source: str, target: str, relation: str) -> None:
        if source not in self.nodes:
            self.add_node(source)

        if target not in self.nodes:
            self.add_node(target)

        self.edges.append((source, relation, target))

    def nodes_by_type(self, node_type: str) -> set[str]:
        return {
            node_id
            for node_id, attrs in self.nodes.items()
            if attrs.get("type") == node_type
        }

    def predecessors(self, target: str, relation: str | None = None) -> set[str]:
        return {
            source
            for source, edge_relation, edge_target in self.edges
            if edge_target == target
            and (relation is None or edge_relation == relation)
        }


def create_local_qdrant() -> QdrantClient:
    return QdrantClient(":memory:")


def recreate_collection(
    client: QdrantClient,
    collection_name: str,
    vector_size: int,
) -> None:
    if client.collection_exists(collection_name):
        client.delete_collection(collection_name)

    client.create_collection(
        collection_name=collection_name,
        vectors_config=models.VectorParams(
            size=vector_size,
            distance=models.Distance.COSINE,
        ),
    )


def upload_documents(
    client: QdrantClient,
    collection_name: str,
    documents: list[DemoDocument],
) -> None:
    recreate_collection(
        client=client,
        collection_name=collection_name,
        vector_size=len(documents[0].vector),
    )

    points = []

    for document in documents:
        payload = dict(document.payload)
        payload["text"] = document.text

        points.append(
            models.PointStruct(
                id=document.point_id,
                vector=document.vector,
                payload=payload,
            )
        )

    client.upsert(collection_name=collection_name, points=points)


def search(
    client: QdrantClient,
    collection_name: str,
    query_vector: list[float],
    limit: int,
    query_filter: models.Filter | None = None,
) -> list[SearchHit]:
    result = client.query_points(
        collection_name=collection_name,
        query=query_vector,
        query_filter=query_filter,
        limit=limit,
        with_payload=True,
    )

    return [
        SearchHit(
            score=point.score,
            payload=dict(point.payload or {}),
        )
        for point in result.points
    ]


def print_hits(title: str, hits: list[SearchHit]) -> None:
    print("\n" + "=" * 100)
    print(title)
    print("=" * 100)

    if not hits:
        print("No hits")
        return

    for index, hit in enumerate(hits, start=1):
        payload_without_text = {
            key: value
            for key, value in hit.payload.items()
            if key != "text"
        }

        print(f"\n#{index} | score={hit.score:.3f}")
        print(f"payload={payload_without_text}")
        print(f"text={hit.payload['text']}")


# ======================================================================================
# CASE 9
# Negation blindness:
# "Find tariffs that do NOT include mobile internet"
# ======================================================================================


def build_tariff_documents() -> list[DemoDocument]:
    return [
        DemoDocument(
            point_id=1,
            text=(
                "Тариф Базовый. Включает 100 минут звонков и SMS. "
                "Мобильный интернет в тариф не входит."
            ),
            vector=[1.0, 0.0, 0.6, 0.3, 0.0],
            payload={
                "product": "Тариф Базовый",
                "doc_type": "tariff_description",
            },
        ),
        DemoDocument(
            point_id=2,
            text=(
                "Тариф Смарт. Включает 500 минут звонков, SMS "
                "и безлимитный мобильный интернет."
            ),
            vector=[1.0, 1.0, 0.6, 0.1, 0.0],
            payload={
                "product": "Тариф Смарт",
                "doc_type": "tariff_description",
            },
        ),
        DemoDocument(
            point_id=3,
            text=(
                "Тариф Премиум. Включает мобильный интернет в роуминге, "
                "1000 минут и приоритетную поддержку."
            ),
            vector=[1.0, 1.0, 0.4, 0.9, 0.0],
            payload={
                "product": "Тариф Премиум",
                "doc_type": "tariff_description",
            },
        ),
    ]


def build_tariff_graph() -> SimpleKnowledgeGraph:
    graph = SimpleKnowledgeGraph()

    graph.add_node("Тариф Базовый", type="Product")
    graph.add_node("Тариф Смарт", type="Product")
    graph.add_node("Тариф Премиум", type="Product")
    graph.add_node("Мобильный интернет", type="Feature")

    graph.add_edge("Тариф Смарт", "Мобильный интернет", relation="INCLUDES")
    graph.add_edge("Тариф Премиум", "Мобильный интернет", relation="INCLUDES")

    return graph


def products_without_feature(
    graph: SimpleKnowledgeGraph,
    feature: str,
) -> set[str]:
    all_products = graph.nodes_by_type("Product")
    products_with_feature = graph.predecessors(
        target=feature,
        relation="INCLUDES",
    )

    return all_products - products_with_feature


def product_filter(products: set[str]) -> models.Filter:
    return models.Filter(
        should=[
            models.FieldCondition(
                key="product",
                match=models.MatchValue(value=product),
            )
            for product in sorted(products)
        ]
    )


def run_case_9(client: QdrantClient) -> dict[str, Any]:
    documents = build_tariff_documents()
    upload_documents(
        client=client,
        collection_name=TARIFF_COLLECTION,
        documents=documents,
    )

    query_text = "Посоветуй тарифы, которые строго НЕ включают мобильный интернет."

    # Artificial query vector for deterministic demo.
    # It is intentionally close to texts that mention mobile internet.
    query_vector = [1.0, 1.0, 0.2, 0.0, 0.0]

    naive_hits = search(
        client=client,
        collection_name=TARIFF_COLLECTION,
        query_vector=query_vector,
        limit=3,
    )

    graph = build_tariff_graph()

    products_with_mobile_internet = graph.predecessors(
        target="Мобильный интернет",
        relation="INCLUDES",
    )

    allowed_products = products_without_feature(
        graph=graph,
        feature="Мобильный интернет",
    )

    graph_hits = search(
        client=client,
        collection_name=TARIFF_COLLECTION,
        query_vector=query_vector,
        limit=3,
        query_filter=product_filter(allowed_products),
    )

    return {
        "query_text": query_text,
        "naive_hits": naive_hits,
        "products_with_mobile_internet": products_with_mobile_internet,
        "allowed_products": allowed_products,
        "graph_hits": graph_hits,
    }


# ======================================================================================
# CASE 4
# Business term vs technical service ID:
# "Шлюз Госуслуг" -> "esia-bridge-prod"
# ======================================================================================


def build_service_documents() -> list[DemoDocument]:
    return [
        DemoDocument(
            point_id=101,
            text=(
                "[Runbook] Если Шлюз Госуслуг недоступен, проверьте "
                "интеграционный backend и дежурную команду platform-oncall."
            ),
            vector=[1.0, 0.6, 0.0, 0.2, 0.0],
            payload={
                "doc_type": "runbook",
                "business_term": "Шлюз Госуслуг",
                "service_id": None,
            },
        ),
        DemoDocument(
            point_id=102,
            text=(
                "[CMDB] Микросервис esia-bridge-prod реализует бизнес-сервис "
                "'Шлюз Госуслуг'."
            ),
            vector=[1.0, 0.1, 0.6, 0.0, 0.0],
            payload={
                "doc_type": "cmdb",
                "business_term": "Шлюз Госуслуг",
                "service_id": "esia-bridge-prod",
            },
        ),
        DemoDocument(
            point_id=103,
            text=(
                "[DevOps Log] Service: esia-bridge-prod. Status: CRITICAL. "
                "Metric: 5xx_ratio_percent = 15 during the last 5 minutes."
            ),
            vector=[0.0, 1.0, 1.0, 1.0, 0.0],
            payload={
                "doc_type": "devops_log",
                "business_term": None,
                "service_id": "esia-bridge-prod",
                "5xx_ratio_percent": 15,
            },
        ),
        DemoDocument(
            point_id=104,
            text=(
                "[DevOps Log] Service: kafka-billing-consumer. Status: HEALTHY. "
                "Metric: consumer_lag = 0."
            ),
            vector=[0.0, 0.3, 0.0, 1.0, 1.0],
            payload={
                "doc_type": "devops_log",
                "business_term": None,
                "service_id": "kafka-billing-consumer",
                "consumer_lag": 0,
            },
        ),
    ]


def build_service_graph() -> SimpleKnowledgeGraph:
    graph = SimpleKnowledgeGraph()

    graph.add_node("Шлюз Госуслуг", type="BusinessService")
    graph.add_node("esia-bridge-prod", type="TechnicalService")

    graph.add_edge(
        source="esia-bridge-prod",
        target="Шлюз Госуслуг",
        relation="IMPLEMENTS",
    )

    return graph


def technical_services_for_business_term(
    graph: SimpleKnowledgeGraph,
    business_term: str,
) -> set[str]:
    candidate_services = graph.predecessors(
        target=business_term,
        relation="IMPLEMENTS",
    )

    return {
        service
        for service in candidate_services
        if graph.nodes.get(service, {}).get("type") == "TechnicalService"
    }


def service_log_filter(service_ids: set[str]) -> models.Filter:
    return models.Filter(
        must=[
            models.FieldCondition(
                key="doc_type",
                match=models.MatchValue(value="devops_log"),
            ),
        ],
        should=[
            models.FieldCondition(
                key="service_id",
                match=models.MatchValue(value=service_id),
            )
            for service_id in sorted(service_ids)
        ],
    )


def run_case_4(client: QdrantClient) -> dict[str, Any]:
    documents = build_service_documents()
    upload_documents(
        client=client,
        collection_name=SERVICE_COLLECTION,
        documents=documents,
    )

    query_text = "Какой сейчас error rate у Шлюза Госуслуг?"

    # Artificial query vector for deterministic demo.
    # It is close to business docs, not to the technical log.
    query_vector = [1.0, 1.0, 0.0, 0.2, 0.0]

    naive_hits = search(
        client=client,
        collection_name=SERVICE_COLLECTION,
        query_vector=query_vector,
        limit=2,
    )

    graph = build_service_graph()

    service_ids = technical_services_for_business_term(
        graph=graph,
        business_term="Шлюз Госуслуг",
    )

    graph_hits = search(
        client=client,
        collection_name=SERVICE_COLLECTION,
        query_vector=query_vector,
        limit=3,
        query_filter=service_log_filter(service_ids),
    )

    return {
        "query_text": query_text,
        "naive_hits": naive_hits,
        "service_ids": service_ids,
        "graph_hits": graph_hits,
    }


def main() -> None:
    client = create_local_qdrant()

    print("\nDEMO: Qdrant vector search vs graph-augmented retrieval")
    print("No LLM is used. The demo isolates retrieval behavior.\n")

    case_9 = run_case_9(client)

    print("CASE 9: Negation blindness")
    print(f"Query: {case_9['query_text']}")

    print_hits(
        title="Naive Qdrant vector search",
        hits=case_9["naive_hits"],
    )

    print("\nGraph search operation:")
    print(
        "predecessors("
        "target='Мобильный интернет', "
        "relation='INCLUDES'"
        ")"
    )
    print(
        "Products WITH mobile internet:",
        sorted(case_9["products_with_mobile_internet"]),
    )
    print(
        "Allowed products = all products - products with mobile internet:",
        sorted(case_9["allowed_products"]),
    )

    print_hits(
        title="Graph-filtered Qdrant search",
        hits=case_9["graph_hits"],
    )

    print(
        "\nTakeaway: vector search found texts about mobile internet; "
        "the graph enforced the business rule 'without this feature'."
    )

    case_4 = run_case_4(client)

    print("\n\nCASE 4: Business term vs technical service ID")
    print(f"Query: {case_4['query_text']}")

    print_hits(
        title="Naive Qdrant vector search",
        hits=case_4["naive_hits"],
    )

    print("\nGraph search operation:")
    print(
        "predecessors("
        "target='Шлюз Госуслуг', "
        "relation='IMPLEMENTS'"
        ")"
    )
    print(
        "Graph-resolved technical service IDs:",
        sorted(case_4["service_ids"]),
    )

    print_hits(
        title="Graph-filtered Qdrant search",
        hits=case_4["graph_hits"],
    )

    print(
        "\nTakeaway: the graph mapped the business term to the technical ID; "
        "Qdrant then searched the correct operational log slice."
    )


if __name__ == "__main__":
    main()