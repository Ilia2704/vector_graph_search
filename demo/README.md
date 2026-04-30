# Qdrant vs Graph Demo

This demo uses real `Qdrant` and real `Neo4j` in Docker containers and shows a very specific failure mode:

- `Qdrant` retrieves semantically relevant snippets.
- A naive vector-only aggregation picks `Bob`.
- The correct answer is `Carol`.
- A graph traversal gets `Carol` because it can enforce one connected path.

The vectors are intentionally hand-authored and relation-blind so the failure mode stays deterministic and easy to explain.

## Why the vector result is undesirable

The query is:

`Python engineer who worked with Alice on a Neo4j project`

Bob looks good to a vector index because these facts all exist somewhere in his neighborhood:

- `Bob is a Python engineer`
- `Bob worked with Alice on BillingAI`
- `Bob built the Neo4j FraudMonitor project`

But those are two different projects.

Carol is the real answer because one project satisfies the whole pattern:

- `Carol worked with Alice on KnowledgeGraph`
- `KnowledgeGraph uses Neo4j`
- `Carol is a Python engineer`

## Files

- [docker-compose.yml](/Users/newuser/Documents/OTUS/3004/vector_graph_search/demo/docker-compose.yml): starts Qdrant, Neo4j, and the demo runner
- [Dockerfile](/Users/newuser/Documents/OTUS/3004/vector_graph_search/demo/Dockerfile): tiny Python runner image
- [run_demo.py](/Users/newuser/Documents/OTUS/3004/vector_graph_search/demo/run_demo.py): runnable demo
- [test_demo.py](/Users/newuser/Documents/OTUS/3004/vector_graph_search/demo/test_demo.py): small integration test
- [neo4j_query.cypher](/Users/newuser/Documents/OTUS/3004/vector_graph_search/demo/neo4j_query.cypher): exact Cypher query used against Neo4j

## Exact sequence

Make sure Docker Desktop is running first. The first image pull can take a few minutes.

```bash
docker compose -f demo/docker-compose.yml up -d qdrant neo4j
docker compose -f demo/docker-compose.yml run --rm --build demo-runner
docker compose -f demo/docker-compose.yml run --rm demo-runner python -m unittest demo/test_demo.py
docker compose -f demo/docker-compose.yml down -v
```

What each step does:

1. Starts `Qdrant` on `http://localhost:6333` and `Neo4j` on `bolt://localhost:7687` plus the browser on `http://localhost:7474`.
2. Seeds both databases and prints the comparison.
3. Runs the small integration test against the same containers.
4. Stops everything and removes the demo data.

If you want to inspect Neo4j in the browser before cleanup:

1. Open `http://localhost:7474`
2. Sign in with username `neo4j`
3. Sign in with password `password`
4. Paste the query from [neo4j_query.cypher](/Users/newuser/Documents/OTUS/3004/vector_graph_search/demo/neo4j_query.cypher)

## Expected outcome

The vector section will rank Bob highly and the naive vector-only answer will be `Bob`.

The graph section will return:

- candidate: `Carol`
- project: `KnowledgeGraph`

## Neo4j mapping

The demo now seeds Neo4j directly and executes the exact Cypher in [neo4j_query.cypher](/Users/newuser/Documents/OTUS/3004/vector_graph_search/demo/neo4j_query.cypher). The same Python script also seeds Qdrant and runs the vector query against the live Qdrant container.
