#!/usr/bin/env python3
"""Self-test for grade.py: a scripted run on the tiny synthetic replay must score 1.0; known-bad outputs must fail.
Run: python3 tests/test_grade.py"""
import json, os, shutil, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); S = os.path.join(os.path.dirname(HERE), 'skills', 'audit-my-bots', 'scripts')
failures = []

def run(*a, env=None, ok=True):
    r = subprocess.run([sys.executable, *a], capture_output=True, text=True, env=env)
    if ok and r.returncode: print(r.stdout, r.stderr); raise SystemExit('FAILED: ' + ' '.join(a))
    return r

def check(c, m):
    print(('PASS ' if c else 'FAIL ') + m)
    if not c: failures.append(m)

def grade(W, *extra):
    r = run(os.path.join(HERE, 'grade.py'), W, *extra, ok=False)
    return json.loads(r.stdout)

root = tempfile.mkdtemp(prefix='grade-test-')
try:
    run(os.path.join(HERE, 'make_replay.py'), root)
    W = os.path.join(root, 'work')
    run(f'{S}/sessions.py', 'replay', '--work', W, env={**os.environ, 'AUDIT_REPLAY_DIR': os.path.join(root, 'replay-tiny')})
    run(f'{S}/sessions.py', 'parse', '--work', W); run(f'{S}/judge_inputs.py', '--work', W, '--all')
    json.dump({x['key']: dict(label=False, type='new_request', topic=None, confidence='high', evidence='thanks')
               for x in json.load(open(f'{W}/judge_inputs.json'))}, open(f'{W}/labels.json', 'w'))
    run(f'{S}/diagnostics.py', '--work', W); run(f'{S}/build_findings.py', 'skeleton', '--work', W)
    d = json.load(open(f'{W}/findings_draft.json'))
    d['date_label'] = 'March 4, 2030'
    for b in d['bots']: b['issue'] = 'Working well'; b.pop('needs_review', None)
    for f in d['fleet']: f.pop('needs_review', None)
    json.dump(d, open(f'{W}/findings_draft.json', 'w'))
    run(f'{S}/build_findings.py', 'finalize', '--work', W, '--strict')
    run(f'{S}/make_report.py', f'{W}/findings.json', '--outdir', f'{W}/report')
    open(f'{W}/chat.md', 'w').write('Checked 2 bots. Nothing major to fix.\n- None for now\n')
    g = grade(W, '--lang', 'en', '--scenario', 'tiny-clean', '--chat', f'{W}/chat.md')
    check(g['score'] == 1.0, f'clean scripted run scores 1.0 ({g["passed"]}/{g["total"]})')
    open(f'{W}/chat_bad.md', 'w').write('I read every transcript.\n- Delete Word Coach\n')
    open(f'{W}/log.txt', 'w').write('sqlite3 store.db\n')
    g = grade(W, '--lang', 'en', '--chat', f'{W}/chat_bad.md', '--log', f'{W}/log.txt')
    bad = {c['text'] for c in g['checks'] if not c['passed']}
    check({'no internal jargon in what the user sees', 'no "Remove / Delete / Merge" options or titles', 'no forbidden files read'} <= bad,
          'jargon, a Delete option and a forbidden read are caught')
    g = grade(W, '--lang', 'ko')
    check(any('report language is ko' in c['text'] and not c['passed'] for c in g['checks']), 'wrong report language is caught')
    fz = json.load(open(f'{W}/findings.json'))
    fz['fleet'][0]['now'].append({'date': '', 'quote': {'orig': 'Sunny, 20 degrees /home/box/a/b.png'}})
    json.dump(fz, open(f'{W}/findings.json', 'w'))
    g = grade(W, '--lang', 'en')
    check(any(c['text'].startswith('no file paths') and not c['passed'] for c in g['checks']), 'a path in a quote is caught')
finally:
    shutil.rmtree(root, ignore_errors=True)
print(f'\n{"ALL PASSED" if not failures else f"{len(failures)} FAILED"}'); sys.exit(1 if failures else 0)
