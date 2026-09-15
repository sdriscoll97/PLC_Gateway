"""Convert BMX13's normalized cached schema into the original Expander Schema model."""
from __future__ import annotations
from tag_schema import Node, Schema


def _node(raw, path=None):
    return Node(
        name=str(raw.get('name', '')),
        path=str(path if path is not None else raw.get('path', raw.get('name', ''))),
        dtype=str(raw.get('datatype', 'Unknown')),
        dimensions=tuple(int(x) for x in (raw.get('dimensions') or ())),
        access=str(raw.get('access', 'Unknown')),
        issue='Alias resolution is not supported' if raw.get('alias') else '',
    )


def schema_from_gateway(payload):
    """Build a local Schema so filtering/expansion performs zero HTTP requests."""
    roots = tuple(_node(raw) for raw in payload.get('roots', ()))
    types = {}
    for dtype, members in (payload.get('types') or {}).items():
        types[str(dtype)] = tuple(_node(raw, '') for raw in members)
    generation = int(payload.get('generation', 0))
    digest = 'gateway:%s:%d' % (payload.get('plc', ''), generation)
    return Schema(roots, types, digest)


def load_gateway_schema(client, plc, refresh=False, limit=2000):
    """Fetch the cached schema once; explicit refresh is the only rediscovery path."""
    if refresh:
        client.refresh_schema(plc)
    first = client.schema(plc, q='', limit=limit, offset=0)
    roots = list(first.get('roots', ()))
    total = int(first.get('total', len(roots)))
    offset = len(roots)
    while offset < total:
        page = client.schema(plc, q='', limit=limit, offset=offset)
        rows = list(page.get('roots', ()))
        if not rows:
            break
        roots.extend(rows)
        offset += len(rows)
    first = dict(first)
    first['roots'] = roots
    schema = schema_from_gateway(first)
    source = 'Gateway schema generation %s (%s)' % (
        first.get('generation', '?'), first.get('cache_source', 'cache'))
    return schema, source
