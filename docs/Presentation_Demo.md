# Three-minute Project 31 demonstration

Start the app with **Start Demo.bat**. Keep the terminal open and make sure the header reports `gemma:2b ready`. If it shows a missing model or unavailable Ollama, follow its message and select **Recheck model**.

## 0:00–0:30: State the problem and input

Say: “Developers spend time maintaining API documentation. My project reads Python API source and supplied usage examples to produce a reference with source evidence and local LLM explanations.”

Select **Bookstore · FastAPI**. Use the file selector to show `app.py`, `routes.py`, `models.py` and `requests.http`. The POST example supplies The Pragmatic Programmer, Andrew Hunt, price 499 and published true. These are documentation inputs; the generator parses the source and examples without executing the Bookstore API.

## 0:30–1:20: Show extracted facts

Click **Generate API reference** and select **POST /v1/books**. Explain that `/v1` comes from the application mounting and `/books` comes from the router.

Show **Request and response fields**. `BookCreate` requires title, author and price. Title length is 1–120; price is at least 0; published is optional and defaults to false. The response schema adds an integer ID and the declared success status is 201.

Open **Source evidence**. Point to the new-ID calculation, construction of the full saved dictionary, storage in `BOOKS`, and `return saved`.

## 1:20–2:00: Show context and generation

Open **Usage examples** and show the matching POST request. Explain that TF-IDF/cosine retrieval ranks supplied examples and HTTP method/path compatibility keeps unrelated requests out of the context.

Return to **API reference** and select **Draft this description**. Wait for generation to finish, then read and compare the actual wording with the source. The model writes prose; extracted method, path, schema and statuses remain separate. If generation fails, read the error, keep the extracted reference visible and use the saved Bookstore project in **Saved projects** to show its clearly identified earlier real Gemma draft.

## 2:00–2:30: Export and show an error case

Download **Markdown** and **OpenAPI**. Open the files manually and verify the route, request schema and status 201.

Select **GET /v1/books/{book_id}** and show the explicit 404 branch. The Inventory sample provides a second case: duplicate SKUs produce a declared 409 response.

## 2:30–3:00: Show evaluation honestly

Open **Evaluation**. State the route/retrieval fixture sizes. Then show the eight-endpoint, sixteen-draft LLM comparison and open a case with its source, full output and assistant review. Say: “Citation validity does not prove factual accuracy. Both LLM settings averaged 1.50 out of 2 correctness in this small assistant-reviewed study, so I keep source evidence available for review.”

## Rehearsal checklist

- The app opens and the readiness indicator updates after **Recheck model**.
- Loading source files and selecting a different endpoint work.
- Request/response field tables are readable at the screen size used for presenting.
- Generation completes or displays an actionable error without losing the reference.
- Markdown and OpenAPI download and open correctly.
- Source evidence, usage examples and the expanded Evaluation cases are readable.

Automated Python, live HTTP workflow and frontend rendering checks passed. The HTTP rehearsal includes a real Gemma generation and both downloads; it does not score prose factuality. You can repeat it with `py -3.13 scripts/rehearse_demo.py --url http://127.0.0.1:8010` while the app is running on that port.

Visual browser rehearsal has not been completed: computer-use stopped because it could not verify whether Chrome's current URL was allowed. Complete this checklist manually before presenting.
