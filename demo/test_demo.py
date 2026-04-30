import unittest

from demo.run_demo import create_local_qdrant, run_case_4, run_case_9


class VectorGraphDemoTest(unittest.TestCase):
    def test_case_9_graph_filters_out_mobile_internet_tariffs(self) -> None:
        client = create_local_qdrant()
        result = run_case_9(client)

        naive_products = [
            hit.payload["product"]
            for hit in result["naive_hits"]
        ]

        graph_products = [
            hit.payload["product"]
            for hit in result["graph_hits"]
        ]

        self.assertIn("Тариф Смарт", naive_products[:2])
        self.assertIn("Тариф Премиум", naive_products[:2])

        self.assertEqual(
            result["products_with_mobile_internet"],
            {"Тариф Смарт", "Тариф Премиум"},
        )

        self.assertEqual(
            result["allowed_products"],
            {"Тариф Базовый"},
        )

        self.assertEqual(
            graph_products,
            ["Тариф Базовый"],
        )

    def test_case_4_graph_resolves_business_term_to_operational_log(self) -> None:
        client = create_local_qdrant()
        result = run_case_4(client)

        naive_doc_types = [
            hit.payload["doc_type"]
            for hit in result["naive_hits"]
        ]

        graph_doc_types = [
            hit.payload["doc_type"]
            for hit in result["graph_hits"]
        ]

        graph_service_ids = [
            hit.payload["service_id"]
            for hit in result["graph_hits"]
        ]

        self.assertNotIn("devops_log", naive_doc_types)

        self.assertEqual(
            result["service_ids"],
            {"esia-bridge-prod"},
        )

        self.assertEqual(
            graph_doc_types,
            ["devops_log"],
        )

        self.assertEqual(
            graph_service_ids,
            ["esia-bridge-prod"],
        )

        self.assertEqual(
            result["graph_hits"][0].payload["5xx_ratio_percent"],
            15,
        )


if __name__ == "__main__":
    unittest.main()