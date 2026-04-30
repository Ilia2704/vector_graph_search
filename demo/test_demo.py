import unittest

from demo.run_demo import (
    run_graph_search,
    run_vector_search,
    seed_neo4j,
    seed_qdrant,
    wait_for_neo4j,
    wait_for_qdrant,
)


class DemoIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            cls.qdrant_client = wait_for_qdrant(timeout_seconds=5)
            cls.neo4j_driver = wait_for_neo4j(timeout_seconds=5)
        except RuntimeError as exc:
            raise unittest.SkipTest(str(exc))

        seed_qdrant(cls.qdrant_client)
        seed_neo4j(cls.neo4j_driver)

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "neo4j_driver"):
            cls.neo4j_driver.close()

    def test_vector_search_picks_the_wrong_person(self) -> None:
        vector_result = run_vector_search(self.qdrant_client, limit=5)
        self.assertEqual(vector_result["naive_answer"], "Bob")

    def test_graph_search_recovers_the_connected_path(self) -> None:
        graph_result = run_graph_search(self.neo4j_driver)
        self.assertEqual(graph_result["answer"], "Carol")
        self.assertEqual(graph_result["matches"][0]["project"], "KnowledgeGraph")


if __name__ == "__main__":
    unittest.main()
