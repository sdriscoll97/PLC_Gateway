from fastapi import APIRouter, HTTPException, Request
router = APIRouter(tags=["browse"])

@router.get("/browse")
def browse(request: Request, plc: str, q: str = "", limit: int = 500, offset: int = 0):
    limit = min(max(limit, 1), 2000); offset = max(offset, 0)
    try: response = request.app.state.manager.tag_list(plc)
    except KeyError as exc: raise HTTPException(404, detail={"code":"unknown_plc","message":str(exc)})
    except Exception as exc: raise HTTPException(502, detail={"code":"browse_failed","message":str(exc)})
    if getattr(response, "Status", None) != "Success":
        raise HTTPException(502, detail={"code":"cip_browse_failed","message":getattr(response,"Status","No response")})
    tags=[]; needle=q.lower().strip()
    for item in response.Value or []:
        name=getattr(item,"TagName",""); dtype=getattr(item,"DataType",None)
        if needle and needle not in name.lower(): continue
        tags.append({"path":name,"datatype":dtype,"scope":"Program" if name.startswith("Program:") else "Controller"})
    tags.sort(key=lambda x:x["path"].lower())
    return {"success":True,"plc":plc,"total":len(tags),"offset":offset,"limit":limit,"tags":tags[offset:offset+limit]}
