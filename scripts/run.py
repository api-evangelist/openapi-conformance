#!/usr/bin/env python3
"""Run every tool in tools.yml against every case and write results/<date>.json + docs/data/latest.json.
Usage: run.py [--tools TOOLDIR] [--only id,id] [--date YYYY-MM-DD]
TOOLDIR holds node/ (npm installs), py/ (venv) and go/ (go install bin). See README for the install lines."""
import datetime, glob, json, os, re, shutil, subprocess, sys, yaml

# Released OpenAPI versions. Declining a document that claims any other version is the right answer: it is invalid.
RELEASED = {'3.0.0', '3.0.1', '3.0.2', '3.0.3', '3.0.4', '3.1.0', '3.1.1', '3.1.2', '3.2.0'}
SUITE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

def load_cases():
    cases = []
    for m in sorted(glob.glob(f'{SUITE}/cases/ae/*/manifest.yml')):
        d = os.path.dirname(m)
        for c in yaml.safe_load(open(m))['cases']:
            cases.append(dict(c, suite='ae', path=os.path.join(d, c['file'])))
    # OAI's own schema tests: pass/ = valid, fail/ = invalid, decided by schema-base.yaml. The folder is the
    # minor line (3.1, 3.2); the case's version is what its openapi field declares.
    for f in sorted(glob.glob(f'{SUITE}/cases/oai/*/*/*.yaml')):
        line, kind = f.split('/')[-3], f.split('/')[-2]
        name = os.path.basename(f).replace('.yaml', '')
        declared = str((yaml.safe_load(open(f)) or {}).get('openapi', ''))
        version = declared if re.fullmatch(rf'{re.escape(line)}\.\d+', declared) else f'{line}.0'
        cases.append({'id': f'oai-{line}-{kind}-{name}', 'suite': 'oai', 'version': version, 'path': f, 'file': os.path.relpath(f, SUITE),
                      'expect': 'invalid' if kind == 'fail' else 'valid', 'level': 'schema',
                      'rule': name.replace('-', ' ').replace('_', ' '), 'spec': f'https://spec.openapis.org/oas/v{line}.0.html'})
    for c in cases:
        try: c['declared'] = str((yaml.safe_load(open(c['path'])) or {}).get('openapi'))
        except Exception: c['declared'] = None
    return cases

def run(cmd, timeout=60):
    env = dict(os.environ, CI='1', NO_COLOR='1', FORCE_COLOR='0', TERM='dumb')
    p = subprocess.Popen(cmd, shell=True, cwd=SUITE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env, stdin=subprocess.DEVNULL, start_new_session=True)
    try:
        out, _ = p.communicate(timeout=timeout); return p.returncode, out
    except subprocess.TimeoutExpired:
        os.killpg(os.getpgid(p.pid), 9); return -1, 'timeout'

def main():
    a = sys.argv[1:]; only = None; date = datetime.date.today().isoformat()
    tooldir = os.environ.get('OPENAPI_TOOLS', os.path.join(SUITE, '.tools'))
    while a:
        k = a.pop(0)
        if k == '--only': only = set(a.pop(0).split(','))
        elif k == '--date': date = a.pop(0)
        elif k == '--tools': tooldir = a.pop(0)
    env = {'suite': SUITE, 'node': f'{tooldir}/node', 'nb': f'{tooldir}/node/node_modules/.bin', 'py': f'{tooldir}/py/bin', 'go': f'{tooldir}/go'}
    for f in ('schema-check.mjs', 'parser-validate.mjs'): shutil.copy(f'{SUITE}/scripts/{f}', env['node'])
    manifest = yaml.safe_load(open(f'{SUITE}/tools.yml'))
    tools = [t for t in manifest['tools'] if not only or t['id'] in only]
    cases = load_cases()
    rows, meta = [], {}
    for t in tools:
        if t.get('skip'):
            meta[t['id']] = {k: t.get(k, '') for k in ('name', 'repo', 'role')} | {'version': '', 'notes': t['skip'], 'skipped': True}
            continue
        _, v = run(t['version_cmd'].format(**env))
        meta[t['id']] = {k: t.get(k, '') for k in ('name', 'repo', 'role', 'notes')} | {'version': v.strip().splitlines()[-1] if v.strip() else ''}
        for c in cases:
            schema = f"{SUITE}/schemas/{c['version'].rsplit('.', 1)[0]}"
            code, out = run(t['cmd'].format(f=c['path'], schema=schema, **env))
            out = re.sub(r'\x1b\[[0-9;]*[A-Za-z]', '', out).strip()
            if code == -1: verdict = 'timeout'
            elif t.get('error') and re.search(t['error'], out): verdict = 'error'
            elif code != 0 and manifest.get('fetch_error') and re.search(manifest['fetch_error'], out): verdict = 'error'
            elif t.get('unsupported') and re.search(t['unsupported'], out):
                verdict = 'unsupported' if c.get('declared') in RELEASED else 'invalid'
            else: verdict = 'valid' if code == 0 else 'invalid'
            rows.append({'tool': t['id'], 'case': c['id'], 'suite': c['suite'], 'version': c['version'], 'level': c['level'], 'expect': c['expect'],
                         'verdict': verdict, 'pass': verdict == c['expect'], 'exit': code, 'tail': out.replace(SUITE, '.')[-600:]})
            print(f"{t['id']:22s} {c['id'][:60]:60s} expect={c['expect']:7s} got={verdict:7s} {'ok' if verdict == c['expect'] else 'MISS'}")
    # --only re-runs some tools: keep every other tool's rows from the existing run for this date.
    prev = f'{SUITE}/results/{date}.json'
    if only and os.path.exists(prev):
        old = json.load(open(prev))
        meta = {t: m for t, m in old['tools'].items() if t not in meta} | meta
        rows = [r for r in old['results'] if r['tool'] not in only] + rows
        order = [t['id'] for t in yaml.safe_load(open(f'{SUITE}/tools.yml'))['tools']]
        meta = dict(sorted(meta.items(), key=lambda kv: order.index(kv[0]) if kv[0] in order else 99))
    doc = {'date': date, 'tools': meta,'cases': [{k: c[k] for k in ('id', 'suite', 'version', 'level', 'expect', 'rule', 'spec', 'file', 'note') if k in c} for c in cases], 'results': rows}
    os.makedirs(f'{SUITE}/results', exist_ok=True); os.makedirs(f'{SUITE}/docs/data', exist_ok=True)
    for p in (f'{SUITE}/results/{date}.json', f'{SUITE}/docs/data/latest.json'):
        json.dump(doc, open(p, 'w'), indent=1)
    print(f'{len(rows)} results, {len(tools)} tools, {len(cases)} cases')

if __name__ == '__main__':
    main()
