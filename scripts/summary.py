#!/usr/bin/env python3
"""Print per-tool, per-version-line scores from docs/data/latest.json (the same arithmetic the report page does)."""
import collections, json, os, sys
d = json.load(open(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), '..', 'docs', 'data', 'latest.json')))
S = collections.defaultdict(collections.Counter)
for r in d['results']:
    c = S[(r['tool'], r['version'].rsplit('.', 1)[0])]
    if r['verdict'] == 'unsupported': c['unsupported'] += 1; continue
    c['n'] += 1; c['ok'] += r['pass']
    c[f"{r['expect']}_n"] += 1; c[f"{r['expect']}_ok"] += r['pass']
    c[f"{r['level']}_n"] += 1; c[f"{r['level']}_ok"] += r['pass']
    c['error'] += r['verdict'] in ('error', 'timeout')
for (t, l), c in sorted(S.items()):
    print(f"{t:24s} {l}  right {c['ok']:3d}/{c['n']:<3d} accepts-valid {c['valid_ok']}/{c['valid_n']}  rejects-invalid {c['invalid_ok']}/{c['invalid_n']}"
          f"  schema {c['schema_ok']}/{c['schema_n']} semantic {c['semantic_ok']}/{c['semantic_n']}  unsup {c['unsupported']} err {c['error']}")
