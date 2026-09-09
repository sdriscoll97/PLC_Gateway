from fastapi import APIRouter, HTTPException, Request
router=APIRouter(tags=["objects"])

@router.get("/objects")
def objects(request: Request, plc: str, class_name: str | None = None, record: int | None = None):
    # Query parameter alias "class" is handled below because class is a Python keyword.
    cls = class_name or request.query_params.get("class")
    class_num=None
    if cls:
        try: class_num=int(str(cls).upper().lstrip("C"))
        except ValueError: raise HTTPException(422, detail={"code":"invalid_class","message":"class must look like C512 or 512"})
    try:
        request.app.state.manager.definition(plc)
        rows=request.app.state.object_db.fetch_object(plc, class_num=class_num, record_no=record)
    except KeyError as exc: raise HTTPException(404, detail={"code":"unknown_plc","message":str(exc)})
    except Exception as exc: raise HTTPException(502, detail={"code":"object_search_failed","message":str(exc)})
    return [{"class":"C%d"%row.class_no,"record":row.record_no,"designation":row.designation,
             "station":row.station_no,"path":"DiTSystemData.ClassObjects.C%d[%d]"%(row.class_no,row.record_no)} for row in rows]
