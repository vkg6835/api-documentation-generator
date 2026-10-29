import copy
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.engine import analyze, openapi, markdown, compare
from app.parser import Parser
from app.retrieval import Tfidf, ExampleIndex
from app.server import demo
from app.llm import validate, GenerationError
from app import storage
from scripts.evaluate import route_metrics


class ProjectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sample=demo("bookstore")
        cls.bookstore=analyze(sample["files"],sample["name"])

    def test_router_alias_and_cross_file_mount(self):
        paths={(e["method"],e["path"]) for e in self.bookstore["endpoints"]}
        self.assertEqual(paths,{("GET","/health"),("GET","/v1/books"),("POST","/v1/books"),("GET","/v1/books/{book_id}"),("PUT","/v1/books/{book_id}"),("DELETE","/v1/books/{book_id}")})

    def test_schema_constraints_and_optional_default(self):
        schema=self.bookstore["schemas"]["BookCreate"]
        self.assertEqual(set(schema["required"]),{"title","author","price"})
        self.assertEqual(schema["properties"]["price"]["minimum"],0)
        self.assertEqual(schema["properties"]["published"]["default"],False)

    def test_typed_parameters_and_error_status(self):
        endpoint=next(e for e in self.bookstore["endpoints"] if e["name"]=="get_book")
        self.assertEqual(endpoint["parameters"][0]["in"],"path")
        self.assertTrue(endpoint["parameters"][0]["required"])
        self.assertEqual({r["status"] for r in endpoint["responses"]},{200,404})

    def test_required_query_and_annotated_constraints(self):
        source='from fastapi import FastAPI, Query\nfrom typing import Annotated\napp=FastAPI()\n@app.get("/search")\ndef search(q: str=Query(), limit: Annotated[int, Query(ge=1)]=10):\n return []\n'
        params=analyze([{"path":"api.py","content":source}])["endpoints"][0]["parameters"]
        self.assertTrue(params[0]["required"])
        self.assertFalse(params[1]["required"])
        self.assertEqual(params[1]["schema"]["minimum"],1)

    def test_flask_blueprint_override_and_status_tuple(self):
        sample=demo("support");record=analyze(sample["files"])
        self.assertEqual(len(record["endpoints"]),4)
        self.assertTrue(all(e["path"].startswith("/api/tickets") for e in record["endpoints"]))
        post=next(e for e in record["endpoints"] if e["method"]=="POST")
        self.assertEqual(post["responses"][0]["status"],201)
        get=next(e for e in record["endpoints"] if e["name"]=="get_ticket")
        self.assertEqual(get["parameters"][0]["type"],"int")

    def test_user_code_is_not_executed(self):
        code='raise RuntimeError("must never execute")\nfrom fastapi import FastAPI\napp=FastAPI()\n@app.get("/safe")\ndef safe():\n return {"ok":True}'
        self.assertEqual(analyze([{"path":"api.py","content":code}])["endpoints"][0]["path"],"/safe")

    def test_syntax_and_dynamic_routes_are_reported(self):
        broken=Parser([{"path":"broken.py","content":"def invalid(:"}]).parse()
        self.assertTrue(broken["notes"])
        code='from fastapi import FastAPI\napp=FastAPI()\nPATH="/dynamic"\n@app.get(PATH)\ndef dynamic():\n return 1'
        record=analyze([{"path":"api.py","content":code}])
        self.assertFalse(record["endpoints"])
        self.assertIn("dynamic route",record["notes"][0])

    def test_sparse_tfidf_matches_hand_calculation(self):
        model=Tfidf("unigram").fit(["book book price","price author"])
        self.assertAlmostEqual(model.idf["w:book"],math.log(3/2)+1)
        self.assertEqual(model.idf["w:price"],1)
        vector=model.transform("book price")
        self.assertAlmostEqual(sum(v*v for v in vector.values()),1)

    def test_cosine_and_unknown_query(self):
        model=Tfidf().fit(["create book","delete ticket"])
        left=model.transform("create book")
        self.assertAlmostEqual(model.cosine(left,left),1)
        self.assertEqual(model.transform("xylophone"),{})

    def test_examples_are_attached_to_compatible_route_only(self):
        for endpoint in self.bookstore["endpoints"]:
            self.assertEqual(len(endpoint["examples"]),1)
            self.assertEqual(endpoint["examples"][0]["method"],endpoint["method"])
        names=[e["examples"][0]["id"] for e in self.bookstore["endpoints"]]
        self.assertEqual(len(names),len(set(names)))

    def test_openapi_retains_body_schema_and_source(self):
        spec=openapi(self.bookstore)
        post=spec["paths"]["/v1/books"]["post"]
        self.assertEqual(post["requestBody"]["content"]["application/json"]["schema"]["$ref"],"#/components/schemas/BookCreate")
        self.assertIn("201",post["responses"])
        self.assertIn("file",post["x-source"])

    def test_model_cannot_change_extracted_contract(self):
        endpoint=self.bookstore["endpoints"][1]
        output={"summary":"Create a book","behavior":"Store an in-memory catalog entry.","evidence_ids":[endpoint["source"]["id"]],"example_ids":[],"parameter_notes":[],"limitations":["Runtime behavior has not been tested."]}
        accepted=validate(output,endpoint)
        self.assertEqual(accepted["evidence_ids"],output["evidence_ids"])
        with self.assertRaises(GenerationError):validate({**output,"method":"DELETE"},endpoint)
        with self.assertRaises(GenerationError):validate({**output,"evidence_ids":["invented"]},endpoint)
        with self.assertRaises(GenerationError):validate({**output,"parameter_notes":[{"name":"invented","description":"bad"}]},endpoint)

    def test_drift_detection_and_markdown(self):
        changed=copy.deepcopy(self.bookstore)
        changed["endpoints"].pop()
        result=compare(changed,self.bookstore)
        self.assertEqual(len(result["removed"]),1)
        self.assertIn("Source:",markdown(self.bookstore))
        self.assertIn("EX-books-create",markdown(self.bookstore))

    def test_gold_metric_hand_computed(self):
        result=route_metrics([("GET","/a"),("POST","/b")],[("GET","/a"),("GET","/c")])
        self.assertEqual(result["precision"],.5)
        self.assertEqual(result["recall"],.5)
        self.assertEqual(result["f1"],.5)

    def test_source_file_validation(self):
        with self.assertRaises(ValueError):analyze([{"path":"../../private.py","content":""}])
        with self.assertRaises(ValueError):analyze([{"path":"api.py","content":"x"*500001}])

    def test_sqlite_updates_preserve_existing_fields(self):
        original=storage.DB_PATH
        with tempfile.TemporaryDirectory() as folder:
            try:
                storage.DB_PATH=Path(folder)/"test.sqlite3"
                storage.initialize()
                record=storage.insert(self.bookstore)
                storage.update(record["id"],lambda value:value.update({"status":"Reviewed"}))
                saved=storage.get(record["id"])
                self.assertEqual(saved["status"],"Reviewed")
                self.assertEqual(saved["endpoints"],record["endpoints"])
            finally:storage.DB_PATH=original


if __name__=="__main__":unittest.main()
