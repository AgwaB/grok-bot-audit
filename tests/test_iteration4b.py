#!/usr/bin/env python3
"""Regression tests for iteration 4b of the skill eval (synthetic replays: fake bots, fake text).
Run: python3 tests/test_iteration4b.py [--keep]

A. shared cause: the paste test is in criteria.md section 5; finalize --strict refuses a fix left as TODO
B2. an all-kept fleet (only the keep line) renders as one compact line: no numbered item (the stray "1"), no box;
   with a clean-up bot the full numbered item stays
B4. evidence with no date on any line has no blank date column
B1/B3/B5/B6. documentation: weekly re-check is a yes/no choice; one test-mode note at step 0 (replay then parse,
   replay `now` for report dates, real time zone for the weekly offer, not the replay's UTC offset, evidence dates as
   recorded); --lang falls back to English; rewrite ui.lede_* before finalize; the paste test is in criteria.md
"""
import json, os, re, shutil, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
SK = os.path.join(ROOT, 'skills', 'audit-my-bots'); S = os.path.join(SK, 'scripts')
sys.path.insert(0, S)
import make_report as mr
sys.path.insert(0, HERE)
import helpers
failures = []

def run(*args, ok=True):
    r = subprocess.run([sys.executable, *args], capture_output=True, text=True)
    if ok and r.returncode != 0:
        print(r.stdout, r.stderr); raise SystemExit(f'FAILED: {" ".join(args)}')
    return r

def check(cond, msg):
    print(('PASS ' if cond else 'FAIL ') + msg)
    if not cond: failures.append(msg)

def skeleton(root, replay):
    W = os.path.join(root, 'w-' + replay)
    run(f'{S}/sessions.py', 'replay', '--work', W, '--from', os.path.join(root, replay))
    run(f'{S}/sessions.py', 'parse', '--work', W)
    run(f'{S}/judge_inputs.py', '--work', W)
    ji = json.load(open(f'{W}/judge_inputs.json', encoding='utf-8'))
    lab = json.load(open(os.path.join(HERE, 'fixtures', 'labels_by_text.json'), encoding='utf-8'))
    rows = []
    for x in ji:
        l = lab.get(x['user'])
        if l and l.get('label'):
            rows.append(f"{x['n']}\t{l['type']}\t{l['topic']}\t{l['confidence']}\t-\t-\t{x['user'][:6]}\n")
    open(f'{W}/labels.tsv', 'w', encoding='utf-8').write(''.join(rows))
    run(f'{S}/judge_inputs.py', '--work', W, '--label', f'{W}/labels.tsv')
    run(f'{S}/diagnostics.py', '--work', W)
    run(f'{S}/build_findings.py', 'skeleton', '--work', W, '--lang', 'en')
    return W, json.load(open(f'{W}/findings_draft.json', encoding='utf-8'))

GENERIC = re.compile(r'\b(ambiguous|unclear|when in doubt|be (more )?careful|double-check)\b', re.I)

def fleet_html(h):
    return h.split('<h2>Across all bots</h2>', 1)[1].split('<footer>', 1)[0]

def test_generic_default(root):
    W, dr = skeleton(root, 'replay-synth-ja')
    d = json.load(open(f'{W}/diag.json')); old = min(d['bots'].values(), key=lambda b: b['share'])['name']
    cu = dict(title='Barely used (test)', cleanup=True, short='Show me how to clean up (test)', fix='See the keep item (test).',
              now=[dict(date='', ref=helpers.any_ref(W, old), text='Last request (test)')], score=dict(impact=1, confidence='medium', effort=1, reversibility=0.6, basis='test'))
    other = next(b['name'] for b in d['bots'].values() if b['name'] != old and b['real_requests'])
    mis = helpers.finding('Misreads (test)', helpers.any_ref(W, other), fix='TODO name the details it must confirm first')
    dr = helpers.fill(W, status={old: 'red', other: 'yellow'}, findings={old: [cu], other: [mis]})
    r = run(f'{S}/build_findings.py', 'finalize', '--work', W, '--strict', ok=False)
    check(r.returncode == 1 and 'fix or short still has TODO' in r.stdout, 'A. finalize --strict refuses a fix left as TODO')
    next(b for b in dr['bots'] if b['name'] == other)['findings'][0]['fix'] = 'Before booking, confirm lodging type, meal and time of day (fake).'
    json.dump(dr, open(f'{W}/findings_draft.json', 'w'), ensure_ascii=False)
    run(f'{S}/build_findings.py', 'finalize', '--work', W, '--strict')
    fz = json.load(open(f'{W}/findings.json', encoding='utf-8'))
    mr.set_ui({}); h = fleet_html(mr.page(fz))
    check('id="bot-fleet"' in h and '<div class="no">' in h, 'B2. a fleet with a clean-up candidate keeps the full numbered items')
    crit = open(os.path.join(SK, 'references', 'criteria.md'), encoding='utf-8').read()
    check('paste test' in crit and 'Ask if the request is ambiguous.' in crit and 'lodging' not in crit and 'hostel' not in crit,
          'A. criteria.md section 5 has the paste test, with generic examples that are not a fixture answer')

def test_all_keep(root):
    W, dr = skeleton(root, 'replay-tiny')
    keep = [f for f in dr['fleet'] if f.get('keep')]
    check(len(dr['fleet']) == 1 and len(keep) == 1, 'B2. the skeleton has exactly one fleet item: the keep item')
    keep = [dict(keep[0], now=[dict(date='', text='Keep both (test).')], fix='Nothing to clean up (test).')]
    # the shape a host bot wrote in the iteration-4b tiny runs (no "keep" marker)
    for f in ([dict(title='Keep or clean up', now=[dict(date='', text='Keep both: A and B are in regular use.')],
                    fix='Nothing to clean up right now.', info=True)], keep or [dict(title='missing keep item', now=[], info=True)]):
        d = dict(schema=3, lang='en', title='Bot audit report', date='2030-03-04', top3=[],
                 bots=[dict(id='b1', name='Weather Buddy', status='green', issue='Working well', why='No repeated problem.', findings=[])],
                 fleet=f)
        mr.set_ui({}); h = mr.page(d); fh = fleet_html(h)
        check('<div class="no">' not in fh and 'id="bot-fleet"' not in fh and 'Show details' not in fh,
              'B2. an all-kept fleet shows no stray number and no box' + (' (keep marker)' if f[0].get('keep') else ' (no marker)'))
        txt = mr.visible(fh)
        check(T(f[0]['fix']) in txt and T(f[0]['now'][0]['text']) in txt, 'B2. the compact line keeps the keep text and the fix')
        d['lang'] = 'ja'; mr.set_ui({k: ('T-' + v if isinstance(v, str) else v) for k, v in mr.UI_DEFAULT.items()})
        check(not any('expand_info' in p for p in mr.check_report(d, mr.page(d)) if 'labels' in p),
              'B2. the compact fleet does not count as an info-only section for the label check')

def T(x): return mr.T(x)

def test_empty_dates():
    f = dict(title='Barely used', now=[dict(date='', text='Last request 02/01')], fix='Consider cleaning it up.', info=True)
    mr.set_ui({}); h = mr.finding(f, 'X', 'b1', 1)
    check('<span class="d"></span>' not in h and 'class="ev nd"' in h, 'B4. evidence with no date has no blank date column')
    f['now'].append(dict(date='03/01', text='Another fact'))
    h = mr.finding(f, 'X', 'b1', 1)
    check('class="ev"' in h and h.count('<span class="d">') == 2, 'B4. with any dated line, the date column stays aligned')

def test_docs():
    skill = open(os.path.join(SK, 'SKILL.md'), encoding='utf-8').read()
    s0 = skill.split('## 0.')[1].split('## 1.')[0]
    check('Test mode' in s0 and 'replay' in s0 and 'parse' in s0 and "replay's `now`" in s0 and 'real time zone' in s0
          and 'UTC offset' in s0 and 'evidence dates stay as recorded' in s0, 'B3. one test-mode note at step 0 covers replay, dates and zones')
    s5 = skill.split('## 5.')[1].split('## 6.')[0]
    check('en if unclear' in s5, 'B5. step 5 --lang falls back to English')
    s6 = skill.split('## 6.')[1].split('## 7.')[0]
    check('ui.lede_*' in s6 and 'Then:' not in s6.split('ui.lede_*')[0] and '§5' in s6, 'B6/A. step 6: rewrite the used ui.lede_* before finalize; decision procedure')
    s9 = skill.split('## 9.')[1]
    check('yes/no' in s9 and 'every week' in s9, 'B1. the weekly re-check is a yes/no choice')
    check(len(skill.splitlines()) <= 172, f'SKILL.md stays short ({len(skill.splitlines())} lines)')

if __name__ == '__main__':
    root = tempfile.mkdtemp(prefix='bot-audit-it4b-')
    try:
        run(os.path.join(HERE, 'make_replay.py'), root)
        test_generic_default(root); test_all_keep(root); test_empty_dates(); test_docs()
    finally:
        if '--keep' in sys.argv: print('kept:', root)
        else: shutil.rmtree(root, ignore_errors=True)
    print('\nALL PASSED' if not failures else f'\n{len(failures)} FAILED')
    sys.exit(1 if failures else 0)
