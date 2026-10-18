#!/usr/bin/env python3
"""Regression tests for iteration 2 of the skill eval (consistency between runs), on a synthetic fixture (fake text).
Run: python3 tests/test_iteration2.py [--keep]

 1. replay skips only the "self" recorded in replay.json (or --self); otherwise every bot is audited
 2. judge_inputs exports every reply of every bot (no word filter, no mode)
 3. --list does not repeat a bot message already shown as the previous item's reply
 4. --label: 7 columns, \\N / - for empty, echo with user text, user_start mismatch is an error, unlisted -> 'none'
 5. fixes after a topic's first incident carry incidents_after / active_days_after; a judged promise is one
 6. incidents in one working session across midnight are one occasion
 7. a request that is the last message in the data is not counted as unanswered
 8. --strict warns about leftover English placeholder text when lang is not English (marker, not detection)
 9. an evidence line with both quote and text is an error
"""
import json, os, re, shutil, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
S = os.path.join(ROOT, 'skills', 'audit-my-bots', 'scripts')
sys.path.insert(0, HERE); sys.path.insert(0, S)
import make_fixture as mf

E, F, K, G = (f'cccccccc-0000-4000-8000-00000000000{i}' for i in (1, 2, 3, 4))
NAMES = {E: 'Draft Helper', F: 'Note Helper', K: 'Diary Helper', G: 'Auditor (self)'}
KO = ['\uc624\ub298 \uc77c\uae30 \uc368\uc918', '\ub354 \uc9e7\uac8c \uc368\uc918', '\uace0\ub9c8\uc6cc\uc694']  # fake Korean lines
failures = []

def run(*args, ok=True):
    r = subprocess.run([sys.executable, *args], capture_output=True, text=True)
    if ok and r.returncode != 0:
        print(r.stdout, r.stderr); raise SystemExit(f'FAILED: {" ".join(args)}')
    return r

def check(cond, msg):
    print(('PASS ' if cond else 'FAIL ') + msg)
    if not cond: failures.append(msg)

LONG = ('This is the first draft of the plan. It has a long intro about the history of the project. '
        'The middle part lists every step with background. Each step is explained again in detail. ') * 3

def build(root):
    e = mf.convo([   # one late session crossing midnight: three corrections, all the same topic
        (0, 22, 0, 'u', 'Design a tool for my notes'), (0, 22, 1, 'b', 'Here is design A. [fake]'),
        (0, 22, 5, 'u', 'No, keep it to the notes goal'), (0, 22, 6, 'b', 'Here is design B. [fake]'),
        (0, 23, 30, 'u', 'Again, keep it to the notes goal'), (0, 23, 31, 'b', 'Here is design C. [fake]'),
        (0, 25, 0, 'u', 'Stay on the notes goal please'), (0, 25, 1, 'b', 'Here is design D. [fake]'),
    ])
    f = mf.convo([
        (0, 9, 0, 'u', 'Summarise my notes'), (0, 9, 1, 'b', LONG),
        (0, 9, 5, 'u', 'Too long, the intro is useless'), (0, 9, 6, 'b', 'Okay, I will keep summaries short from now on. [fake]'),
        (2, 9, 0, 'u', 'Summarise the meeting'), (2, 9, 1, 'b', 'A long summary again. [fake]'),
        (2, 9, 5, 'u', 'Too long again'), (2, 9, 6, 'b', 'Shorter. [fake]'),
        (2, 10, 0, 'remember', 'Keep summaries under five lines'),
        (4, 9, 0, 'u', 'Summarise the call'), (4, 9, 1, 'b', 'A long summary once more. [fake]'),
        (4, 9, 5, 'u', 'Still too long'), (4, 9, 6, 'b', 'Short. [fake]'),
        (5, 9, 0, 'u', 'Thanks, that works'), (5, 9, 1, 'b', 'Here is the memo you asked for.\n' + LONG + 'From now on, all staff send summaries by Friday. ' + LONG),
        (5, 10, 0, 'u', 'And the code?'), (5, 10, 1, 'b', 'Sure:\n```\n# from now on use v2\n```\nThat is all. [fake]'),
        (6, 9, 0, 'u', 'Summarise the doc'), (6, 9, 1, 'b', 'Short summary. [fake]'),
        (7, 9, 0, 'u', 'Any update on the doc?'),   # last message in the data, no reply yet
    ])
    k = mf.convo([
        (1, 9, 0, 'u', KO[0]), (1, 9, 1, 'b', 'A long diary entry. [fake]'),
        (1, 9, 5, 'u', KO[1]), (1, 9, 6, 'b', 'A short entry. [fake]'),
        (1, 9, 9, 'u', 'too long, shorter'), (1, 9, 10, 'b', 'Shorter. [fake]'),
        (1, 9, 15, 'u', KO[2]), (1, 9, 16, 'b', 'You are welcome. [fake]'),
    ])
    g = mf.convo([(0, 9, 0, 'u', 'Audit my bots'), (0, 9, 1, 'b', 'Done. [fake]')])
    R = os.path.join(root, 'replay'); os.makedirs(R)
    for aid, conv in ((E, e), (F, f), (K, k), (G, g)):
        mf.write_pages(aid, NAMES[aid], conv, size=6, root=os.path.join(R, 'transcripts'), prefix='page_')
    json.dump([dict(id=x, name=NAMES[x], description='') for x in (E, F, K, G)], open(f'{R}/bots.json', 'w'))
    json.dump({'now': '2030-03-09 09:00', 'self': G}, open(f'{R}/replay.json', 'w'))
    return R

def main():
    root = tempfile.mkdtemp(prefix='bot-audit-it2-'); W = os.path.join(root, 'work')
    try:
        R = build(root)
        # 1. self from replay.json
        r = run(f'{S}/sessions.py', 'replay', '--work', W, '--from', R)
        bots = json.load(open(f'{W}/bots.json'))
        check(len(bots) == 3 and G not in {b['id'] for b in bots}, '1. replay skips the "self" recorded in replay.json')
        W0 = os.path.join(root, 'w0'); json.dump({'now': '2030-03-09 09:00'}, open(f'{R}/replay.json', 'w'))
        run(f'{S}/sessions.py', 'replay', '--work', W0, '--from', R)
        check(len(json.load(open(f'{W0}/bots.json'))) == 4, '1. without a recorded self, every listed bot is audited')
        run(f'{S}/sessions.py', 'parse', '--work', W)
        # 2. every reply, no mode
        r = run(f'{S}/judge_inputs.py', '--work', W)
        check(f'{NAMES[K]}: 3 items' in r.stdout and 'mode' not in r.stdout and 'Latin' not in r.stdout, '2. every reply of every bot is exported (no word filter, no mode)')
        ji = json.load(open(f'{W}/judge_inputs.json'))
        # 3. compact list
        r = run(f'{S}/judge_inputs.py', '--work', W, '--list')
        check(r.stdout.count('Here is design B') == 1 and '(= next> of #' in r.stdout, '3. --list shows each bot message once')
        r2 = run(f'{S}/judge_inputs.py', '--work', W, '--list', '--short')
        check(len(r2.stdout) < len(r.stdout) and re.search(r'-- \d+ items \(#\d+-#\d+\), [\d.]+ KB; (next batch: --from \d+|that was the last item)', r2.stdout)
              and 'Too long, the intro is useless' in r2.stdout, '3. --short keeps user text, cuts bot text, and reports the batch size')
        # 4. labels
        byu = {x['user']: x for x in ji}
        rows = [(byu['No, keep it to the notes goal'], 'No, keep', ''), (byu['Again, keep it to the notes goal'], 'Again', ''),
                (byu['Stay on the notes goal please'], 'Stay on', ''), (byu['Too long, the intro is useless'], 'Too long, the', 'yes'),
                (byu['Too long again'], 'Too long ag', ''), (byu['Still too long'], 'Still', '')]
        tsv = ''.join(f"{x['n']}\tcorrection\t{'scope_selection' if x['bot'] == E else 'format_length'}\thigh\t{x['user'][:8]}\t{p or chr(92) + 'N'}\t{s}\n"
                      for x, s, p in rows)
        tsv += f"{byu['Thanks, that works']['n']}\tpreference\tformat_length\tmedium\t-\t-\tThanks\n"
        open(f'{W}/labels.tsv', 'w').write(tsv)
        r = run(f'{S}/judge_inputs.py', '--work', W, '--label', f'{W}/labels.tsv')
        lab = json.load(open(f'{W}/labels.json'))
        kq = byu['Summarise the meeting']['key'] if 'Summarise the meeting' in byu else None
        others = [v for k, v in lab.items() if not v['label'] and v['type'] != 'preference']
        check('user: Too long, the intro is useless' in r.stdout and sum(v['label'] for v in lab.values()) == 6
              and others and all(v['type'] == 'none' for v in others), '4. --label echoes user text; unlisted items are type none')
        pf = lab[byu['Thanks, that works']['key']]
        check(pf['type'] == 'preference' and pf['topic'] == 'format_length' and pf['evidence'] == ''
              and lab[byu['Too long, the intro is useless']['key']].get('fix_promised') is True,
              '4. preferences keep a topic; - and \\N are empty; promised is recorded')
        open(f'{W}/bad.tsv', 'w').write(f"{byu['Too long again']['n']}\tcorrection\tformat_length\thigh\tx\t-\tStill\n")
        r = run(f'{S}/judge_inputs.py', '--work', W, '--label', f'{W}/bad.tsv', ok=False)
        check(r.returncode != 0 and 'off by one' in r.stdout, '4. a user_start mismatch is an error')
        run(f'{S}/judge_inputs.py', '--work', W, '--label', f'{W}/labels.tsv')
        # 5-7. diagnostics
        run(f'{S}/diagnostics.py', '--work', W)
        d = json.load(open(f'{W}/diag.json'))
        ge = d['bots'][E]['correction_topics']['scope_selection']
        check(ge['incidents'] == 3 and ge['occasions'] == 1, '6. three incidents in one session across midnight: one occasion')
        gf = d['bots'][F]['correction_topics']['format_length']
        fxt = {f['id']: f for f in d['bots'][F]['fixes']}
        fc = {fxt[c['id']]['kind']: c for c in gf['fixes_after']}
        check(len(fxt) == 2 and not any('all staff' in f['text'] or 'v2' in f['text'] for f in fxt.values()),
              '5. fixes are memory saves and judged promises only ("from now on" in drafted text or code is not one)')
        check(gf['occasions'] == 3 and fc.get('bot_promised', {}).get('incidents_after') == 2
              and fc.get('memory_write', {}).get('incidents_after') == 1 and fc['memory_write']['active_days_after'] == 4,
              '5. fixes (incl. a judged promise) carry incidents_after and active_days_after')
        lastref = f"{d['bots'][F]['ref_prefix']}:" 
        check(not d['bots'][F].get('waits') and len(d['bots'][F]['unanswered_at_end']) == 1 and d['bots'][F]['unanswered_at_end'][0].startswith(lastref),
              '7. the last message in the data is not a wait; it is listed as unanswered at the end')
        # 8-9. skeleton and finalize
        run(f'{S}/build_findings.py', 'skeleton', '--work', W, '--lang', 'ko')
        import helpers
        dr = helpers.fill(W, lang='ko')
        dr['fleet'][0]['title'] = 'Keep / clean-up'   # left as the skeleton wrote it
        ref = helpers.ref_of(W, F, 'Too long, the intro is useless')
        next(b for b in dr['bots'] if b['id'] == F)['findings'] = [helpers.finding('Summary length (test)', ref, 'Too long, the intro is useless')]
        json.dump(dr, open(f'{W}/findings_draft.json', 'w'))
        r = run(f'{S}/build_findings.py', 'finalize', '--work', W, '--strict', ok=False)
        check(r.returncode != 0 and "skeleton's placeholder text" in r.stdout and 'fallback language' in r.stdout,
              '8. --strict flags leftover English placeholders and ui labels in a non-English report')
        dr['lang'] = 'en'; json.dump(dr, open(f'{W}/en.json', 'w'))
        r = run(f'{S}/build_findings.py', 'finalize', '--work', W, '--draft', f'{W}/en.json', '--strict', ok=False)
        check("skeleton's placeholder text" not in r.stdout and r.returncode == 0, '8. no placeholder warning when the report is in English')
        x = json.loads(json.dumps(dr)); next(b for b in x['bots'] if b['id'] == F)['findings'][0]['now'][0]['text'] = 'extra'
        json.dump(x, open(f'{W}/bad.json', 'w'))
        r = run(f'{S}/build_findings.py', 'finalize', '--work', W, '--draft', f'{W}/bad.json', ok=False)
        check(r.returncode != 0 and 'both "quote" and "text"' in r.stdout, '9. an evidence line with quote and text is an error')
        fz = json.load(open(f'{W}/findings.json')) if os.path.exists(f'{W}/findings.json') else {}
        check('_skeleton' not in fz, '8. finalize drops the placeholder marker')
        if '--keep' in sys.argv: print('kept:', root)
    finally:
        if '--keep' not in sys.argv: shutil.rmtree(root, ignore_errors=True)
    print(f'\n{"ALL PASSED" if not failures else f"{len(failures)} FAILED"}')
    sys.exit(1 if failures else 0)

if __name__ == '__main__':
    main()
