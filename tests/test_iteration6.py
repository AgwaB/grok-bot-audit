#!/usr/bin/env python3
"""Regression tests for iteration 6 (synthetic replays: fake bots, fake text). Run: python3 tests/test_iteration6.py [--keep]

A. references carry no fixture answers: no test-fixture message or label text appears in any reference or SKILL.md
B. use counts routine runs: a bot typed to once whose routine still runs is not idle; a stopped routine is
C. age facts: a bot added late to an older fleet shows its own age next to the fleet's
D. rhythm facts: a bot used monthly has a typical gap of about a month; corrections come with a rate per 100 requests
E. every reply of every bot is a judge item, in any language and mixed with code; skipped cards and past-date memory
   facts are counted without words
F. the work folder is new and private per run (two runs never share it)
G. setup facts: pasted answers between bots, same-member groups, browser on a plugin site, memory facts, routine run
   spacing; setup items the host writes from them finalize and render in their own report section
H. weekly re-check: summary.json and --previous (UNCHANGED / CHANGED); routine rules documented; text for another
   bot goes as a message to remember, not into a description field
"""
import datetime as dt, glob, json, os, re, shutil, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
SK = os.path.join(ROOT, 'skills', 'audit-my-bots'); S = os.path.join(SK, 'scripts')
sys.path.insert(0, S); sys.path.insert(0, HERE)
import make_fixture as mf
failures = []

def check(cond, msg):
    print(('PASS ' if cond else 'FAIL ') + msg)
    if not cond: failures.append(msg)

def run(*args, ok=True):
    r = subprocess.run([sys.executable, *args], capture_output=True, text=True)
    if ok and r.returncode != 0:
        print(r.stdout, r.stderr); raise SystemExit(f'FAILED: {" ".join(args)}')
    return r

def convo(script):
    out, n, k = [], 0, 0
    for d, h, m, who, text in sorted(script, key=lambda x: x[:3]):
        t = mf.BASE + dt.timedelta(days=d, hours=h - 9, minutes=m)
        if who == 'u': out.append(mf.user(t, text, n)); n += 1
        elif who == 'b': out += mf.bot(text, k); k += 1
        elif who == 'routine': out.append(mf.hidden(t, text[1:] if text.startswith('\x00') else '[routine] ' + text))   # \x00: a full hidden prompt
        elif who == 'skip': out.append(mf.hidden(t, f'Earlier you prompted the user and they moved on without responding ("{text}"). Treat it as skipped.'))
        elif who == 'mem': out.append(mf.memory(t, text))
        elif who == 'tool': out.append(dict(role='assistant', message=dict(content=[dict(type='tool_use', id=f'x{k}', name=text[0], input=text[1])]))); k += 1
    return out

def anchor(days=58):
    return [x for d in range(days) for x in ((d, 12, 0, 'u', f'Everyday question number {d} about item {d * 7}'), (d, 12, 1, 'b', f'Answer {d}. [fake]'))]

def fleet(root, name, bots, now, labels=None):
    """bots: {name: script}. Returns (W, diag, draft)."""
    R = os.path.join(root, name); W = os.path.join(root, 'w-' + name); tmp = R + '/_p'; os.makedirs(R)
    listing = []
    for i, (bn, sc) in enumerate(bots.items(), 1):
        bid = f'ffffffff-0000-4000-8000-{i:012d}'
        mf.write_pages(bid, bn, convo(sc), size=200, root=tmp); listing.append(dict(id=bid, name=bn, description=''))
    json.dump(listing, open(R + '/bots.json', 'w')); json.dump({'now': now}, open(R + '/replay.json', 'w'))
    for raw in sorted(glob.glob(tmp + '/*/*.txt')):
        run(f'{S}/sessions.py', 'save-page', '--work', R, f'{os.path.basename(os.path.dirname(raw))}={raw}')
    shutil.rmtree(tmp)
    run(f'{S}/sessions.py', 'replay', '--work', W, '--from', R); run(f'{S}/sessions.py', 'parse', '--work', W)
    out = run(f'{S}/judge_inputs.py', '--work', W).stdout
    items = json.load(open(W + '/judge_inputs.json'))
    lines = [f"{it['n']}\tcorrection\t{topic}\thigh\t-\t-\t{it['user'][:6]}\n" for it in items for t, topic in (labels or {}).items()
             if it['user'] == t]
    open(W + '/labels.tsv', 'w').write(''.join(lines))
    run(f'{S}/judge_inputs.py', '--work', W, '--label', W + '/labels.tsv')
    run(f'{S}/diagnostics.py', '--work', W); run(f'{S}/build_findings.py', 'skeleton', '--work', W, '--lang', 'en')
    diag = json.load(open(W + '/diag.json')); draft = json.load(open(W + '/findings_draft.json'))
    return W, {b['name']: b for b in diag['bots'].values()}, diag, draft, out

NOW = '2030-04-27 21:00'   # day 57.5 after mf.BASE

def test_no_fixture_text():
    texts = set(json.load(open(os.path.join(HERE, 'fixtures', 'labels_by_text.json'))))
    for entries in mf.CONVOS.values():
        for e in entries:
            for x in e['message']['content']:
                t = x.get('text') or (x.get('input') or {}).get('content') or ''
                t = re.sub(r'<[^>]+>|\[t\d+u\]|\[fake text\]|\[\u507d\u30c6\u30ad\u30b9\u30c8\]', '', t)
                texts |= {seg.strip() for seg in re.split(r'[\n"]', t) if len(seg.strip()) >= 12}
    docs = {p: open(p, encoding='utf-8').read() for p in glob.glob(os.path.join(SK, '**', '*.md'), recursive=True)}
    hits = [(os.path.basename(p), t) for t in texts for p, s in docs.items() if t in s]
    check(not hits, 'A. no fixture message or label text in SKILL.md or the references' + (f': {hits[:3]}' if hits else ''))
    names = [v['name'] for v in mf.BOTS.values()]
    hits = [(os.path.basename(p), n) for n in names for p, s in docs.items() if n in s]
    check(not hits, 'A. no fixture bot name in SKILL.md or the references' + (f': {hits[:3]}' if hits else ''))
    crit = docs[os.path.join(SK, 'references', 'criteria.md')]
    check('Same kind of action' in crit and 'list of past' in crit, 'A. the paste test rejects a rule that just lists unrelated misreads')

def test_cleanup(root):
    mb = [(0, 8, 0, 'u', 'Send me a brief every morning'), (0, 8, 1, 'b', 'Routine set. [fake]')] + \
         [x for d in range(1, 58) for x in ((d, 7, 0, 'routine', 'brief'), (d, 7, 1, 'b', f'Brief {d}. [fake]'))]
    old = [(0, 9, 0, 'u', 'Post a ticker every morning'), (0, 9, 1, 'b', 'Routine set. [fake]')] + \
          [x for d in range(1, 11) for x in ((d, 7, 30, 'routine', 't'), (d, 7, 31, 'b', f'Ticker {d}. [fake]'))]
    monthly = [(0, 20, 0, 'u', 'Summarise expenses by category'), (0, 20, 1, 'b', 'Summary. [fake]'),
               (28, 20, 0, 'u', 'Summarise expenses by category again'), (28, 20, 1, 'b', 'Summary. [fake]')]
    new = [(50, 18, 0, 'u', 'Weekly review please'), (50, 18, 1, 'b', 'Three wins. [fake]')]
    W, B, diag, draft, _ = fleet(root, 'cleanup', {'Brief Bot': mb, 'Stopped Bot': old, 'Monthly Bot': monthly, 'New Bot': new,
                                                   'Anchor': anchor()}, NOW)
    check(B['Brief Bot']['idle_days'] < 1 and B['Brief Bot']['idle_typed_days'] > 50 and B['Brief Bot']['routines']['runs'] == 57,
          'B. typed once, routine still running: idle counts the routine (idle_days vs idle_typed_days)')
    check(B['Stopped Bot']['idle_days'] > 40 and B['Stopped Bot']['routines']['last'][:10] == '2030-03-11', 'B. a routine that stopped long ago leaves the bot idle')
    check(B['Monthly Bot']['typical_gap_days'] == 28 and B['Monthly Bot']['active_days'] == 2, 'D. a monthly bot has a typical gap of 28 days')
    check(B['New Bot']['age_days'] < 10 and diag['fleet_age_days'] > 50, 'C. a bot added late shows its own age next to the fleet age')
    check(not any(k in json.dumps(draft) for k in ('status_suggested', 'too_new', 'faded')) and all(b['status'] == 'TODO' for b in draft['bots']),
          'B/C/D. the skeleton leaves every status to the host bot')

def test_rate_floor(root):
    many = [x for d in range(10, 50) for j in range(10) for x in ((d, 8, j * 2, 'u', f'Sort batch {d}-{j}'), (d, 8, j * 2 + 1, 'b', 'Sorted. [fake]'))]
    cor = {f'Too wordy again, number {i}': 'format_length' for i in range(3)}
    many += [x for i, d in enumerate((15, 30, 45)) for x in ((d, 9, 0, 'u', f'Too wordy again, number {i}'), (d, 9, 1, 'b', 'Shorter. [fake]'))]
    few = [x for d in range(10, 40) for x in ((d, 8, 0, 'u', f'Draft post {d}'), (d, 8, 1, 'b', 'Drafted. [fake]'))]
    cor2 = {f'Too formal again, take {i}': 'tone_style' for i in range(3)}
    few += [x for i, d in enumerate((12, 22, 32)) for x in ((d, 8, 2, 'u', f'Too formal again, take {i}'), (d, 8, 3, 'b', 'Casual. [fake]'))]
    W, B, *_ = fleet(root, 'rate', {'Sorter': many, 'Poster': few, 'Anchor': anchor()}, NOW, labels={**cor, **cor2})
    g, g2 = B['Sorter']['correction_topics']['format_length'], B['Poster']['correction_topics']['tone_style']
    check(g['incidents'] == 3 and g['occasions'] == 3 and g['per_100_requests'] < 1, f"D. 3 incidents in 403 requests: {g['per_100_requests']} per 100")
    check(g2['incidents'] == 3 and g2['per_100_requests'] > 5, f"D. 3 incidents in 33 requests: {g2['per_100_requests']} per 100")

def test_judge_all(root):
    ko = '\uc5d0 retry logic add \ud574\uc918, \ub85c check'   # fake Korean words between code
    es = [x for d in range(0, 20, 2) for x in ((d, 9, 0, 'u', 'Escribe un resumen del art\u00edculo de hoy'), (d, 9, 1, 'b', 'Resumen. [fake]'))]
    es += [(4, 9, 3, 'u', 'Demasiado largo, por favor'), (4, 9, 4, 'b', 'Vale. [fake]')]
    kc = [x for d in range(0, 20) for x in ((d, 9, 0, 'u', f'`load_{d}()` {ko}'), (d, 9, 1, 'b', 'Done. [fake]'))]
    en = [x for d in range(0, 20) for x in ((d, 9, 0, 'u', f'Summarise note {d}'), (d, 9, 1, 'b', 'Summary. [fake]'))]
    vague = [x for d in range(0, 30, 2) for x in ((d, 16, 0, 'u', 'do the thing'), (d, 16, 1, 'b', 'Which one? [fake]'), (d, 16, 2, 'skip', 'Which file?'))]
    nudge = [(1, 9, 0, 'u', 'Find the receipt'), (1, 9, 1, 'b', 'Looking now. [fake]'), (1, 11, 0, 'u', '\u3069\u3046?'), (1, 11, 1, 'b', 'Found it. [fake]'),
             (0, 9, 0, 'mem', [('2030-03-01', 'Flight booked for 2030-03-20.')])]
    W, B, diag, draft, out = fleet(root, 'mode', {'Spanish': es, 'KoCode': kc, 'English': en, 'Vague': vague, 'Nudge': nudge, 'Anchor': anchor()}, NOW)
    items = json.load(open(W + '/judge_inputs.json')); per = {}
    for it in items: per[it['bot_name']] = per.get(it['bot_name'], 0) + 1
    check(per['Spanish'] == 10 and per['KoCode'] == 19 and per['English'] == 19, f'E. every reply after a bot message is an item in any language ({per})')
    check(B['Vague']['skipped_questions']['count'] == 15, 'E. skipped question cards are counted')
    check(any(f.get('past_dates') == ['2030-03-20'] for f in B['Nudge']['memory']['facts']), 'E. a memory fact with a past date is marked, in any language')
    check(B['Vague']['repeated_texts'] and len(B['Vague']['repeated_texts'][0]['days']) == 15, 'E. the same text on many days is an exact repeat with its days')

def test_unique_w(root):
    skill = open(os.path.join(SK, 'SKILL.md'), encoding='utf-8').read()
    block = re.search(r'## 0\. Set up.*?```bash\n(.*?)```', skill, re.S).group(1)
    base = os.path.join(root, 'runs')
    script = block.replace('/workspace/bot-audit-run', base)
    env = dict(os.environ, SKILL=SK); env.pop('W', None)
    outs = [subprocess.run(['bash', '-c', script], capture_output=True, text=True, env=env).stdout.strip() for _ in range(2)]
    dirs = [os.path.dirname(o) for o in outs]
    check(len(set(dirs)) == 2 and all(os.path.isdir(d) for d in dirs), 'F. two runs on the same day get different work folders')
    check(all(oct(os.stat(d).st_mode & 0o777) == '0o700' for d in dirs), 'F. the work folder is private to this user (700)')
    check('date +%F)}' not in skill, 'F. the default work folder is no longer just the date')

def test_setup(root):
    rs, wr = [], []
    for i, d in enumerate((20, 27, 34)):
        body = (f'Findings {i}: the fake market grew in the last year, mainly in cities, and prices fell a little while repair '
                f'networks expanded; three sources agree and one disagrees about the size of the change. [fake {i}]')
        rs += [(d, 10, 0, 'u', f'Research fake market {i}'), (d, 10, 5, 'b', body)]
        wr += [(d, 15, 0, 'u', 'Turn this into a post:\n' + body), (d, 15, 2, 'b', 'Draft ready. [fake]')]
    ga = [x for d in range(30, 56, 2) for x in ((d, 10, 0, 'u', f'[Group chat: "{"Alpha" if d % 4 else "Beta"}"] Checklist step {d}?'), (d, 10, 1, 'b', 'Done. [fake]'))]
    gb = [x for d in range(30, 56, 2) for x in ((d, 10, 0, 'u', f'[Group chat: "{"Alpha" if d % 4 else "Beta"}"] Checklist step {d}?'), (d, 10, 2, 'b', 'Copy ready. [fake]'))]
    mail = [(0, 9, 0, 'mem', [('2030-03-01', 'Never send emails without asking me first.')])]
    mail += [x for d in (40, 45, 50) for x in ((d, 9, 0, 'u', 'Check my inbox'), (d, 9, 1, 'tool', ('computer', {'action': 'navigate', 'url': 'https://mail.google.com/mail/u/0/'})),
                                              (d, 9, 2, 'b', 'Found it. [fake]'))]
    plug = [x for d in (40, 45, 50) for x in ((d, 9, 0, 'u', 'Check my inbox'), (d, 9, 1, 'tool', ('computer', {'url': 'https://mail.google.com/'})),
                                              (d, 9, 2, 'tool', ('CallDynamicTool', {'namespace': 'user-Gmail', 'toolName': 'search_threads'})), (d, 9, 3, 'b', 'Ok. [fake]'))]
    watch = [(54, 9, 0, 'u', 'Watch the price every 10 minutes'), (54, 9, 1, 'b', 'Routine set. [fake]')]
    t0 = dt.timedelta(days=55)
    for k in range(200):
        t = t0 + dt.timedelta(minutes=10 * k); d, h, m = t.days, 9 + t.seconds // 3600, (t.seconds % 3600) // 60
        watch += [(d, h, m, 'routine', 'price'), (d, h, m, 'b', 'No change. [fake]')]
    W, B, diag, draft, _ = fleet(root, 'setup', {'Researcher': rs, 'Writer': wr, 'Alpha One': ga, 'Alpha Two': gb, 'Mailer': mail,
                                                 'Plugged': plug, 'Watcher': watch, 'Anchor': anchor()}, NOW)
    pa = diag['fleet']['pasted_answers']
    check(len(pa) == 1 and (pa[0]['src'], pa[0]['to']) == ('Researcher', 'Writer') and len(pa[0]['days']) == 3 and not pa[0]['shared_groups'],
          'G. answers pasted from one bot into another are listed with their days and refs')
    check([sorted(r['groups']) for r in diag['fleet']['same_member_groups']] == [['Alpha', 'Beta']], 'G. two group chats with the same members are listed')
    check([(c['service'], c['plugin_used']) for c in B['Mailer']['browser_sites']] == [('Gmail', False)] and B['Plugged']['browser_sites'][0]['plugin_used'],
          'G. browser use on a plugin site is listed, with whether the plugin is used')
    check(B['Watcher']['routines']['median_gap_min'] == 10 and B['Watcher']['routines']['no_reply_or_same'] > 0.9, 'G. routine spacing and repeated replies are facts')
    import helpers
    rf = lambda bot: helpers.any_ref(W, bot)
    sc = dict(impact=1, confidence='medium', effort=1, reversibility=1.0, basis='test')
    items = [dict(kind='group', title='Pass work in a group (test)', now=[dict(date='', ref=pa[0]['examples'][0]['ref'], text='Pasted on 3 days (test)')],
                  group=dict(project='Fake project', lead='Researcher', order=['Researcher', 'Writer'], blocked='ask_user',
                             members=[dict(bot='Researcher', part='Fake part'), dict(bot='Writer', part='Fake part')]),
                  fix='Test text (fake).', copy='Test copy (fake).', copy_kind='group', short='Test (fake)', score=dict(sc, effort=2)),
             dict(kind='redundant_groups', title='Two groups (test)', now=[dict(date='', ref=rf('Alpha One'), text='Alpha / Beta (test)')], fix='Test text (fake).', short='Test (fake)', score=sc),
             dict(kind='connector', bot='Mailer', title='Gmail in the browser (test)', now=[dict(date='', ref=rf('Mailer'), text='Browser on Gmail (test)')], fix='Test text (fake).', short='Test (fake)', score=sc),
             dict(kind='safety_rules', bot='Mailer', title='Safety rule only in memory (test)', fix='Test text (fake).', copy='Test copy (fake).', copy_kind='other', short='Test (fake)', score=sc,
                  now=[dict(date='03/01', source='memory', quote={'orig': 'Never send emails without asking me first.'}), dict(date='', ref=rf('Mailer'), text='Asked to check mail (test)')]),
             dict(kind='routine_cost', bot='Watcher', title='Routine every 10 minutes (test)', now=[dict(date='', ref=B['Watcher']['routines']['refs'][0], text='Every 10 minutes (test)')],
                  fix='Test text (fake).', copy='Test copy (fake).', copy_kind='routine', short='Test (fake)', score=sc)]
    helpers.fill(W, fleet=items)
    r = run(f'{S}/build_findings.py', 'finalize', '--work', W, '--strict', ok=False)
    check(r.returncode == 0, 'G. a draft with setup items finalizes (memory quote of the safety rule checks out)' + ('' if r.returncode == 0 else ': ' + r.stdout[-300:]))
    r = run(f'{S}/make_report.py', W + '/findings.json', '--outdir', W + '/report', '--no-pdf')
    h = open(glob.glob(W + '/report/*.html')[0], encoding='utf-8').read()
    check('id="bot-setup"' in h and 'Your setup' in h and h.index('id="bot-fleet"' if 'id="bot-fleet"' in h else 'fleet-1') < h.index('id="bot-setup"'),
          'G. the report shows setup items in their own section after the fleet')
    return W

def test_weekly(W):
    sm = json.load(open(W + '/report/summary.json'))
    check(set(sm) == {'date', 'bots', 'fleet'} and all('status' in v for v in sm['bots'].values()), 'H. make_report writes summary.json (statuses and item kinds, no wording)')
    r = run(f'{S}/make_report.py', W + '/findings.json', '--outdir', W + '/report2', '--no-pdf', '--previous', W + '/report/summary.json')
    check('UNCHANGED' in r.stdout, 'H. --previous prints UNCHANGED when nothing changed')
    fz = json.load(open(W + '/findings.json')); fz['bots'][0]['status'] = 'yellow'
    json.dump(fz, open(W + '/f2.json', 'w'))
    r = run(f'{S}/make_report.py', W + '/f2.json', '--outdir', W + '/report3', '--no-pdf', '--previous', W + '/report/summary.json')
    check('CHANGED: ' + fz['bots'][0]['name'] in r.stdout, 'H. --previous names what changed')
    setup = open(os.path.join(SK, 'references', 'setup.md'), encoding='utf-8').read()
    check(all(x in setup for x in ('Report only', 'UNCHANGED', 'Safe to re-run', 'about 10 minutes')), 'H. setup.md: weekly routine is report-only, quiet when unchanged, safe to re-run')
    skill = open(os.path.join(SK, 'SKILL.md'), encoding='utf-8').read()
    wr = open(os.path.join(SK, 'references', 'writing.md'), encoding='utf-8').read()
    check("that bot's settings" not in skill and 'asking it to remember' in skill and 'personal bots may have none' in wr,
          'H. text for another bot is a message to remember, not a description or settings field')
    check(len(skill.splitlines()) <= 172, f'H. SKILL.md stays within 172 lines ({len(skill.splitlines())})')
    check('setup.md' in skill and all(k in setup for k in ('New chat', 'Connect apps', 'Auto-review rules', 'Details tab')),
          'H. setup steps use the documented app paths and SKILL.md points to them')
    check(not re.search(r'"(Remove|Delete|Merge) ', setup), 'H. no setup option is labelled Remove, Delete or Merge')

def main():
    keep = '--keep' in sys.argv; root = tempfile.mkdtemp(prefix='it6-')
    try:
        test_no_fixture_text(); test_cleanup(root); test_rate_floor(root); test_judge_all(root); test_unique_w(root)
        W = test_setup(root); test_weekly(W)
    finally:
        if keep: print('kept', root)
        else: shutil.rmtree(root, ignore_errors=True)
    print(f'{len(failures)} FAILED' if failures else 'ALL PASSED')
    sys.exit(1 if failures else 0)

if __name__ == '__main__':
    main()
