#!/usr/bin/env python3
"""Regression tests for iteration 3 of the skill eval, on the synthetic fixture of test_iteration2 (fake text).
Run: python3 tests/test_iteration3.py [--keep]

 1. make_report writes the opening sentence and its ui key to report/lede.txt and prints both
 2. make_report checks the whole report (all pages) and writes report/checks.txt
 3. fix candidates are listed once per bot; groups refer to them by id
 4. finalize: a line made only of bot names is never a placeholder warning
 5. an evidence line with "chat" is shown as the ui.in_chat label (e.g. "You (in X)")
 6. the footer adds the translated-quote sentence only when a translation exists
 7. "too_early": true shows the ui.too_early tag
 8. compare_runs.py prints the status table and agreement rates
"""
import json, os, re, shutil, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
S = os.path.join(ROOT, 'skills', 'audit-my-bots', 'scripts')
sys.path.insert(0, HERE)
import test_iteration2 as t2
failures = []

def run(*args, ok=True):
    r = subprocess.run([sys.executable, *args], capture_output=True, text=True)
    if ok and r.returncode != 0:
        print(r.stdout, r.stderr); raise SystemExit(f'FAILED: {" ".join(args)}')
    return r

def check(cond, msg):
    print(('PASS ' if cond else 'FAIL ') + msg)
    if not cond: failures.append(msg)

def main():
    root = tempfile.mkdtemp(prefix='bot-audit-it3-'); W = os.path.join(root, 'work')
    try:
        R = t2.build(root)
        run(f'{S}/sessions.py', 'replay', '--work', W, '--from', R)
        run(f'{S}/sessions.py', 'parse', '--work', W)
        run(f'{S}/judge_inputs.py', '--work', W, '--all')
        ji = json.load(open(f'{W}/judge_inputs.json')); byu = {x['user']: x for x in ji}
        rows = ['No, keep it to the notes goal', 'Again, keep it to the notes goal', 'Stay on the notes goal please',
                'Too long, the intro is useless', 'Too long again', 'Still too long']
        open(f'{W}/labels.tsv', 'w').write(''.join(
            f"{byu[u]['n']}\tcorrection\t{'scope_selection' if byu[u]['bot'] == t2.E else 'format_length'}\thigh\t-\t-\t{u[:6]}\n" for u in rows))
        run(f'{S}/judge_inputs.py', '--work', W, '--label', f'{W}/labels.tsv')
        run(f'{S}/diagnostics.py', '--work', W)
        d = json.load(open(f'{W}/diag.json'))
        bf = d['bots'][t2.F]
        ids = [c['id'] for g in bf['groups'].values() for c in g['fix_candidates']]
        check(bf['fix_candidates'] and all(set(c) == {'id', 'ts', 'incidents_after', 'active_days_after'} for g in bf['groups'].values() for c in g['fix_candidates'])
              and set(ids) <= {f['id'] for f in bf['fix_candidates']} and len({f['id'] for f in bf['fix_candidates']}) == len(bf['fix_candidates']),
              '3. fix candidates listed once per bot; groups refer to them by id')
        run(f'{S}/build_findings.py', 'skeleton', '--work', W, '--lang', 'ko')
        dr = json.load(open(f'{W}/findings_draft.json'))
        check(any(b.get('fix_candidates') for b in dr['bots']), '3. the draft carries the per-bot candidate list next to fix_check')
        dr['date_label'] = 'x'
        for b in dr['bots']:
            b.pop('needs_review', None)
            for f in b['findings']: f.pop('needs_review', None); f.pop('fix_check', None)
        for f in dr['fleet']: f.pop('needs_review', None)
        names = [b['name'] for b in dr['bots']]
        json.dump(dr, open(f'{W}/findings_draft.json', 'w'))
        r = run(f'{S}/build_findings.py', 'finalize', '--work', W, '--strict', ok=False)
        name_line = next((e['text'] for f in dr['fleet'] for e in f.get('now', []) if e.get('text') and all(n in names for n in e['text'].split(', '))), None)
        check(name_line and "placeholder" in r.stdout and not any(f'("{name_line[:50]}' in l for l in r.stdout.splitlines()),
              '4. a line made only of bot names is not flagged as a placeholder')
        # finalize in English and render
        dr['lang'] = 'en'
        for b in dr['bots']: b['issue'] = 'Test issue'
        fx = next(f for f in dr['bots'] if f['id'] == t2.F)['findings'][0]
        fx['now'].append(dict(date='03/02', chat=t2.NAMES[t2.E], quote={'orig': 'Stay on the notes goal please'}))
        fx['too_early'] = True
        json.dump(dr, open(f'{W}/findings_draft.json', 'w'))
        run(f'{S}/build_findings.py', 'finalize', '--work', W)
        fz = json.load(open(f'{W}/findings.json'))
        check(not any('fix_candidates' in b for b in fz['bots']), '3. finalize drops the per-bot candidate list')
        r = run(f'{S}/make_report.py', f'{W}/findings.json', '--outdir', f'{W}/report', '--no-pdf')
        lede = open(f'{W}/report/lede.txt', encoding='utf-8').read().strip()
        h = open(next(os.path.join(f'{W}/report', x) for x in os.listdir(f'{W}/report') if x.endswith('.html')), encoding='utf-8').read()
        check(lede and re.search(r'opening sentence \(lede_(all|y|r|none)\)', r.stdout) and lede in h, '1. lede.txt holds the rendered opening sentence; its key is printed')
        check(os.path.exists(f'{W}/report/checks.txt') and ('checks: OK' in r.stdout or 'CHECK' in r.stdout), '2. make_report writes a whole-report check summary')
        check(f'<span class="who">You (in {t2.NAMES[t2.E]})</span>' in h, '5. a quote from another bot\'s chat is labelled "You (in X)"')
        check('<span class="tag">Too early to tell</span>' in h, '7. too_early shows the tag')
        check('Translated quotes show the original' not in h, '6. no translated-quote note without a translation')
        fz['fleet'][0]['now'].append(dict(date='', quote={'orig': t2.KO[1], 'translation': 'Write it shorter'}))
        fz['bots'][0]['issue'] = 'TODO fix me'
        json.dump(fz, open(f'{W}/f2.json', 'w'))
        r = run(f'{S}/make_report.py', f'{W}/f2.json', '--outdir', f'{W}/r2', '--no-pdf')
        h2 = open(next(os.path.join(f'{W}/r2', x) for x in os.listdir(f'{W}/r2') if x.endswith('.html')), encoding='utf-8').read()
        check('Translated quotes show the original below.' in h2, '6. the note appears when a translation exists')
        check('CHECK TODO text left in the report' in r.stdout and 'TODO' in open(f'{W}/r2/checks.txt').read(), '2. leftover TODO anywhere is reported')
        # 8. compare_runs
        shutil.copytree(W, os.path.join(root, 'w2')); f2 = json.load(open(os.path.join(root, 'w2', 'findings.json')))
        f2['bots'][0]['status'] = 'red' if f2['bots'][0]['status'] != 'red' else 'green'
        json.dump(f2, open(os.path.join(root, 'w2', 'findings.json'), 'w'))
        r = run(os.path.join(HERE, 'compare_runs.py'), f'a={W}', f'b={os.path.join(root, "w2")}')
        n = len(fz['bots'])
        check(f'status agreement: {n - 1}/{n} bots' in r.stdout and '**no**' in r.stdout and '| bot | a | b |' in r.stdout,
              '8. compare_runs prints the table and agreement')
        if '--keep' in sys.argv: print('kept:', root)
    finally:
        if '--keep' not in sys.argv: shutil.rmtree(root, ignore_errors=True)
    print(f'\n{"ALL PASSED" if not failures else f"{len(failures)} FAILED"}')
    sys.exit(1 if failures else 0)

if __name__ == '__main__':
    main()
