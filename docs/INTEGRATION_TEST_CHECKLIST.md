# PLC Gateway controlled integration checklist

- [ ] BBCMWPBMX13 still owns validated VLAN interfaces; no workstation routing/VLAN change was made.
- [ ] PLC_6 `10.160.12.10:44818` is reachable from BMX13.
- [ ] `/health` succeeds with gateway still in read-only mode.
- [ ] `/diagnostics?plc=PLC_6` reports TCP/CIP results without fabricated firmware.
- [ ] Approved read tag returns the same value through `/read` and an independent server-side check.
- [ ] `/read/batch` returns multiple approved tags and does not create a connection storm.
- [ ] `/browse` returns tag metadata; paging/filtering works.
- [ ] `/objects?plc=PLC_6&class=C512` returns expected Brewmaxx objects when SQL access is available.
- [ ] Workstation on 172.23.74.x reaches gateway through approved HTTPS endpoint while direct PLC TCP remains unavailable.
- [ ] GUI read/browse workflows use the gateway client and require no PLC IP address locally.
- [ ] Before write test: approved AD identity/group, SQL audit table, service account, exact safe test tag and change window are documented.
- [ ] Unauthorized write is denied and audited.
- [ ] Non-allowlisted tag write is denied and audited.
- [ ] Approved safe write is immediately read back and correlation ID matches SQL audit row.
- [ ] Service auto-start/recovery and reboot behavior are validated.
- [ ] HTTPS certificate/renewal, monitoring, log retention and support ownership are approved.
