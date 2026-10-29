import json
import re
import time
from pathlib import Path
from urllib.parse import urlparse

from app.parser import Parser
from app.retrieval import ExampleIndex, parse_examples


def compatible(endpoint, example):
    path = urlparse(example["url"]).path
    pattern = re.sub(r"\\\{[^}]+\\\}", "[^/]+", re.escape(endpoint["path"]))
    return endpoint["method"] == example["method"] and re.fullmatch(pattern, path) is not None


def analyze(files, name="Untitled API"):
    started = time.perf_counter()
    if not isinstance(files, list) or not 1 <= len(files) <= 30:
        raise ValueError("Submit between 1 and 30 source/example files.")
    total = 0
    names = set()
    for file in files:
        if not isinstance(file, dict) or not isinstance(file.get("path"), str) or not isinstance(file.get("content"), str):
            raise ValueError("Each file needs a path and text content.")
        path = file["path"].replace("\\", "/")
        if len(path)>160 or path.startswith("/") or ":" in path or ".." in path.split("/") or not path.endswith((".py", ".http", ".rest", ".txt")):
            raise ValueError("Use relative .py, .http, .rest or .txt file names.")
        if path in names:
            raise ValueError("File names must be unique.")
        names.add(path)
        file["path"] = path
        total += len(file["content"].encode())
    if total>500_000:
        raise ValueError("The combined source limit is 500 KB.")
    if not any(file["path"].endswith(".py") for file in files):
        raise ValueError("Include at least one Python source file.")
    parsed = Parser(files).parse()
    examples = parse_examples(files)
    evaluation_path = Path(__file__).resolve().parents[1]/"artifacts"/"evaluation.json"
    mode = json.loads(evaluation_path.read_text())["retrieval"]["selected_mode"] if evaluation_path.exists() else "word_bigram"
    index = ExampleIndex(examples, mode)
    for endpoint in parsed["endpoints"]:
        query = " ".join([endpoint["method"], endpoint["path"], endpoint["name"], endpoint["docstring"]]+[parameter["name"] for parameter in endpoint["parameters"]])
        # Similarity ranks examples; literal method/path compatibility prevents
        # attaching a request for a different endpoint to the documentation.
        endpoint["examples"] = [row for row in index.search(query, len(examples)) if compatible(endpoint, row)][:3]
    parsed.update({"name": str(name).strip()[:100] or "Untitled API", "files": files, "examples": examples,
        "file_count": len(files), "source_bytes": total, "baseline_seconds": round(time.perf_counter()-started, 4),
        "job": None, "status": "Source analyzed", "retrieval_mode": mode, "implementation": "Own Python AST workflow, sparse TF-IDF and cosine retrieval. Local pretrained Gemma supplies optional prose."})
    parsed["metrics"] = {"endpoints": len(parsed["endpoints"]), "schemas": len(parsed["schemas"]),
        "parameters": sum(len(row["parameters"]) for row in parsed["endpoints"]),
        "with_examples": sum(bool(row["examples"]) for row in parsed["endpoints"]),
        "with_declared_response_schema": sum(bool(row["responses"][0]["schema"]) for row in parsed["endpoints"])}
    return parsed


def openapi(record):
    paths = {}
    for endpoint in record["endpoints"]:
        method = endpoint["method"].lower()
        if method in paths.get(endpoint["path"], {}):
            continue
        prose = endpoint.get("llm") or {}
        operation = {"operationId": endpoint["id"], "summary": prose.get("summary", endpoint["summary"]),
            "description": prose.get("behavior", endpoint["docstring"] or "Extracted from source; semantic description needs review."),
            "parameters": [], "responses": {}, "x-source": {key:endpoint["source"][key] for key in ("id","file","start","end")}}
        bodies = []
        notes = {row["name"]:row["description"] for row in prose.get("parameter_notes", [])}
        for parameter in endpoint["parameters"]:
            if parameter["in"] in ("body", "form", "file"):
                bodies.append(parameter)
                continue
            item = {key:parameter[key] for key in ("name", "in", "required", "schema")}
            if notes.get(parameter["name"]) or parameter["description"]:
                item["description"] = notes.get(parameter["name"], parameter["description"])
            if not parameter["required"] and parameter["default"] is not None:
                item["schema"] = {**item["schema"], "default": parameter["default"]}
            operation["parameters"].append(item)
        if bodies:
            body_schema = bodies[0]["schema"] if len(bodies)==1 else {"type":"object", "properties":{row["name"]:row["schema"] for row in bodies}, "required":[row["name"] for row in bodies if row["required"]]}
            operation["requestBody"] = {"required":any(row["required"] for row in bodies), "content":{"application/json":{"schema":body_schema}}}
        for response in endpoint["responses"]:
            item = {"description": response["description"]}
            if response["schema"]:
                item["content"] = {"application/json":{"schema":response["schema"]}}
            operation["responses"][str(response["status"])] = item
        paths.setdefault(endpoint["path"], {})[method] = operation
    return {"openapi":"3.1.0", "info":{"title":record["name"], "version":"1.0.0", "description":"Generated by static analysis. LLM descriptions require review; source references are retained."},
        "paths":paths, "components":{"schemas":record["schemas"]}, "x-analysis-notes":record["notes"]}


def markdown(record):
    lines = ["# "+record["name"], "", "Generated from supplied Python source and usage examples. Descriptions are drafts for review.",
             "", f"Endpoints: {len(record['endpoints'])} · Schemas: {len(record['schemas'])}"]
    for endpoint in record["endpoints"]:
        prose = endpoint.get("llm") or {}
        source = endpoint["source"]
        summary = prose.get("summary", endpoint["summary"])
        behavior = prose.get("behavior", endpoint["docstring"] or "Semantic description not generated.")
        lines += ["", f"## {endpoint['method']} `{endpoint['path']}`", "", summary]
        if " ".join(behavior.split()).casefold() != " ".join(summary.split()).casefold():
            lines += ["", behavior]
        lines += ["", f"Source: `{source['file']}` lines {source['start']}–{source['end']} · `{source['id']}`", ""]
        if endpoint["parameters"]:
            lines += ["| Parameter | Location | Type | Required |", "|---|---|---|---|"]
            for p in endpoint["parameters"]:
                lines.append(f"| {p['name']} | {p['in']} | {p['type'].replace('|',' / ')} | {'Yes' if p['required'] else 'No'} |")
        else:
            lines.append("No parameters declared in the supported function signature.")
        lines += ["", "### Responses", ""]+[f"- {r['status']}: {r['description']}" for r in endpoint["responses"]]
        for example in endpoint["examples"]:
            lines += ["", "### Usage: "+example["title"], "", "```http", example["text"], "```", f"Example source: `{example['file']}` · `{example['id']}`"]
        if prose:
            lines += ["", "Evidence: "+", ".join(prose["evidence_ids"]), "", "Limitations: "+"; ".join(prose["limitations"])]
    lines += ["", "## Schemas", "", "```json", json.dumps(record["schemas"], indent=2), "```", "", "## Analysis notes", ""]
    lines += ["- "+note for note in record["notes"]] or ["- No static-analysis warnings."]
    return "\n".join(lines)


def compare(record, previous):
    def signatures(project):
        return {(e["method"],e["path"]):json.dumps({"parameters":e["parameters"],"responses":e["responses"]},sort_keys=True) for e in project["endpoints"]}
    now, old = signatures(record), signatures(previous)
    show = lambda keys: [{"method":method,"path":path} for method,path in sorted(keys)]
    return {"added":show(now.keys()-old.keys()), "removed":show(old.keys()-now.keys()),
            "changed":show({key for key in now.keys() & old.keys() if now[key]!=old[key]}),
            "schemas_changed":record["schemas"]!=previous["schemas"]}
