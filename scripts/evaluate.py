"""Reproducible evaluation. Gold labels are authored separately from the parser."""
import argparse
import json
from pathlib import Path
import re
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.engine import analyze
from app.retrieval import ExampleIndex, parse_examples
from app.server import demo
from app import llm

ROOT=Path(__file__).resolve().parents[1]


def route_metrics(expected,predicted):
    expected,predicted=set(expected),set(predicted)
    true=len(expected & predicted)
    precision=true/len(predicted) if predicted else 0
    recall=true/len(expected) if expected else 0
    return {"precision":precision,"recall":recall,"f1":2*precision*recall/(precision+recall) if precision+recall else 0,
        "correct":true,"predicted":len(predicted),"missing":[list(item) for item in sorted(expected-predicted)],"unexpected":[list(item) for item in sorted(predicted-expected)]}


def regex_routes(files):
    found=[]
    # Deliberately simple baseline: literal local decorator path only.
    pattern=r'@\w+\.(get|post|put|patch|delete|route)\(\s*["\']([^"\']*)["\']([^\n]*)'
    for file in files:
        if not file["path"].endswith(".py"):continue
        for method,path,tail in re.findall(pattern,file["content"]):
            methods=re.findall(r'["\'](GET|POST|PUT|PATCH|DELETE)["\']',tail) if method=="route" else [method.upper()]
            path=re.sub(r'<(?:(?:\w+):)?(\w+)>',r'{\1}',path)
            found += [(method,path) for method in methods or ["GET"]]
    return found


def retrieval_metrics(index,queries):
    hits1=hits3=0
    reciprocal=0
    rows=[]
    for query,expected in queries:
        ranking=index.search(query,3)
        ids=[row["id"] for row in ranking]
        hits1+=bool(ids and ids[0]==expected)
        hits3+=expected in ids
        reciprocal+=1/(ids.index(expected)+1) if expected in ids else 0
        rows.append({"query":query,"expected":expected,"retrieved":ids})
    return {"hit1":hits1/len(queries),"hit3":hits3/len(queries),"mrr_at_3":reciprocal/len(queries),"predictions":rows}


def main():
    args=argparse.ArgumentParser()
    args.add_argument("--llm",action="store_true",help="Also record actual source-only and example-grounded local generations")
    options=args.parse_args()
    gold=json.loads((ROOT/"evaluation/gold.json").read_text())
    expected,ast_found,regex_found=[],[],[]
    examples=[]
    projects={}
    for name in gold["routes"]:
        sample=demo(name)
        projects[name]=analyze(sample["files"],sample["name"])
        expected += [(name,*route) for route in gold["routes"][name]]
        ast_found += [(name,e["method"],e["path"]) for e in projects[name]["endpoints"]]
        regex_found += [(name,*route) for route in regex_routes(sample["files"])]
        examples += parse_examples(sample["files"])
    experiments=[]
    for mode in ["unigram","word_bigram","word_char"]:
        index=ExampleIndex(examples,mode)
        experiments.append({"mode":mode,"features":len(index.vectorizer.idf),"dev":retrieval_metrics(index,gold["retrieval_dev"])})
    winner=max(experiments,key=lambda row:(row["dev"]["hit1"],row["dev"]["hit3"],row["dev"]["mrr_at_3"]))["mode"]
    for experiment in experiments:
        experiment["test"]=retrieval_metrics(ExampleIndex(examples,experiment["mode"]),gold["retrieval_test"])
    result={"project_number":31,"dataset":gold["provenance"],"extraction":{"gold_count":len(expected),"ast":route_metrics(expected,ast_found),"regex":route_metrics(expected,regex_found)},
        "retrieval":{"index_count":len(examples),"dev_count":len(gold["retrieval_dev"]),"test_count":len(gold["retrieval_test"]),"selected_mode":winner,"selection_rule":"Development hit@1, then hit@3 and MRR; test excluded from selection","experiments":experiments},
        "limitations":["Small authored fixtures, not a general API benchmark.","No runtime execution or end-to-end API behavior test.","Citation validity does not establish semantic correctness of LLM descriptions.","No LLM training or fine-tuning is claimed."]}
    artifact=ROOT/"artifacts"
    artifact.mkdir(exist_ok=True)
    (artifact/"evaluation.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps({"routes":len(expected),"ast_f1":result["extraction"]["ast"]["f1"],"regex_f1":result["extraction"]["regex"]["f1"],"retrieval_selected":winner},indent=2),flush=True)
    if options.llm:
        endpoint=next(e for e in projects["bookstore"]["endpoints"] if e["method"]=="POST")
        generations=[]
        for grounded in [False,True]:
            try:
                output=llm.explain(endpoint,grounded)
                generations.append({"setting":"source + usage" if grounded else "source only","accepted":True,"output":output})
                if grounded:
                    (artifact/"demo_llm_output.json").write_text(json.dumps({endpoint["id"]:output},indent=2),encoding="utf-8")
            except llm.GenerationError as exc:
                generations.append({"setting":"source + usage" if grounded else "source only","accepted":False,"error":str(exc)})
            print(json.dumps({"llm_setting":generations[-1]["setting"],"accepted":generations[-1]["accepted"]}),flush=True)
        (artifact/"llm_comparison.json").write_text(json.dumps({"model":llm.MODEL,"endpoint":endpoint["path"],"cases":generations,"rubric":"Review factual correctness, completeness, clarity, relevant citations and unsupported claims manually. Two generations cannot estimate broad model quality."},indent=2),encoding="utf-8")


if __name__=="__main__":main()
