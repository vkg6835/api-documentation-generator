"""Capture real local generations; report only explicitly reviewed, matching outputs."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app import llm
from app.engine import analyze
from app.quality import output_digest, quality_report


def main():
    parser=argparse.ArgumentParser()
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--generate",action="store_true",help="Capture one source-only and one source/example generation for each predefined case")
    mode.add_argument("--report",action="store_true",help="Validate explicit reviews and write the comparison report")
    options=parser.parse_args()
    artifact=ROOT/"artifacts/llm_suite.json"
    review_path=ROOT/"evaluation/llm_review.json"
    if options.report:
        result=quality_report(json.loads(artifact.read_text(encoding="utf-8")),json.loads(review_path.read_text(encoding="utf-8")))
        (ROOT/"artifacts/llm_quality.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
        print(json.dumps({"cases":result["case_count"],"reviewer":result["reviewer"],"settings":result["settings"]},indent=2))
        return
    readiness=llm.model_status()
    if not readiness["available"]: raise SystemExit(readiness["message"]+" "+readiness["action"])
    definition=json.loads((ROOT/"evaluation/llm_cases.json").read_text(encoding="utf-8"))
    capture={"model":llm.MODEL,"generated_at_utc":datetime.now(timezone.utc).isoformat(),"provenance":definition["provenance"],"rubric":definition["rubric"],"cases":[]}
    projects={}
    for case in definition["cases"]:
        name=case["project"]
        if name not in projects:
            folder=ROOT/"examples"/name
            files=[{"path":path.relative_to(folder).as_posix(),"content":path.read_text(encoding="utf-8")} for path in sorted(folder.rglob("*")) if path.is_file() and path.suffix in (".py",".http")]
            projects[name]=analyze(files,name)
        endpoint=next(e for e in projects[name]["endpoints"] if (e["method"],e["path"])==(case["method"],case["path"]))
        row={**case,"contract":{key:endpoint[key] for key in ("name","parameters","responses")},"evidence":endpoint["evidence"],"examples":endpoint["examples"],"generations":{}}
        for grounded in (False,True):
            setting="source + usage" if grounded else "source only"
            try:
                result={"accepted":True,"output":llm.explain(endpoint,grounded)}
            except llm.GenerationError as exc:
                result={"accepted":False,"error":str(exc)}
            row["generations"][setting]=result
            print(json.dumps({"case":case["id"],"setting":setting,"accepted":result["accepted"],"output_sha256":output_digest(result)}),flush=True)
        capture["cases"].append(row)
        artifact.write_text(json.dumps(capture,indent=2),encoding="utf-8")
    print("Saved actual outputs. Review them against the evidence and essential facts before running --report.",flush=True)


if __name__=="__main__":main()
