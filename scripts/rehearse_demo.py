"""Check the live local generator workflow. This is not a visual browser test."""
import argparse
import json
from pathlib import Path
import time
import urllib.request
from urllib.parse import urlparse


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--url",default="http://127.0.0.1:8000")
    options=parser.parse_args()
    base=options.url.rstrip("/")
    target=urlparse(base)
    if target.scheme!="http" or target.hostname not in ("127.0.0.1","localhost") or target.username or target.password:
        raise SystemExit("Use the HTTP address of the local demo.")

    def request(path,body=None,json_response=True):
        query=urllib.request.Request(base+path,data=json.dumps(body).encode() if body is not None else None,headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(query,timeout=10) as response:
            data=response.read().decode()
            return (json.loads(data) if json_response else data),response.headers

    health,_=request("/api/health")
    assert health["project_number"]==31
    if not health["llm"]["available"]:
        raise SystemExit(health["llm"]["message"]+" "+health["llm"]["action"])
    for asset in ("/","/static/app.js","/static/schema.js","/static/model-status.js","/static/quality.js"):
        content,_=request(asset,json_response=False)
        assert content.strip(),asset
    sample,_=request("/api/demo?name=bookstore")
    sample["name"]="Bookstore presentation rehearsal"
    record,_=request("/api/analyze",sample)
    identifier=record["id"]
    endpoint=next(e for e in record["endpoints"] if (e["method"],e["path"])==("POST","/v1/books"))
    schema=record["schemas"]["BookCreate"]
    assert set(schema["required"])=={"title","author","price"}
    assert schema["properties"]["price"]["minimum"]==0
    assert schema["properties"]["title"]["maxLength"]==120
    assert schema["properties"]["published"]["default"] is False
    assert endpoint["examples"][0]["id"]=="EX-books-create"
    print(f"Source analysis and declared schema checked: {identifier}",flush=True)
    request(f"/api/projects/{identifier}/explain",{"endpoint_id":endpoint["id"]})
    deadline=time.monotonic()+165
    while time.monotonic()<deadline:
        record,_=request(f"/api/projects/{identifier}")
        if record["job"]["status"]!="running": break
        time.sleep(1)
    else:
        raise SystemExit("Generation is still running. Inspect its saved project in the app.")
    if record["job"]["errors"]: raise SystemExit(record["job"]["errors"][0])
    assert record["job"]["completed"]==1
    endpoint=next(e for e in record["endpoints"] if e["id"]==endpoint["id"])
    assert endpoint["llm"]["model"]==health["llm"]["model"]
    print("Actual local description: "+endpoint["llm"]["behavior"],flush=True)
    spec,headers=request(f"/api/projects/{identifier}/openapi")
    assert "attachment" in headers["Content-Disposition"]
    assert spec["paths"]["/v1/books"]["post"]["requestBody"]["content"]["application/json"]["schema"]["$ref"]=="#/components/schemas/BookCreate"
    assert "201" in spec["paths"]["/v1/books"]["post"]["responses"]
    text,headers=request(f"/api/projects/{identifier}/markdown",json_response=False)
    assert "attachment" in headers["Content-Disposition"]
    health_section=text.split("## GET `/health`",1)[1].split("## GET",1)[0]
    assert health_section.count("Report whether the demonstration API process is responding.")==1
    assert "| Parameter |" not in health_section
    inventory,_=request("/api/demo?name=inventory")
    inventory_record,_=request("/api/analyze",inventory)
    create=next(e for e in inventory_record["endpoints"] if e["method"]=="POST")
    assert {r["status"] for r in create["responses"]}=={201,409}
    evaluation,_=request("/api/evaluation")
    assert evaluation["llm_quality"]["case_count"]==8
    assert evaluation["llm_quality"]["generation_count"]==16
    artifacts=Path(__file__).resolve().parents[1]/"artifacts"
    (artifacts/"bookstore-docs.md").write_text(text,encoding="utf-8")
    (artifacts/"bookstore-openapi.json").write_text(json.dumps(spec,indent=2),encoding="utf-8")
    print(f"HTTP workflow rehearsal passed: generation, both exports, Inventory 409 and reviewed evaluation. Open {base}/#project/{identifier}",flush=True)
    print("Visual browser rehearsal remains a separate manual check.",flush=True)
    print("Workflow and contract checks do not establish the description's semantic correctness. Review its prose against the source.",flush=True)


if __name__=="__main__":main()
