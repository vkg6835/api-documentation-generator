# Likely expectations for Project 31

The confirmed topic is **API Documentation Generator**: generate API docs from source code and usage examples. The priorities below are inferred from that topic and the earlier ILLM lab assignments. They are not a confirmed marking rubric.

| Likely expectation | What to show |
|---|---|
| A working LLM feature | Generate an actual Gemma description from endpoint source, schema definitions and a matching HTTP request |
| Useful documentation | Method/path, inputs, declared responses, usage, readable behavior and downloadable reference |
| Understanding the implementation | Walk through one AST route, prefix resolution, the TF-IDF formula, cosine ranking and the prompt |
| A clear baseline | Compare local-decorator regex extraction with AST plus mount resolution on the same annotated sources |
| Controlled experiments | Compare unigram, bigram and character features on identical retrieval queries; select on development queries |
| Honest measurements | Show expected routes, saved predictions, test counts, missed matches and the limits of an authored fixture set |
| Attribution and reliability | Exact handler/model snippets, source IDs, example IDs and validation that rejects invented identifiers |
| An explainable personal contribution | Own workflow, numerical calculations, validators, exporters and UI; disclose the pretrained Gemma model |
| A convincing demonstration | One code-to-documentation example, exports, a second framework and a concrete error case |

Earlier labs emphasize implementing fundamental representations and metrics, using consistent data in comparisons, separating development and test decisions, and explaining results. Those habits are relevant here. The project does not claim to implement every model from every lab.

There is no evidence that this project specifically requires fine-tuning an LLM, implementing a Transformer from scratch, supporting every programming language, or achieving a particular headline score. Do not claim those as professor requirements without a project rubric.

The choice is a local Python-first prototype: FastAPI and Flask source analysis, usage-context retrieval, grounded generation and reproducible evaluation. The generator's own HTTP service uses the standard library, avoiding unrelated framework dependencies in the demonstration environment.

The project should be described as a research prototype. Its strongest current evidence is correct extraction on ten annotated routes, measured retrieval on twelve held-out authored queries, and an actual source-only/grounded LLM comparison. Broader documentation quality still needs a larger, independently reviewed dataset.
