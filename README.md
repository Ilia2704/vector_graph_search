# vector_graph_search

Local deterministic demo for the lecture:

**Knowledge-base search: where vectors fail and graphs help**

The project shows two retrieval failures:

1. **Case 9: negation blindness**

   User asks for tariffs that do **not** include mobile internet.

   Naive vector search returns tariffs where mobile internet is mentioned.

   Graph fixes it with set difference:

   ```text
   all products - products that include "Mobile internet"