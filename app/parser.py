"""Static Python analysis. Uploaded code is parsed, never imported or executed.

Supported scope: literal FastAPI/APIRouter and Flask/Blueprint routes, ordinary
imports, static router mounting, typed parameters, and basic Pydantic models.
Dynamic routes and custom framework abstractions are reported as limitations.
"""
import ast
import hashlib
import re


METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}


def expression(node):
    return ast.unparse(node) if node is not None else "Any"


def literal(node, fallback=None):
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        return fallback


def keywords(call):
    return {item.arg: item.value for item in call.keywords if item.arg}


def status(node, default=200):
    value = literal(node)
    if isinstance(value, int):
        return value
    match = re.search(r"HTTP_(\d{3})_", expression(node))
    return int(match[1]) if match else default


def schema_for(node, model_names):
    if node is None:
        return {}
    if isinstance(node, ast.Constant):
        return {"type": "null"} if node.value is None else {}
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return {"anyOf": [schema_for(node.left, model_names), schema_for(node.right, model_names)]}
    name = expression(node).split(".")[-1]
    simple = {"str": "string", "int": "integer", "float": "number", "bool": "boolean", "None": "null"}
    if name in simple:
        return {"type": simple[name]}
    if name in model_names:
        return {"$ref": "#/components/schemas/"+name}
    if isinstance(node, ast.Subscript):
        kind = expression(node.value).split(".")[-1]
        items = list(node.slice.elts) if isinstance(node.slice, ast.Tuple) else [node.slice]
        if kind == "Annotated":
            return schema_for(items[0], model_names)
        if kind in ("list", "List", "Sequence", "set", "Set"):
            return {"type": "array", "items": schema_for(items[0], model_names)}
        if kind in ("dict", "Dict", "Mapping"):
            return {"type": "object", "additionalProperties": schema_for(items[-1], model_names)}
        if kind == "Optional":
            return {"anyOf": [schema_for(items[0], model_names), {"type": "null"}]}
        if kind == "Union":
            return {"anyOf": [schema_for(item, model_names) for item in items]}
        if kind == "Literal":
            values = [literal(item) for item in items]
            return {"enum": values}
    return {}


def field_details(default, annotation):
    marker = None
    if isinstance(annotation, ast.Subscript) and expression(annotation.value).split(".")[-1] == "Annotated":
        pieces = list(annotation.slice.elts) if isinstance(annotation.slice, ast.Tuple) else [annotation.slice]
        annotation = pieces[0]
        marker = next((piece for piece in pieces[1:] if isinstance(piece, ast.Call)), None)
    if isinstance(default, ast.Call):
        marker = default
    options = keywords(marker) if marker else {}
    value_node = marker.args[0] if marker and marker.args else options.get("default", None if marker is default and marker is not None else default)
    required = value_node is None or (isinstance(value_node, ast.Constant) and value_node.value is Ellipsis)
    if "default_factory" in options:
        required = False
    constraints = {}
    for key, target in {"ge": "minimum", "le": "maximum", "gt": "exclusiveMinimum", "lt": "exclusiveMaximum",
                        "min_length": "minLength", "max_length": "maxLength", "pattern": "pattern"}.items():
        if key in options and literal(options[key]) is not None:
            constraints[target] = literal(options[key])
    return annotation, marker, required, literal(value_node), constraints, literal(options.get("description"), "")


class Parser:
    def __init__(self, files):
        self.files = files
        self.units = []
        self.sources = []
        self.notes = []
        self.instances = {}
        self.models = {}
        self.model_sources = {}

    def evidence(self, unit, node):
        start, end = node.lineno, node.end_lineno
        code = "\n".join(unit["content"].splitlines()[start-1:end])
        source_id = "SRC-"+hashlib.sha256(f"{unit['path']}:{start}:{code}".encode()).hexdigest()[:10]
        row = {"id": source_id, "file": unit["path"], "start": start, "end": end, "code": code}
        if source_id not in {item["id"] for item in self.sources}:
            self.sources.append(row)
        return row

    def resolve(self, unit, name):
        pieces = name.split(".")
        mapped = unit["imports"].get(pieces[0])
        target = mapped+"."+".".join(pieces[1:]) if mapped and len(pieces)>1 else mapped or unit["module"]+"."+name
        if target in self.instances:
            return target
        candidates = [key for key in self.instances if key.endswith("."+target) or key == target]
        return candidates[0] if len(candidates)==1 else target

    def parse(self):
        for file in self.files:
            if not file["path"].endswith(".py"):
                continue
            try:
                tree = ast.parse(file["content"], filename=file["path"])
            except SyntaxError as exc:
                self.notes.append(f"{file['path']}:{exc.lineno}: Python syntax error: {exc.msg}")
                continue
            unit = {**file, "tree": tree, "module": file["path"][:-3].replace("/", "."), "imports": {}}
            for node in tree.body:
                if isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        unit["imports"][alias.asname or alias.name] = (node.module+"." if node.module else "")+alias.name
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        unit["imports"][alias.asname or alias.name] = alias.name
            self.units.append(unit)
            for node in tree.body:
                if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
                    factory = unit["imports"].get(expression(node.value.func), expression(node.value.func)).split(".")[-1]
                    if factory in ("FastAPI", "APIRouter", "Flask", "Blueprint"):
                        opts = keywords(node.value)
                        prefix = literal(opts.get("prefix", opts.get("url_prefix")), "")
                        for target in node.targets:
                            if isinstance(target, ast.Name):
                                self.instances[unit["module"]+"."+target.id] = {"kind": factory, "prefix": prefix,
                                    "mounts": [""] if factory in ("FastAPI", "Flask") else []}
                if isinstance(node, ast.ClassDef) and any(expression(base).split(".")[-1] == "BaseModel" or unit["imports"].get(expression(base), "").endswith(".BaseModel") for base in node.bases):
                    if node.name in self.models:
                        self.notes.append(f"Duplicate model name {node.name}; use unique model names in the submitted files.")
                    self.models[node.name] = node
                    self.model_sources[node.name] = self.evidence(unit, node)
        mounts = []
        for unit in self.units:
            for node in ast.walk(unit["tree"]):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in ("include_router", "register_blueprint") and node.args:
                    parent = self.resolve(unit, expression(node.func.value))
                    child = self.resolve(unit, expression(node.args[0]))
                    opts = keywords(node)
                    override = opts.get("prefix", opts.get("url_prefix"))
                    value = literal(override, "")
                    if parent in self.instances and child in self.instances and isinstance(value, str):
                        mounts.append((parent, child, value, node.func.attr=="register_blueprint" and override is not None))
                    else:
                        self.notes.append(f"{unit['path']}:{node.lineno}: router mount could not be statically resolved.")
        for _ in range(len(self.instances)+1):
            changed = False
            for parent, child, prefix, replace in mounts:
                info = self.instances[child]
                for parent_mount in self.instances[parent]["mounts"]:
                    combined = parent_mount+self.instances[parent]["prefix"]+prefix
                    if combined not in info["mounts"]:
                        info["mounts"].append(combined)
                        changed = True
                    if replace:
                        info["flask_override"] = prefix
            if not changed:
                break
        schemas = {}
        for name, model in self.models.items():
            properties, required_fields = {}, []
            for field in model.body:
                if not isinstance(field, ast.AnnAssign) or not isinstance(field.target, ast.Name):
                    continue
                annotation, marker, required, default, constraints, description = field_details(field.value, field.annotation)
                field_schema = {**schema_for(annotation, self.models), **constraints}
                if description:
                    field_schema["description"] = description
                if not required and default is not None:
                    field_schema["default"] = default
                properties[field.target.id] = field_schema
                if required:
                    required_fields.append(field.target.id)
            schemas[name] = {"type": "object", "properties": properties, "required": required_fields}
        endpoints = []
        for unit in self.units:
            for function in [node for node in ast.walk(unit["tree"]) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]:
                for decorator in function.decorator_list:
                    if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
                        continue
                    action = decorator.func.attr
                    if action not in METHODS | {"route", "api_route"}:
                        continue
                    owner = self.resolve(unit, expression(decorator.func.value))
                    if owner not in self.instances:
                        continue
                    opts = keywords(decorator)
                    path = literal(decorator.args[0] if decorator.args else opts.get("path", opts.get("rule")))
                    if not isinstance(path, str):
                        self.notes.append(f"{unit['path']}:{decorator.lineno}: dynamic route path skipped.")
                        continue
                    methods = [action.upper()] if action in METHODS else literal(opts.get("methods"), ["GET"])
                    if not isinstance(methods, (list, tuple, set)) or not all(isinstance(method, str) and method.lower() in METHODS for method in methods):
                        self.notes.append(f"{unit['path']}:{decorator.lineno}: dynamic or unsupported HTTP methods skipped.")
                        continue
                    info = self.instances[owner]
                    prefixes = info["mounts"] or [""]
                    if not info["mounts"] and info["kind"] in ("APIRouter", "Blueprint"):
                        self.notes.append(f"{unit['path']}: {expression(decorator.func.value)} is not mounted in the supplied files; its standalone prefix is shown.")
                    for mount in prefixes:
                        route = mount+("" if "flask_override" in info else info["prefix"])+path
                        converters = {match[2]: match[1] or "str" for match in re.finditer(r"<(?:(\w+):)?(\w+)>", route)}
                        route = re.sub(r"<(?:(?:\w+):)?(\w+)>", r"{\1}", route)
                        path_names = set(re.findall(r"{(\w+)(?::[^}]+)?}", route))
                        parameters = []
                        args = function.args.posonlyargs+function.args.args
                        defaults = [None]*(len(args)-len(function.args.defaults))+function.args.defaults
                        for arg, default_node in list(zip(args, defaults))+list(zip(function.args.kwonlyargs, function.args.kw_defaults)):
                            if arg.arg in ("self", "cls"):
                                continue
                            annotation, marker, required, default, constraints, description = field_details(default_node, arg.annotation)
                            kind = unit["imports"].get(expression(marker.func), expression(marker.func)).split(".")[-1] if marker else ""
                            if kind in ("Depends", "Security") or expression(annotation).split(".")[-1] in ("Request", "Response", "BackgroundTasks"):
                                continue
                            model_name = expression(annotation).split(".")[-1]
                            location = "path" if arg.arg in path_names else {"Header": "header", "Cookie": "cookie", "Body": "body", "Form": "form", "File": "file"}.get(kind, "body" if model_name in self.models else "query")
                            actual_annotation = annotation or ast.Name(id=converters.get(arg.arg, "Any"))
                            parameters.append({"name": arg.arg, "in": location, "type": expression(actual_annotation),
                                "required": True if location=="path" else required, "default": default,
                                "schema": {**schema_for(actual_annotation, self.models), **constraints}, "description": description})
                        response_code = status(opts.get("status_code"))
                        if info["kind"] in ("Flask", "Blueprint") and function.body and isinstance(function.body[-1], ast.Return):
                            returned = function.body[-1].value
                            if isinstance(returned, ast.Tuple) and len(returned.elts)>=2:
                                response_code = status(returned.elts[1], response_code)
                        responses = [{"status": response_code, "description": "Declared success response", "schema": schema_for(opts.get("response_model"), self.models)}]
                        for node in ast.walk(function):
                            if isinstance(node, ast.Call) and expression(node.func).split(".")[-1] in ("HTTPException", "abort"):
                                error_opts = keywords(node)
                                code = status(error_opts.get("status_code", node.args[0] if node.args else None), 500)
                                if code not in [item["status"] for item in responses]:
                                    responses.append({"status": code, "description": literal(error_opts.get("detail"), "Explicit error branch"), "schema": {}})
                        evidence = [self.evidence(unit, function)]
                        annotations = [arg.annotation for arg in args if arg.annotation]+[opts["response_model"]] if opts.get("response_model") else [arg.annotation for arg in args if arg.annotation]
                        used = {node.id for annotation in annotations for node in ast.walk(annotation) if isinstance(node, ast.Name)}
                        evidence += [self.model_sources[name] for name in sorted(used) if name in self.model_sources]
                        for method in methods:
                            identifier = "EP-"+hashlib.sha256(f"{method}:{route}:{unit['path']}:{function.name}".encode()).hexdigest()[:10]
                            endpoints.append({"id": identifier, "method": method.upper(), "path": route, "name": function.name,
                                "summary": literal(opts.get("summary"), "") or (ast.get_docstring(function) or function.name.replace("_", " ")).splitlines()[0],
                                "docstring": ast.get_docstring(function) or "", "parameters": parameters, "responses": responses,
                                "source": evidence[0], "evidence": evidence, "async": isinstance(function, ast.AsyncFunctionDef),
                                "framework": "Flask" if info["kind"] in ("Flask", "Blueprint") else "FastAPI", "llm": None})
        keys = [(row["method"], row["path"]) for row in endpoints]
        if len(keys)!=len(set(keys)):
            self.notes.append("Duplicate method/path declarations were found; export keeps the first declaration and reports this warning.")
        return {"endpoints": endpoints, "schemas": schemas, "sources": self.sources, "notes": list(dict.fromkeys(self.notes))}
