"""Read-only Logix tag/UDT schema discovery for expandable gateway clients."""
from __future__ import annotations
from fastapi import APIRouter, HTTPException, Request

router = APIRouter(tags=["schema"])


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
            # Reserve first so recursive definitions cannot recurse forever.
            types[dtype] = []
            internal = data_type.get("internal_tags", {})
            members = []
            for member_name in data_type.get("attributes", []):
                member = internal.get(member_name)
                if member is None:
                    continue
                members.append(_normalize(member_name, member, types, member_name))
            types[dtype] = members
    if not isinstance(dtype, str):
        dtype = str(dtype) if dtype is not None else "Unknown"
    return {
        "name": name,
        "path": path or name,
        "datatype": dtype,
        "dimensions": _dimensions(definition),
        "access": definition.get("external_access", "Unknown"),
        "alias": bool(definition.get("alias")),
        "structured": dtype in types,
    }


@router.get("/schema")
def schema(request: Request, plc: str, q: str = "", limit: int = 500, offset: int = 0):
    limit = min(max(limit, 1), 2000)
    offset = max(offset, 0)
    try:
        raw_tags = request.app.state.manager.schema_tags(plc)
    except KeyError as exc:
        raise HTTPException(404, detail={"code": "unknown_plc", "message": str(exc)})
    except Exception as exc:
        raise HTTPException(502, detail={"code": "schema_discovery_failed", "message": str(exc)})

    types = {}
    roots = []
    needle = q.lower().strip()
    try:
        for raw in raw_tags or []:
            name = raw.get("tag_name", "")
            node = _normalize(name, raw, types, name)
            if not needle or needle in name.lower() or needle in node["datatype"].lower():
                roots.append(node)
    except Exception as exc:
        raise HTTPException(502, detail={"code": "schema_normalization_failed", "message": str(exc)})

    roots.sort(key=lambda item: item["path"].lower())
    return {
        "success": True,
        "plc": plc,
        "total": len(roots),
        "offset": offset,
        "limit": limit,
        "roots": roots[offset:offset + limit],
        "types": types,
    }


@router.get("/schema/type/{type_name}")
def schema_type(request: Request, type_name: str, plc: str):
    try:
        raw_tags = request.app.state.manager.schema_tags(plc)
    except KeyError as exc:
        raise HTTPException(404, detail={"code": "unknown_plc", "message": str(exc)})
    except Exception as exc:
        raise HTTPException(502, detail={"code": "schema_discovery_failed", "message": str(exc)})
    types = {}
    for raw in raw_tags or []:
        _normalize(raw.get("tag_name", ""), raw, types)
    if type_name not in types:
        raise HTTPException(404, detail={"code": "unknown_type", "message": type_name})
    return {"success": True, "plc": plc, "type": type_name, "members": types[type_name]}
