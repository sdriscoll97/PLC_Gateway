# Security decisions required before production

- **Authentication:** IIS/Windows Authentication or another OT-approved AD-integrated method must terminate client authentication. Direct Uvicorn access is not a production authentication boundary.
- **Identity forwarding:** reverse proxy must strip inbound identity headers and inject the authenticated Windows identity itself.
- **Authorization:** map the approved OT write group to `write_authorized_users` (or replace the temporary exact-identity adapter with enterprise group validation). Reads should also be restricted by network/proxy policy.
- **Write allowlist:** every writable tag or anchored regex requires OT approval. Empty means no writes.
- **Audit:** SQL database/schema/table, service-account rights and retention require approval. `PLC_GATEWAY_AUDIT_SQL` is an environment secret and must not be committed.
- **Certificates:** use an enterprise-issued certificate on IIS; decide hostname, renewal ownership and TLS policy.
- **Service account:** choose a least-privilege domain/service identity with only required SQL/network rights; deny interactive logon where policy permits.
- **Exposure:** API must be reachable only from approved engineering networks. Never bind/expose an arbitrary proxy on VLAN 617.
- **Write retries:** intentionally absent. A write is not automatically retried.
