from __future__ import annotations
import getpass, re
from uuid import uuid4
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from audit.audit_models import AuditRecord

router=APIRouter(tags=["writes"])
class WriteRequest(BaseModel):
    plc: str
    tag: str
    value: bool|int|float|str
    verify_tag: str|None=None

def user_for(request):
    # IIS/AD integration can forward the authenticated identity. The app never trusts
    # this header for production unless the reverse proxy strips client-supplied copies.
    return request.headers.get("x-authenticated-user") or getpass.getuser()

def authorized(config, user):
    return user in config.write_authorized_users

@router.post("/write")
def write(body: WriteRequest, request: Request):
    config=request.app.state.config; manager=request.app.state.manager; audit=request.app.state.audit
    correlation=uuid4(); user=user_for(request); client=request.client.host if request.client else None
    try: definition=manager.definition(body.plc)
    except KeyError as exc: raise HTTPException(404, detail={"code":"unknown_plc","message":str(exc),"correlation_id":str(correlation)})
    error=None; old=None; actual=None; succeeded=False; verified=None
    try:
        if config.read_only: raise PermissionError("Gateway is configured read-only")
        if not authorized(config,user): raise PermissionError("User is not authorized for PLC writes")
        if not manager.allowed_write(body.plc,body.tag): raise PermissionError("Tag is not in the server write allowlist")
        if config.require_audit_for_writes and not audit.configured: raise PermissionError("SQL audit is required but not configured")
        pre=manager.read(body.plc,[body.tag])[0]
        if pre.Status!="Success": raise RuntimeError("Pre-read failed: "+pre.Status)
        old=pre.Value
        result=manager.write(body.plc,body.tag,body.value)
        if result.Status!="Success": raise RuntimeError("Write failed: "+result.Status)
        succeeded=True
        verify_tag=body.verify_tag or body.tag
        rb=manager.read(body.plc,[verify_tag])[0]
        if rb.Status!="Success": raise RuntimeError("Read-back failed: "+rb.Status)
        actual=rb.Value; verified=(actual==body.value)
    except PermissionError as exc:
        error=str(exc)
    except Exception as exc:
        error=str(exc)
    record=AuditRecord.now(user_name=user,client_host=client,plc_name=body.plc,plc_address=definition.ip,
        tag_name=body.tag,old_value=old,requested_value=body.value,actual_value=actual,
        write_succeeded=succeeded,verified=verified,correlation_id=correlation,error_detail=error)
    try: audit.log(record)
    except Exception as audit_exc:
        # Never permit an unaudited successful write to be reported as clean.
        if succeeded: error=(error+"; " if error else "")+"Audit logging failed: "+str(audit_exc)
        elif config.require_audit_for_writes and error is None: error="Audit logging failed: "+str(audit_exc)
    if error:
        status=403 if isinstance(error,str) and ("read-only" in error or "authorized" in error or "allowlist" in error or "audit is required" in error) else 502
        raise HTTPException(status,detail={"code":"write_denied" if status==403 else "write_failed","message":error,"correlation_id":str(correlation)})
    return {"success":True,"plc":body.plc,"tag":body.tag,"expected":body.value,"actual":actual,
            "verified":verified,"correlation_id":str(correlation)}
