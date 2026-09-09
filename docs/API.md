# API examples

FastAPI publishes interactive OpenAPI documentation at `/docs` when allowed by deployment policy.

- `GET /health` checks only the gateway process/configuration, not PLC reachability.
- `GET /diagnostics?plc=PLC_6` checks TCP 44818 and CIP PLC-time status without fabricating firmware metadata.
- `GET /read?plc=PLC_6&tag=SomeTag` reads one centrally configured PLC/tag.
- `POST /read/batch` body: `{"plc":"PLC_6","tags":["Tag1","Tag2"]}`.
- `GET /browse?plc=PLC_6&q=Motor&limit=500&offset=0` returns filtered tag metadata.
- `GET /objects?plc=PLC_6&class=C512&record=1582` uses the existing Brewmaxx SQL object lookup.
- `POST /write` body: `{"plc":"PLC_6","tag":"ApprovedTag","value":55,"verify_tag":"ApprovedStatusTag"}`. This is denied while read-only, for unauthorized identities, for tags outside the server allowlist, or when required SQL audit is not configured.

Errors use HTTP status codes plus `detail.code` and `detail.message` such as `unknown_plc`, `plc_read_failed`, `cip_read_failed`, `object_search_failed`, `write_denied`, and `write_failed`.
