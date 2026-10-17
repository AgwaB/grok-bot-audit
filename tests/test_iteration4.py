#!/usr/bin/env python3
"""Regression tests for iteration 4 of the skill eval, on synthetic fixtures (fake bots, fake text).
Run: python3 tests/test_iteration4.py [--keep]

 1. --list without --to prints one batch cut by size (about 10 KB) and the --from of the next batch; batches cover every
    item once, and chats in a non-Latin script get fewer items per batch (so SKILL.md names no fixed count)
 2. evidence "who": "bot" is a keyword: shown as ui.who_bot (default: the bot's name), never as the English word;
    in a fleet item it is an error
 3. the English fallback opening sentences are count-neutral (no "1 need work")
 4. (option order and fixed strings: documentation, checked in 9)
 5. fix candidates: an old fix an incident came after is never cut by the cap; left-out saves are counted
    (fix_check_omitted); link lists never become fix or promise candidates
 6. (one-off mistakes vs criteria: documentation, checked in 9)
 7. (secrets the user typed, bots not in the list: documentation, checked in 9)
 8. a section with only information items shows ui.expand_info, not a count; the footer adds the "quotes are word
    for word" sentence (ui.footer_q) only when the report has a quote; untranslated conditional labels are flagged
 9. documentation: no fixed batch size, preference vs one-off rule, secrets and unlisted bots, score.basis is
    internal, option order and translated fixed strings, replay self; no Hangul anywhere in the repository
10. replay prints what it skipped as self; a bot that shares the tester's name is audited unless its id is self
"""
import glob, json, os, re, shutil, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
SK = os.path.join(ROOT, 'skills', 'audit-my-bots'); S = os.path.join(SK, 'scripts')
sys.path.insert(0, HERE); sys.path.insert(0, S)
import make_fixture as mf
import make_report as mr
failures = []

M, A = 'dddddddd-0000-4000-8000-000000000001', 'dddddddd-0000-4000-8000-0000000000aa'
NAMES = {M: 'Memo Helper', A: 'Auditor'}
LONG = 'A long summary with an intro, background and every detail repeated twice. [fake] ' * 4
CJK = '\u65e5\u672c\u8a9e\u306e\u30e1\u30e2'   # fake Japanese text (non-Latin script)

def run(*args, ok=True):
    r = subprocess.run([sys.executable, *args], capture_output=True, text=True)
    if ok and r.returncode != 0:
        print(r.stdout, r.stderr); raise SystemExit(f'FAILED: {" ".join(args)}')
    return r

def check(cond, msg):
    print(('PASS ' if cond else 'FAIL ') + msg)
    if not cond: failures.append(msg)

def build(root):
    script = [
        (0, 9, 0, 'u', 'Summarise the report'), (0, 9, 1, 'b', LONG),
        (0, 9, 5, 'u', 'Too long, cut it down'), (0, 9, 6, 'b', 'Okay. From now on I will keep summaries short. [fake]'),
        (1, 9, 0, 'u', 'Any sources?'),
        (1, 9, 1, 'b', "Sources:\n- [I'll send updates](https://example.com/c)\n- [Going forward: the plan](https://example.com/a)"),
        (1, 9, 5, 'u', 'hello'), (1, 9, 6, 'b', 'Hi! [fake]'),
        (2, 9, 0, 'u', 'Summarise the call'), (2, 9, 1, 'b', LONG),
        (2, 9, 5, 'u', 'Too long again'), (2, 9, 6, 'b', 'Shorter. [fake]'),
    ]
    for i in range(15):   # many later memory saves with no incident after them
        script += [(3 + i, 9, 0, 'u', f'Note fact {i}'), (3 + i, 9, 1, 'remember', f'Fake fact number {i} about the user'),
                   (3 + i, 9, 2, 'b', 'Noted. [fake]')]
    script += [(19, 9, 0, 'u', 'Make the weekly memo'), (19, 9, 1, 'b', "I'll let you know when it is done. [fake]"),
               (19, 9, 30, 'u', 'hello?'), (19, 9, 31, 'b', 'Here it is. [fake]')]
    m = mf.convo(script)
    a = mf.convo([(0, 8, 0, 'u', 'Audit my bots'), (0, 8, 1, 'b', 'Done. [fake]')])
    R = os.path.join(root, 'replay'); os.makedirs(R)
    for aid, conv in ((M, m), (A, a)):
        mf.write_pages(aid, NAMES[aid], conv, size=10, root=os.path.join(R, 'transcripts'), prefix='page_')
    json.dump([dict(id=x, name=NAMES[x], description='Fake test bot.') for x in (M, A)], open(f'{R}/bots.json', 'w'))
    json.dump({'now': '2030-03-22 09:00'}, open(f'{R}/replay.json', 'w'))   # no self recorded
    return R

def batches(W):
    seen, sizes, start = [], [], 1
    for _ in range(50):
        r = run(f'{S}/judge_inputs.py', '--work', W, '--list', '--short', '--from', str(start))
        nums = [int(x) for x in re.findall(r'^#(\d+) ', r.stdout, re.M)]
        last = r.stdout.strip().splitlines()[-1]
        seen += nums; sizes.append((len(nums), len(r.stdout.encode('utf-8'))))
        m = re.search(r'next batch: --from (\d+)', last)
        if not m: return seen, sizes, last
        start = int(m.group(1))
    return seen, sizes, 'loop'

def test_batches(root):
    def items(text, n, bot):
        return [dict(n=i + 1, key=f'{bot}:{i}', bot=bot, bot_name='X', ts='2030-03-01 09:00', request='',
                     prev_bot=f'Bot message {i}. ' + text * 20, user=(text + ' ') * 40, next_bot=f'Reply {i}. ' + text * 20,
                     signal='(all replies)') for i in range(n)]
    out = {}
    for name, text in (('latin', 'plain words'), ('cjk', CJK)):
        W = os.path.join(root, 'list-' + name); os.makedirs(W)
        json.dump(items(text, 120, 'b' + name), open(f'{W}/judge_inputs.json', 'w'), ensure_ascii=False)
        seen, sizes, last = batches(W)
        out[name] = sizes
        check(sorted(seen) == list(range(1, 121)) and len(seen) == 120 and 'last item' in last,
              f'1. size-cut batches cover every item once ({name}: {len(sizes)} batches)')
        big = max(s for _, s in sizes[:-1]) if len(sizes) > 1 else 0
        check(len(sizes) > 1 and big < 14 * 1024, f'1. each batch stays near 10 KB ({name}: largest {big} bytes)')
    check(out['cjk'][0][0] < out['latin'][0][0], f"1. a non-Latin script fits fewer items per batch "
          f"({out['cjk'][0][0]} vs {out['latin'][0][0]}), so the count can't be fixed")
    W = os.path.join(root, 'list-latin')
    r = run(f'{S}/judge_inputs.py', '--work', W, '--list', '--short', '--from', '1', '--to', '3')
    check(re.findall(r'^#(\d+) ', r.stdout, re.M) == ['1', '2', '3'] and 'fit in 10 KB' in r.stdout, '1. --to still lists an exact range')

def report(d, ui=None):
    mr.set_ui(ui or {}); return mr.page(d)

def test_render():
    info = dict(title='Went quiet once', info=True, now=[dict(date='', text='No reply for 7 hours on 03/02')], fix='Nothing to do.')
    d = dict(schema=3, lang='en', title='Bot audit report', date='2030-03-22', top3=[],
             bots=[dict(id=M, name='Memo Helper', status='green', issue='Working well', why='No repeated problem.', findings=[dict(info)])],
             fleet=[dict(info, title='Went quiet everywhere'), dict(info, title='Keep / clean-up candidates', keep=True)])
    h = report(d)
    check(h.count('Show details') == 2 and 'Show proposals' not in h, '8. sections with only information items show expand_info, not a count')
    foot = re.search(r'<footer>(.*?)</footer>', h).group(1)
    check(foot == 'Built from the 2030-03-22 audit.', '8. with no quote, the footer is only the base sentence')
    d['bots'][0]['findings'].append(dict(title='Long summaries', now=[dict(date='03/01', who='bot', quote={'orig': 'From now on I will keep summaries short.'})],
                                         fix='Save the length.', copy='Keep summaries to five lines.', copy_kind='memory',
                                         score=dict(impact=1, confidence='medium', effort=1, reversibility=1.0, basis='test')))
    h = report(d)
    check('Quotes are taken word for word from the chats.' in re.search(r'<footer>(.*?)</footer>', h).group(1), '8. with a quote, footer_q is added')
    check('Show proposals (1)' in h and h.count('Show details') == 1, '8. the toggle counts proposals only, as the table does')
    check(re.findall(r'<span class="who">([^<]*)</span>', h) == ['Memo Helper'],
          '2. "who": "bot" shows the bot\'s name by default, never the English word')
    d['bots'][0]['findings'][1]['now'][0]['who'] = 'Bot'
    h = report(d, {'who_bot': '{bot} said'})
    check('<span class="who">Memo Helper said</span>' in h, '2. "who": "Bot" (any case) is the keyword too; ui.who_bot is the host bot\'s label')
    tr = {k: ('T-' + v if isinstance(v, str) else v) for k, v in mr.UI_DEFAULT.items()}
    tr.pop('footer_q')
    d['lang'] = 'ja'; mr.set_ui(tr); h = mr.page(d)
    probs = mr.check_report(d, h)
    check(any('footer_q' in p for p in probs) and not any('who_bot' in p for p in probs) and not any('expand_info' in p for p in probs),
          '8. an untranslated footer_q is flagged when used; a placeholder-only who_bot is never flagged')
    mr.set_ui({})
    c = dict(bots=[dict(status='yellow'), dict(status='red'), dict(status='green')])
    texts = [mr.UI_DEFAULT[k].format(n=1, y=1, r=1) for k in mr.LEDE_KEYS]
    check(not any(re.search(r'\b1 (need|should|bots)\b', t) for t in texts) and mr.lede_of(c)[0] == 'lede_all',
          '3. the English fallback ledes are count-neutral (' + texts[0] + ')')

def test_pipeline(root):
    R = build(root); W = os.path.join(root, 'work')
    r = run(f'{S}/sessions.py', 'replay', '--work', W, '--from', R)
    bots = json.load(open(f'{W}/bots.json'))
    check('No self recorded; nothing skipped.' in r.stdout and A in {b['id'] for b in bots},
          '10. with no self recorded, a bot named like the tester is audited and replay says nothing was skipped')
    r2 = run(f'{S}/sessions.py', 'replay', '--work', os.path.join(root, 'w-self'), '--from', R, '--self', A)
    check(f'Skipped as self (the bot that ran the audit): {NAMES[A]}.' in r2.stdout
          and A not in {b['id'] for b in json.load(open(os.path.join(root, 'w-self', 'bots.json')))}, '10. replay prints the bot it skipped as self')
    run(f'{S}/sessions.py', 'parse', '--work', W)
    run(f'{S}/judge_inputs.py', '--work', W, '--all')
    ji = json.load(open(f'{W}/judge_inputs.json')); byu = {x['user']: x for x in ji}
    open(f'{W}/labels.tsv', 'w').write(''.join(f"{byu[u]['n']}\tcorrection\tformat_length\thigh\t-\t-\t{u[:6]}\n"
                                               for u in ('Too long, cut it down', 'Too long again')))
    run(f'{S}/judge_inputs.py', '--work', W, '--label', f'{W}/labels.tsv')
    run(f'{S}/diagnostics.py', '--work', W)
    d = json.load(open(f'{W}/diag.json')); b = d['bots'][M]; g = b['groups']['format_length']
    texts = {f['id']: f['text'] for f in b['fix_events']}
    early = [c for c in g['fix_candidates'] if c['incidents_after']]
    check(len(early) == 1 and 'From now on I will keep summaries short' in texts[early[0]['id']],
          '5. the early fix an incident came after is kept, though 15 saves came later')
    later = [c for c in g['fix_candidates'] if not c['incidents_after']]
    om = g.get('fix_candidates_omitted') or {}
    check(len(later) == 12 and om.get('count') == 3 and om.get('first') and om.get('last'), '5. 12 latest of the rest kept; 3 left out are counted')
    check(not any('Going forward' in t or 'https://' in t for t in texts.values()), '5. a link list is never a fix candidate')
    pr = b['promise_candidates']
    check(len(pr) == 1 and pr[0]['bot'].startswith("I'll let you know"), '5. a link list is never a promise; a real promise still is')
    run(f'{S}/build_findings.py', 'skeleton', '--work', W, '--lang', 'en')
    dr = json.load(open(f'{W}/findings_draft.json'))
    fm = next(x for x in dr['bots'] if x['id'] == M)['findings'][0]
    check(fm.get('fix_check_omitted', {}).get('count') == 3, '5. the draft finding carries fix_check_omitted')
    dr['date_label'] = 'March 22, 2030'
    for x in dr['bots']:
        x['issue'] = 'Test issue'; x.pop('needs_review', None)
        for f in x['findings']: f.pop('needs_review', None); f.pop('fix_check', None)
    for f in dr['fleet']: f.pop('needs_review', None)
    dr['fleet'][0]['now'].append(dict(date='03/01', who='bot', quote={'orig': 'Shorter.'}))
    json.dump(dr, open(f'{W}/findings_draft.json', 'w'))
    r = run(f'{S}/build_findings.py', 'finalize', '--work', W, ok=False)
    check(r.returncode == 1 and '"who": "bot" means this bot, but a fleet item has none' in r.stdout, '2. "who": "bot" in a fleet item is an error')
    dr['fleet'][0]['now'][-1]['who'] = NAMES[M]
    json.dump(dr, open(f'{W}/findings_draft.json', 'w'))
    run(f'{S}/build_findings.py', 'finalize', '--work', W, '--strict')
    fz = json.load(open(f'{W}/findings.json'))
    check(not any('fix_check_omitted' in f for x in fz['bots'] for f in x['findings'] + x.get('more', [])), '5. finalize drops fix_check_omitted')

def test_docs():
    rd = lambda *p: open(os.path.join(SK, *p), encoding='utf-8').read()
    skill, crit, wr, sch, rub = rd('SKILL.md'), rd('references', 'criteria.md'), rd('references', 'writing.md'), \
        rd('references', 'findings-schema.md'), rd('references', 'rubric_correction.md')
    ev = open(os.path.join(HERE, 'EVAL.md'), encoding='utf-8').read()
    check('--to 50' not in skill and 'about 50' not in skill + rub and '`--from` of the next batch' in skill,
          '9/1. no fixed batch size in SKILL.md or the rubric')
    check('single correction' not in crit and 'A one-off correction never does' in crit and 'preference' in skill.split('## 0.')[0],
          '9/6. criteria and the safety rule agree: no rule from one mistake; a stated preference may be proposed')
    check('Secrets the user typed' in crit and 'Bots not in the list' in crit and 'Secrets the user typed' in wr and 'removed' in wr,
          '9/7. user-typed secrets and unlisted bots are specified')
    check('never shown in the report' in crit and 'never shown in the report' in sch and 'internal' in wr, '9/9. score.basis is documented as internal')
    check('## Chat message and options' in wr and 'None for now' in wr and 'report order' in skill and "user's language" in skill.split('## 9.')[1],
          '9/4. option order and translated fixed strings are specified')
    check('"self": "<its agent id>"' in ev and 'Never\nskip by name' in ev.replace('Never skip', 'Never\nskip') and 'prints what it skipped' in skill,
          '9/10. replay self is documented in EVAL.md and SKILL.md')
    check(len(skill.splitlines()) <= 172, f'9. SKILL.md stays short ({len(skill.splitlines())} lines)')
    hangul = re.compile('[\u1100-\u11ff\u3130-\u318f\uac00-\ud7af]')
    bad = []
    for p in glob.glob(os.path.join(ROOT, '**', '*'), recursive=True):
        if '/.git/' in p or not os.path.isfile(p) or p.endswith(('.png', '.pyc')): continue
        try: t = open(p, encoding='utf-8').read()
        except UnicodeDecodeError: continue
        if hangul.search(t): bad.append(os.path.relpath(p, ROOT))
    check(not bad, '9/global. no Hangul text anywhere in the repository' + (f': {bad}' if bad else ''))

def main():
    root = tempfile.mkdtemp(prefix='bot-audit-it4-')
    try:
        test_batches(root); test_render(); test_pipeline(root); test_docs()
        if '--keep' in sys.argv: print('kept:', root)
    finally:
        if '--keep' not in sys.argv: shutil.rmtree(root, ignore_errors=True)
    print(f'\n{"ALL PASSED" if not failures else f"{len(failures)} FAILED"}')
    sys.exit(1 if failures else 0)

if __name__ == '__main__':
    main()
