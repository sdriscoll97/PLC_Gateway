# Handoff requirement verification

This matrix maps the handoff to committed deliverables. Items requiring plant infrastructure approval are intentionally marked deployment validation rather than falsely claimed complete.

| Requirement | Implementation / evidence | Status |
|---|---|---|
| FastAPI modular service | `PLCGateway/app.py`, `api/*.py` | Implemented |
| Central logical PLC config | `PLCGateway/plc/plc_config.json`, `config.py` | Implemented; addresses require site validation |
| Health/read/batch | `/health`, `api/read.py` | Implemented; plant validation required |
| Browse | `api/browse.py` with filter/paging | Implemented; plant validation required |
| Object search | `api/objects.py`, existing `plantit_db.py` | Implemented; SQL validation required |
| Diagnostics | `api/diagnostics.py`, TCP/CIP only | Implemented; plant validation required |
| Controlled write + read-back | `api/write.py` | Implemented, disabled by default |
| Unknown PLC/arbitrary IP rejection | manager accepts logical config names only | Implemented |
| Tag write allowlist | anchored server regex allowlist | Implemented, empty by default |
| Authentication/authorization | reverse-proxy identity contract + exact approved identities | Adapter implemented; AD/IIS approval/integration required |
| SQL audit incl denied attempts | `audit/sql_logger.py`, `audit/schema.sql` | Implemented; DB/service account approval required |
| Batch connection control | managed wrapper + per-PLC bounded semaphore/lock | Implemented |
| Explicit timeouts | config + Pylogix/HTTP timeouts | Implemented |
| No automatic write retry | no write retry path | Implemented |
| Rotating structured service logs | rotating gateway log | Implemented |
| Windows Service/recovery | `scripts/install_service.ps1`, runbook | Procedure supplied; wrapper/recovery validation required |
| HTTPS | IIS reverse-proxy design in runbook | Deployment approval/certificate required |
| Gateway client | `gateway_client.py` | Implemented; GUI transport migration requires workstation validation |
| Mock tests | `tests/` | Implemented; execute on target/dev machine |
| API docs/errors | FastAPI OpenAPI + `docs/API.md` | Implemented |
| Deployment/rollback/support | `docs/DEPLOYMENT_RUNBOOK.md` | Implemented |
| Security decisions | `docs/SECURITY.md` | Implemented |
| Controlled integration checklist | `docs/INTEGRATION_TEST_CHECKLIST.md` | Implemented |

The success criteria involving actual BBCMWPBMX13, workstation, PLC_6, AD, IIS, certificates, and SQL cannot be certified by source review alone; follow the integration checklist before production sign-off.
