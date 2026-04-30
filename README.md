# vector_graph_search

Локальное demo для занятия:

**«Поиск в базе знаний: где векторы ошибаются, а графы помогают»**

Проект показывает, почему обычный vector search в RAG может находить похожий текст, но не находить правильный контекст.

В demo сравниваются два подхода:

```text
Naive vector search:
query → Qdrant → похожие документы

Graph-augmented search:
query → graph lookup → Qdrant filter → правильный evidence
```

В проекте нет LLM, OpenAI API, Ollama, Neo4j и Docker.

Qdrant запускается локально в in-memory режиме.

---

# Бизнес-кейс 1: тариф без мобильного интернета

Пользователь спрашивает:

```text
Посоветуй тарифы, которые строго НЕ включают мобильный интернет.
```

В базе есть три тарифа:

```text
Тариф Базовый:
- включает звонки и SMS;
- мобильный интернет не входит.

Тариф Смарт:
- включает звонки, SMS и безлимитный мобильный интернет.

Тариф Премиум:
- включает мобильный интернет в роуминге и приоритетную поддержку.
```

Правильный ответ:

```text
Тариф Базовый
```

Но naive vector search сначала находит:

```text
Тариф Смарт
Тариф Премиум
```

Почему?

Потому что в запросе есть слова:

```text
мобильный интернет
```

Vector search ищет похожие тексты и поднимает документы, где эта фраза явно встречается.  
Но пользователь просит тариф **без** мобильного интернета.

Граф хранит связи:

```text
Тариф Смарт   -[INCLUDES]-> Мобильный интернет
Тариф Премиум -[INCLUDES]-> Мобильный интернет
```

Граф помогает сделать правило:

```text
allowed_products = all_products - products_with_mobile_internet
```

Результат:

```text
Тариф Базовый
```

После этого Qdrant ищет только внутри допустимого множества и возвращает правильный тариф.

---

# Бизнес-кейс 2: бизнес-термин против технического ID

Пользователь спрашивает:

```text
Какой сейчас error rate у Шлюза Госуслуг?
```

Проблема: в логах сервис называется не “Шлюз Госуслуг”, а:

```text
esia-bridge-prod
```

В базе есть документы:

```text
1. Runbook про Шлюз Госуслуг

2. CMDB-документ:
   esia-bridge-prod реализует бизнес-сервис "Шлюз Госуслуг"

3. DevOps Log:
   Service: esia-bridge-prod
   Metric: 5xx_ratio_percent = 15

4. DevOps Log:
   Service: kafka-billing-consumer
   Metric: consumer_lag = 0
```

Naive vector search возвращает:

```text
Runbook
CMDB
```

Эти документы похожи на запрос, но они не содержат текущую метрику error rate.

Граф хранит связь:

```text
esia-bridge-prod -[IMPLEMENTS]-> Шлюз Госуслуг
```

Граф резолвит бизнес-термин в технический ID:

```text
Шлюз Госуслуг → esia-bridge-prod
```

После этого Qdrant ищет только в логах нужного сервиса:

```text
doc_type == "devops_log"
service_id == "esia-bridge-prod"
```

И возвращает правильный evidence:

```text
5xx_ratio_percent = 15
```

---

# Главная идея

```text
Vector search = ищет похожий текст
Graph search = задает связи, правила и правильную область поиска
```

В production RAG это выглядит так:

```text
query
→ graph lookup
→ allowed entities / resolved IDs
→ filtered vector search
→ evidence
→ LLM answer
```

---

# Структура проекта

```text
vector_graph_search/
├── .python-version
├── .gitignore
├── README.md
├── pyproject.toml
├── uv.lock
└── demo/
    ├── __init__.py
    ├── run_demo.py
    └── test_demo.py
```

---

# Установка

Нужен `uv`.

Проект использует Python:

```text
3.11.9
```

Установить Python и зависимости:

```bash
uv python install 3.11.9
uv sync --frozen
```

Проверить версию Python:

```bash
uv run python --version
```

Ожидаемо:

```text
Python 3.11.9
```

---

# Запуск demo

```bash
uv run python -m demo.run_demo
```

---

# Запуск тестов

```bash
uv run python -m unittest demo.test_demo -v
```

Ожидаемый результат:

```text
Ran 2 tests

OK
```

---

# Что смотреть в выводе

## Case 9

Naive Qdrant search:

```text
#1 Тариф Смарт
#2 Тариф Премиум
#3 Тариф Базовый
```

Graph-filtered Qdrant search:

```text
#1 Тариф Базовый
```

## Case 4

Naive Qdrant search:

```text
#1 Runbook
#2 CMDB
```

Graph-filtered Qdrant search:

```text
#1 DevOps Log: esia-bridge-prod
Metric: 5xx_ratio_percent = 15
```