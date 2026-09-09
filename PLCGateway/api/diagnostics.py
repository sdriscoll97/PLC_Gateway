from fastapi import APIRouter, HTTPException, Request
router=APIRouter(tags=["diagnostics"])

@router.get("/diagnostics")
def diagnostics(request: Request, plc: str):
    try:
        result=request.app.state.manager.diagnostics(plc)
        result.update({"plc":plc,"success":bool(result.get("reachable"))})
        return result
    except KeyError as exc: raise HTTPException(404, detail={"code":"unknown_plc","message":str(exc)})
    except Exception as exc: raise HTTPException(502, detail={"code":"diagnostics_failed","message":str(exc)})
