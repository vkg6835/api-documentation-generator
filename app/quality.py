"""Summarize explicit source-based reviews, bound to the recorded model outputs."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CRITERIA = ("correctness", "completeness", "clarity")


def output_digest(result):
    return hashlib.sha256(json.dumps(result, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def quality_report(capture, review):
    if review.get("capture_sha256") != output_digest(capture):
        raise ValueError("The captured inputs or outputs changed; update the review before reporting scores.")
    definitions = {case["id"]:case for case in capture["cases"]}
    if set(definitions) != set(review["cases"]):
        raise ValueError("Review every captured case before publishing the report.")
    rows=[]
    totals={setting:{"accepted":0,"reviewed":0,"unsupported_claims":0,**{key:0 for key in CRITERIA}} for setting in ("source only","source + usage")}
    for identifier,case in definitions.items():
        row={key:case[key] for key in ("id","project","method","path","essential_facts")}
        row.update({"evidence":case.get("evidence",[]),"examples":case.get("examples",[]),"contract":case.get("contract",{})})
        row["drafts"]=[]
        for setting in totals:
            result=case["generations"][setting]
            judgement=review["cases"][identifier][setting]
            if judgement["output_sha256"] != output_digest(result):
                raise ValueError("The model outputs changed; update their reviews before reporting scores.")
            scores=judgement["scores"]
            if result["accepted"]:
                if not isinstance(scores,dict) or set(scores)!=set(CRITERIA) or any(type(scores[key]) is not int or not 0<=scores[key]<=2 for key in CRITERIA):
                    raise ValueError("Accepted descriptions need a 0, 1 or 2 score for each criterion.")
                totals[setting]["accepted"]+=1
                totals[setting]["reviewed"]+=1
                for criterion in CRITERIA: totals[setting][criterion]+=scores[criterion]
            elif scores is not None:
                raise ValueError("Rejected generations have no prose scores.")
            if not isinstance(judgement["unsupported_claims"],list) or not isinstance(judgement["notes"],str):
                raise ValueError("Each review needs unsupported claims and a source-based explanation.")
            totals[setting]["unsupported_claims"]+=len(judgement["unsupported_claims"])
            row["drafts"].append({"setting":setting,**result,"review":judgement})
        rows.append(row)
    for total in totals.values():
        for criterion in CRITERIA:
            total[criterion]=round(total[criterion]/total["reviewed"],2) if total["reviewed"] else None
    return {"model":capture["model"],"case_count":len(rows),"generation_count":len(rows)*2,"project_count":len({row["project"] for row in rows}),
            "reviewer":review["reviewer"],"review_method":review["method"],"rubric":capture["rubric"],"settings":totals,"cases":rows,
            "limitations":"One generation per setting and endpoint, small authored sources, and an assistant review. Scores average accepted descriptions; rejected generations are reported separately. Independent human assessment and broad factuality are not established."}


def load_quality_report():
    capture_path=ROOT/"artifacts/llm_suite.json"
    review_path=ROOT/"evaluation/llm_review.json"
    if not capture_path.exists() or not review_path.exists(): return None
    try:
        return quality_report(json.loads(capture_path.read_text(encoding="utf-8")),json.loads(review_path.read_text(encoding="utf-8")))
    except (ValueError,KeyError,TypeError):
        return {"pending":True,"message":"The comparison needs a complete review matching the captured outputs."}
