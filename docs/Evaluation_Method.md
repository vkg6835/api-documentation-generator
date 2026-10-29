# Expanded LLM evaluation

The expanded study compares one source-only draft with one source-plus-usage draft for each of eight endpoints. The inputs cover Bookstore FastAPI routes, Support Tickets Flask routes and a separate Inventory FastAPI example. These cases are authored demonstration sources, not a public benchmark or independent dataset.

## Capture and review

1. `evaluation/llm_cases.json` defines the cases, essential facts and scoring rubric before generation.
2. `py -3.13 scripts/compare_llm.py --generate` runs the actual local `gemma:2b` model. Both settings use the same endpoint contract and source evidence; the second also includes retrieved compatible HTTP requests. Existing generation options are temperature 0, a 4096-token context and up to 650 output tokens.
3. `artifacts/llm_suite.json` retains the actual outputs, timings, source snippets, request examples and declared contracts. One attempt is captured for each setting; rejected outputs are retained as failures rather than silently retried or removed.
4. `evaluation/llm_review.json` records a manual source-based **Codex assistant review** of all description fields. Correctness, completeness and clarity each receive 0, 1 or 2; unsupported claims are listed explicitly. Static contract facts are not credited as generated prose completeness.
5. `py -3.13 scripts/compare_llm.py --report` validates the review and computes the displayed report. Hashes bind the review to the captured inputs and outputs. Changing or regenerating them makes the old review invalid.

The source snippets and full recorded outputs are available inside each comparison case on the Evaluation page. This permits inspection of errors that valid citation IDs alone cannot detect.

## Recorded results

| Setting | Accepted | Correctness / 2 | Completeness / 2 | Clarity / 2 | Flagged unsupported claims |
|---|---|---|---|---|---|
| Source only | 8/8 | 1.50 | 1.00 | 1.88 | 4 |
| Source plus usage | 8/8 | 1.50 | 1.00 | 1.50 | 4 |

Acceptance means JSON shape and provenance checks passed. It does not mean the prose is correct. Scores average accepted descriptions; if a later run rejects an output, the acceptance count and rejected case remain visible while its prose scores are omitted.

Usage context corrected the Bookstore create-book return-value claim. Across all eight cases, both settings still made errors such as calling an in-memory dictionary a database or list, and both often omitted error branches or return statuses. These results do not establish a consistent improvement in documentation quality from usage examples.

## Limits and a future independent review

The sources, expectations and scores were prepared with an assistant. No independent human rater, repeated-run variability estimate, large-project benchmark or general accuracy claim is established. The model was not trained or fine-tuned.

For a stronger future study, have at least two human reviewers independently score randomized, unlabeled pairs using the same rubric, resolve disagreements, and evaluate additional independently selected source projects. Preserve failures and report reviewer agreement. Do not copy old scores to new generations.
