from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter(tags=["reads"])
class BatchRead(BaseModel):
    plc: str
    tags: list[str] = Field(min_length=1, max_length=64)

def _result(tag, response):
    if response is None or getattr(response, "Status", None) != "Success":
        return {"tag": tag, "success": False, "status": getattr(response, "Status", "No response"), "value": None, "datatype": None}
    value = response.Value
    return {"tag": tag, "success": True, "status": "Success", "value": value, "datatype": type(value).__name__}

@router.get("/read")
def read_tag(request: Request, plc: str, tag: str):
    try: response = request.app.state.manager.read(plc, [tag])[0]
    except KeyError as exc: raise HTTPException(404, detail={"code":"unknown_plc","message":str(exc)})
    except Exception as exc: raise HTTPException(502, detail={"code":"plc_read_failed","message":str(exc)})
    result = _result(tag, response)
    if not result["success"]: raise HTTPException(502, detail={"code":"cip_read_failed","message":result["status"],"tag":tag})
    return result

@router.post("/read/batch")
def read_batch(body: BatchRead, request: Request):
    try: responses = request.app.state.manager.read(body.plc, body.tags)
    except KeyError as exc: raise HTTPException(404, detail={"code":"unknown_plc","message":str(exc)})
    except ValueError as exc: raise HTTPException(422, detail={"code":"invalid_batch","message":str(exc)})
    except Exception as exc: raise HTTPException(502, detail={"code":"plc_read_failed","message":str(exc)})
    items = [_result(tag, responses[i] if i < len(responses) else None) for i, tag in enumerate(body.tags)]
    return {"success": all(x["success"] for x in items), "plc": body.plc,
            "results": {x["tag"]: x["value"] for x in items if x["success"]}, "items": items}
