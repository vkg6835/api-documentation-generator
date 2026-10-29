"""Local HTTP service with no third-party runtime dependencies."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
from urllib.parse import urlparse, parse_qs

from app import storage, llm
from app.engine import analyze, openapi, markdown, compare
from app.quality import load_quality_report

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT/"static"


def demo(name):
    if name not in ("bookstore", "support", "inventory"):
        raise ValueError("Unknown demonstration project.")
    folder = ROOT/"examples"/name
    files = [{"path":path.relative_to(folder).as_posix(),"content":path.read_text(encoding="utf-8")}
             for path in sorted(folder.rglob("*")) if path.is_file() and path.suffix in (".py",".http")]
    return {"name":{"bookstore":"Bookstore API","support":"Support Tickets API","inventory":"Inventory API"}[name],"files":files}


def initialize():
    storage.initialize()
    if not storage.all_records():
        for name in ("bookstore","support"):
            sample=demo(name)
            record=analyze(sample["files"],sample["name"])
            record["demo"] = True
            if name=="bookstore" and (ROOT/"artifacts"/"demo_llm_output.json").exists():
                saved=json.loads((ROOT/"artifacts"/"demo_llm_output.json").read_text())
                for endpoint in record["endpoints"]:
                    if endpoint["id"] in saved:
                        try:
                            endpoint["llm"]={**llm.validate(saved[endpoint["id"]],endpoint),**{key:saved[endpoint["id"]][key] for key in ("model","seconds","mode")}}
                        except (ValueError,KeyError):
                            pass
            storage.insert(record)


def generate(identifier, endpoint_ids):
    def set_job(value, **updates):
        value["job"].update(updates)
    try:
        record=storage.get(identifier)
        endpoints=[e for e in record["endpoints"] if e["id"] in endpoint_ids]
        completed, errors = 0, []
        for endpoint in endpoints:
            storage.update(identifier,lambda value:set_job(value,current=f"{endpoint['method']} {endpoint['path']}"))
            try:
                output=llm.explain(endpoint)
                def attach(value):
                    target=next(e for e in value["endpoints"] if e["id"]==endpoint["id"])
                    target["llm"]=output
                storage.update(identifier,attach)
                completed+=1
            except (llm.GenerationError, OSError, ValueError) as exc:
                errors.append(str(exc))
            storage.update(identifier,lambda value:set_job(value,completed=completed,processed=completed+len(errors),errors=errors))
        def finish(value):
            set_job(value,status="done",current="",completed=completed,errors=errors)
            value["status"]="Draft descriptions generated" if completed else "Source analyzed"
        storage.update(identifier,finish)
    finally:
        llm.LOCK.release()


class Handler(BaseHTTPRequestHandler):
    server_version = "APINotes/1.0"

    def log_message(self, format, *args):
        pass

    def send(self, value, code=200, content_type="application/json", filename=None):
        body=json.dumps(value).encode() if content_type=="application/json" else value.encode() if isinstance(value,str) else value
        self.send_response(code)
        self.send_header("Content-Type",content_type+"; charset=utf-8")
        self.send_header("Content-Length",str(len(body)))
        self.send_header("X-Content-Type-Options","nosniff")
        self.send_header("Cache-Control","no-store")
        self.send_header("Content-Security-Policy","default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'")
        if filename:
            self.send_header("Content-Disposition",f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        try:
            route=urlparse(self.path)
            path=route.path
            if path=="/api/health":
                return self.send({"status":"ok","project_number":31,"local_only":True,"llm":llm.model_status()})
            if path=="/api/demo":
                return self.send(demo(parse_qs(route.query).get("name",["bookstore"])[0]))
            if path=="/api/projects":
                records=storage.all_records()
                return self.send({"items":[{key:r[key] for key in ("id","name","created_at","status","metrics","demo") if key in r} for r in records]})
            if path=="/api/evaluation":
                file=ROOT/"artifacts"/"evaluation.json"
                result=json.loads(file.read_text()) if file.exists() else {"pending":True}
                result["llm_quality"]=load_quality_report()
                return self.send(result)
            if path.startswith("/api/projects/"):
                pieces=path.strip("/").split("/")
                record=storage.get(pieces[2])
                if not record:
                    return self.send({"error":"Project not found"},404)
                if len(pieces)==3:
                    return self.send(record)
                if pieces[3]=="markdown":
                    return self.send(markdown(record),content_type="text/markdown",filename=record["id"]+"-docs.md")
                if pieces[3]=="openapi":
                    return self.send(openapi(record),filename=record["id"]+"-openapi.json")
                if pieces[3]=="compare":
                    previous=storage.get(parse_qs(route.query).get("previous",[""])[0])
                    if not previous:
                        return self.send({"error":"Choose an existing project revision"},404)
                    return self.send(compare(record,previous))
            if path=="/":
                return self.send((STATIC/"index.html").read_bytes(),content_type="text/html")
            if path.startswith("/static/"):
                file=(STATIC/path.removeprefix("/static/")).resolve()
                if file.parent==STATIC.resolve() and file.is_file():
                    types={".js":"text/javascript",".css":"text/css",".svg":"image/svg+xml"}
                    return self.send(file.read_bytes(),content_type=types.get(file.suffix,"application/octet-stream"))
            return self.send({"error":"Not found"},404)
        except (ValueError,OSError,KeyError) as exc:
            self.send({"error":str(exc)},400)

    def do_POST(self):
        try:
            origin=self.headers.get("Origin")
            if origin and origin!=f"http://{self.headers.get('Host')}":
                return self.send({"error":"Requests must originate from this local application."},403)
            size=int(self.headers.get("Content-Length","0"))
            if not 0<size<=1_000_000:
                return self.send({"error":"Submit a JSON request of at most 1 MB."},413)
            if "application/json" not in self.headers.get("Content-Type",""):
                return self.send({"error":"Use application/json."},415)
            body=json.loads(self.rfile.read(size))
            if not isinstance(body,dict):
                raise ValueError("Submit a JSON object.")
            path=urlparse(self.path).path
            if path=="/api/analyze":
                record=analyze(body.get("files"),body.get("name","Untitled API"))
                return self.send(storage.insert(record),201)
            if path.startswith("/api/projects/") and path.endswith("/explain"):
                identifier=path.split("/")[3]
                record=storage.get(identifier)
                if not record:
                    return self.send({"error":"Project not found"},404)
                selected=body.get("endpoint_id")
                ids=[e["id"] for e in record["endpoints"] if not selected or e["id"]==selected]
                if not ids:
                    raise ValueError("No matching endpoints to explain.")
                if len(ids)>20:
                    raise ValueError("Generate at most 20 endpoint descriptions in one request.")
                readiness=llm.model_status()
                if not readiness["available"]:
                    return self.send({"error":readiness["message"]+" "+readiness["action"],"llm":readiness},503)
                if not llm.LOCK.acquire(blocking=False):
                    return self.send({"error":"The local model is already drafting descriptions."},409)
                def begin(value):
                    value["job"]={"status":"running","total":len(ids),"processed":0,"completed":0,"current":"","errors":[]}
                try:
                    storage.update(identifier,begin)
                    threading.Thread(target=generate,args=(identifier,ids),daemon=True).start()
                except Exception:
                    llm.LOCK.release()
                    raise
                return self.send({"id":identifier,"status":"running","total":len(ids)},202)
            return self.send({"error":"Not found"},404)
        except (ValueError,KeyError,TypeError) as exc:
            self.send({"error":str(exc)},400)


def serve(port=8000):
    initialize()
    server=ThreadingHTTPServer(("127.0.0.1",port),Handler)
    print(f"API Notes, Project 31: http://127.0.0.1:{port}",flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        server.server_close()
