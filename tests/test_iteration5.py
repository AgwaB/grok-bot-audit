#!/usr/bin/env python3
"""Regression tests for iteration 5 of the skill eval (synthetic replays: fake bots, fake text).
Run: python3 tests/test_iteration5.py [--keep]

A. grader: the chat-language check measures the prose only. Bot names, markdown table rules and pipes, code spans,
   file paths, attachment lines and test-harness headings ("# Step 8: ...") are not counted, so a Japanese chat about
   bots with English names passes; an English chat about bots with Japanese names still fails
B. an outage item built from diag's overlapping waits quotes each user message with "chat" and its ref; the report
   labels them with ui.in_chat
C. a bot with no proposals shows no "0" in the status table; the grader reads that as 0
D. documentation: commands.log from the first command and the literal env.sh path (step 0); routine text language and
   real time zone; fixes phrased from the user's side; fleet_note and n_items documented; SKILL.md stays short; no
   Hangul anywhere in the repo
"""
import json, os, re, shutil, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
SK = os.path.join(ROOT, 'skills', 'audit-my-bots'); S = os.path.join(SK, 'scripts')
sys.path.insert(0, S); sys.path.insert(0, HERE)
import make_report as mr
import grade
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
    rows = [f"{x['n']}\t{l['type']}\t{l['topic']}\t{l['confidence']}\t-\t-\t{x['user'][:6]}\n"
            for x in ji for l in [lab.get(x['user'])] if l and l.get('label')]
    open(f'{W}/labels.tsv', 'w', encoding='utf-8').write(''.join(rows))
    run(f'{S}/judge_inputs.py', '--work', W, '--label', f'{W}/labels.tsv')
    run(f'{S}/diagnostics.py', '--work', W)
    run(f'{S}/build_findings.py', 'skeleton', '--work', W, '--lang', 'en')
    return W, json.load(open(f'{W}/findings_draft.json', encoding='utf-8'))

NAMES = ['Recipe Helper', 'Trip Planner', '\u30e1\u30e2\u30dc\u30c3\u30c8', 'Old Notes']
# The shape of the iteration-5 ja-a chat.md (fake bots, short Japanese prose, English bot names and harness headings)
JA_CHAT = '\n'.join([
    '# Step 8: chat message (not sent)', '',
    '4\u3064\u306e\u30dc\u30c3\u30c8\u3092\u70b9\u691c\u3057\u307e\u3057\u305f\u3002', '',
    '| \u30dc\u30c3\u30c8 | \u72b6\u614b | \u8ab2\u984c |', '|---|---|---|',
    '| Recipe Helper | \u8981\u6539\u5584 | \u9577\u3059\u304e\u308b |',
    '| Trip Planner | \u8981\u6539\u5584 | \u53d6\u308a\u9055\u3048\u308b |',
    '| Old Notes | \u6574\u7406\u5019\u88dc | \u4f7f\u308f\u308c\u3066\u3044\u306a\u3044 |', '',
    '1. Recipe Helper: \u30eb\u30fc\u30eb\u3092\u4fdd\u5b58', '2. Trip Planner: \u4e88\u7d04\u524d\u306b\u78ba\u8a8d',
    '3. Trip Planner \u3068 Old Notes \u3092\u898b\u308b', '',
    'Attachments: report/fleet_report_2030-03-11.pdf, report/fleet_report_2030-03-11.html',
    'See `findings.json` in /workspace/bot-audit-run/2030-03-11/report/', '',
    '# Step 9: multi-select question (not sent)', '',
    '- Recipe Helper: \u30eb\u30fc\u30eb\u3092\u4fdd\u5b58', '- Trip Planner: \u4e88\u7d04\u524d\u306b\u78ba\u8a8d',
    '- Old Notes \u3092\u6574\u7406\u3059\u308b', '- \u4eca\u306f\u3069\u308c\u3082\u3057\u306a\u3044'])

def test_chat_language():
    raw = grade.script_share(JA_CHAT, 'ja'); clean = grade.script_share(grade.chat_prose(JA_CHAT, NAMES), 'ja')
    check(raw < 0.5, f'A. the raw Japanese chat scores under the bar because of names and headings ({raw:.2f})')
    check(clean >= 0.9, f'A. the prose-only share of that chat passes ({clean:.2f})')
    p = grade.chat_prose(JA_CHAT, NAMES)
    check(not re.search(r'Step 8|Attachments|fleet_report|findings\.json|/workspace|---|Recipe Helper|Old Notes', p),
          'A. headings, attachment lines, paths, code spans, table rules and bot names are dropped')
    en = '\n'.join(['Checked 2 bots. \u30e1\u30e2\u30dc\u30c3\u30c8 needs work because it keeps forgetting your notes.',
                    '- \u30e1\u30e2\u30dc\u30c3\u30c8: save a rule about the notes', '- \u30ec\u30b7\u30d4: add a description',
                    '- None for now'])
    s = grade.script_share(grade.chat_prose(en, ['\u30e1\u30e2\u30dc\u30c3\u30c8', '\u30ec\u30b7\u30d4']), 'ja')
    check(s is not None and s < 0.5, f'A. an English chat about bots with Japanese names still fails a ja check ({s:.2f})')

def test_outage_and_counts(root):
    W, dr = skeleton(root, 'replay-synth-ja')
    import helpers
    d = json.load(open(f'{W}/diag.json')); tls = helpers.timelines(W)
    sys.path.insert(0, S); from common import resolve_ref
    ws = d['fleet']['overlapping_waits'][0]['waits']
    ev = []
    for w in ws:
        tl, e = resolve_ref(w['refs'][0], tls)
        ev.append(dict(date=w['first'][5:10].replace('-', '/'), chat=tl['name'], ref=w['refs'][0], quote={'orig': e['text']}))
    check(len({x['chat'] for x in ev}) >= 2, 'B. overlapping waits name messages (refs) in two or more bots')
    dr = helpers.fill(W, fleet=[dict(title='Several bots went quiet at once (test)', info=True, now=ev, fix='Nothing to change (test).')])
    run(f'{S}/build_findings.py', 'finalize', '--work', W, '--strict')
    fz = json.load(open(f'{W}/findings.json', encoding='utf-8'))
    mr.set_ui({}); h = mr.page(fz)
    lab = mr.UI_DEFAULT['in_chat'].split('{')[0]
    check(lab and lab in mr.visible(h.split('<h2>Across all bots</h2>', 1)[1]), 'B. the report labels outage quotes with ui.in_chat')
    zero = [b for b in fz['bots'] if not mr.NPROP(b)]
    cells = dict(re.findall(r'<a href="#bot-([^"]+)">.*?<td class="c">(.*?)</td>', h))
    check(zero and all(not re.match(r'\s*0\b', cells[b['id']]) for b in zero), 'C. a bot with no proposals shows no "0" count')
    os.makedirs(f'{W}/report', exist_ok=True)
    run(f'{S}/make_report.py', f'{W}/findings.json', '--outdir', f'{W}/report', ok=False)
    g = json.loads(run(os.path.join(HERE, 'grade.py'), W, '--lang', 'en', ok=False).stdout)
    c = next(x for x in g['checks'] if x['text'].startswith('Proposals counts'))
    check(c['passed'], f'C. the grader reads a dash as 0 proposals ({c["evidence"]})')

def test_docs():
    skill = open(os.path.join(SK, 'SKILL.md'), encoding='utf-8').read()
    s0 = skill.split('## 0.')[1].split('## 1.')[0]
    check('commands.log' in s0 and 'from the first' in s0, 'D. step 0: commands.log from the first command')
    check('printed path' in s0 and 'literal path' in s0, 'D. step 0: source env.sh by its printed, literal path')
    s9 = skill.split('## 9.')[1]
    check("clean-up finding's `short`" in s9 and 'bot sections' in s9, 'D. step 9: the clean-up option is its short line, among the bot sections')
    check(len(skill.splitlines()) <= 172, f'D. SKILL.md stays short ({len(skill.splitlines())} lines)')
    wr = open(os.path.join(SK, 'references', 'writing.md'), encoding='utf-8').read()
    check('copy_kind` `routine`' in wr and "user's report language" in wr and 'real time zone' in wr,
          'D. writing.md: routine text in the report language, times in the real zone')
    check("user's side" in wr and 'quietly change' in wr, 'D. writing.md: fixes say what the user can do or what is applied on a pick')
    sc = open(os.path.join(SK, 'references', 'findings-schema.md'), encoding='utf-8').read()
    check('fleet_note' in sc and 'leave it empty' in sc, 'D. findings-schema.md: fleet_note default documented')
    check('n_items' in sc and 'no "0"' in sc, 'D. findings-schema.md: no zero count for n_items')
    hangul = []
    for d, _, fs in os.walk(ROOT):
        if '/.git' in d or '__pycache__' in d: continue
        for f in fs:
            try: t = open(os.path.join(d, f), encoding='utf-8').read()
            except (UnicodeDecodeError, OSError): continue
            if re.search('[\uac00-\ud7a3\u1100-\u11ff\u3130-\u318f]', t): hangul.append(os.path.relpath(os.path.join(d, f), ROOT))
    check(not hangul, f'D. no Hangul in the repo {hangul[:5]}')

if __name__ == '__main__':
    root = tempfile.mkdtemp(prefix='bot-audit-it5-')
    try:
        run(os.path.join(HERE, 'make_replay.py'), root)
        test_chat_language(); test_outage_and_counts(root); test_docs()
    finally:
        if '--keep' in sys.argv: print('kept:', root)
        else: shutil.rmtree(root, ignore_errors=True)
    print('\nALL PASSED' if not failures else f'\n{len(failures)} FAILED')
    sys.exit(1 if failures else 0)
