"""Read-only Logix tag/UDT schema discovery for expandable gateway clients."""
from __future__ import annotations
import re
from fastapi import APIRouter, HTTPException, Request

router = APIRouter(tags=["schema"])
_TOKEN = re.compile(r"^(?P<name>[^\[]+)(?P<indexes>(?:\[\d+\])*)$")
_INDEX = re.compile(r"\[(\d+)\]")


def _dimensions(definition):
    if "dimensions" in definition:
        count = int(definition.get("dim", 0) or 0)
        return list(definition.get("dimensions", [])[:count])
    value = definition.get("array")
    return [value] if value else []


def _normalize(name, definition, types, path=None):
    data_type = definition.get("data_type")
    dtype = definition.get("data_type_name") or data_type
    if isinstance(data_type, dict):
        dtype = data_type.get("name") or dtype
        if not isinstance(dtype, str):
            raise ValueError(f"Structure has no type name: {name}")
        if dtype not in types:
            types[dtype] = []
            internal = data_type.get("internal_tags", {})
            members = []
            for member_name in data_type.get("attributes", []):
                member = internal.get(member_name)
                if member is not None:
                    members.append(_normalize(member_name, member, types, member_name))
            types[dtype] = members
    if not isinstance(dtype, str):
        dtype = str(dtype) if dtype is not None else "Unknown"
    return {"name": name, "path": path or name, "datatype": dtype,
            "dimensions": _dimensions(definition),
            "access": definition.get("external_access", "Unknown"),
            "alias": bool(definition.get("alias")), "structured": dtype in types}


def _discover(request, plc):
    try:
        raw_tags = request.app.state.manager.schema_tags(plc)
    except KeyError as exc:
        raise HTTPException(404, detail={"code":"unknown_plc","message":str(exc)})
    except Exception as exc:
        raise HTTPException(502, detail={"code":"schema_discovery_failed","message":str(exc)})
    types, roots = {}, []
    try:
        for raw in raw_tags or []:
            name = raw.get("tag_name", "")
            roots.append(_normalize(name, raw, types, name))
    except Exception as exc:
        raise HTTPException(502, detail={"code":"schema_normalization_failed","message":str(exc)})
    return roots, types


def _parse_token(token):
    match = _TOKEN.fullmatch(token)
    if not match:
        raise HTTPException(400, detail={"code":"invalid_path","message":token})
    return match.group("name"), [int(x) for x in _INDEX.findall(match.group("indexes"))]


def _apply_indexes(node, indexes, token):
    dims = list(node.get("dimensions") or [])
    if len(indexes) > len(dims):
        raise HTTPException(400, detail={"code":"too_many_indexes","message":token})
    for position, index in enumerate(indexes):
        if index < 0 or index >= int(dims[position]):
            raise HTTPException(400, detail={"code":"index_out_of_range","message":token})
    resolved = dict(node)
    resolved["dimensions"] = dims[len(indexes):]
    return resolved


def _resolve(path, roots, types):
    parts = path.split(".")
    root_name, indexes = _parse_token(parts[0])
    node = next((item for item in roots if item["name"] == root_name), None)
    if node is None:
        raise HTTPException(404, detail={"code":"unknown_path","message":path})
    node = _apply_indexes(node, indexes, parts[0])
    resolved_path = parts[0]
    for token in parts[1:]:
        # A member cannot be traversed until every array dimension on its parent is indexed.
        if node.get("dimensions"):
            raise HTTPException(400, detail={"code":"array_index_required","message":resolved_path})
        members = types.get(node["datatype"], [])
        name, indexes = _parse_token(token)
        child = next((item for item in members if item["name"] == name), None)
        if child is None:
            raise HTTPException(404, detail={"code":"unknown_member","message":token})
        node = _apply_indexes(child, indexes, token)
        resolved_path += "." + token
    node = dict(node); node["path"] = resolved_path
    return node


def _array_children(node, offset, limit):
    dims = list(node.get("dimensions") or [])
    if not dims: return []
    count = int(dims[0]); end = min(count, offset + limit)
    children = []
    for index in range(offset, end):
        child = dict(node)
        child["name"] = f"[{index}]"
        child["path"] = f'{node["path"]}[{index}]'
        child["dimensions"] = dims[1:]
        child["kind"] = "array_element"
        child["expandable"] = bool(child["dimensions"] or child["structured"])
        children.append(child)
    return children


@router.get("/schema")
def schema(request: Request, plc: str, q: str = "", limit: int = 500, offset: int = 0):
    limit=min(max(limit,1),2000); offset=max(offset,0)
    roots, types = _discover(request, plc); needle=q.lower().strip()
    filtered=[n for n in roots if not needle or needle in n["name"].lower() or needle in n["datatype"].lower()]
    filtered.sort(key=lambda item:item["path"].lower())
    return {"success":True,"plc":plc,"total":len(filtered),"offset":offset,"limit":limit,
            "roots":filtered[offset:offset+limit],"types":types}


@router.get("/schema/expand")
def schema_expand(request: Request, plc: str, path: str, limit: int = 100, offset: int = 0):
    """Lazily expand one tag/UDT/array node into GUI-ready children."""
    limit=min(max(limit,1),500); offset=max(offset,0)
    roots, types = _discover(request, plc)
    node = _resolve(path, roots, types)
    if node.get("dimensions"):
        total=int(node["dimensions"][0]); children=_array_children(node, offset, limit)
        kind="array"
    elif node.get("structured"):
        members=types.get(node["datatype"], []); total=len(members); children=[]
        for member in members[offset:offset+limit]:
            child=dict(member); child["path"]=path+"."+member["name"]
            child["kind"]="member"; child["expandable"]=bool(child["dimensions"] or child["structured"])
            children.append(child)
        kind="structure"
    else:
        total=0; children=[]; kind="leaf"
    return {"success":True,"plc":plc,"path":path,"datatype":node["datatype"],"kind":kind,
            "dimensions":node.get("dimensions",[]),"total":total,"offset":offset,"limit":limit,
            "children":children}


@router.get("/schema/type/{type_name}")
def schema_type(request: Request, type_name: str, plc: str):
    _roots, types = _discover(request, plc)
    if type_name not in types:
        raise HTTPException(404, detail={"code":"unknown_type","message":type_name})
    return {"success":True,"plc":plc,"type":type_name,"members":types[type_name]}
