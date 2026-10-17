#!/usr/bin/env python3
"""Regression tests for issues found in real runs, on a synthetic fixture built in a temp folder (fake bots, fake text).
Run: python3 tests/test_regressions.py [--keep]

 1. fetching: save-page takes several pages (several bots) in one call; replay copies pre-saved pages
 2. languages: without cues, a non-English correction is only found with --all
 3. judge context: long messages keep their start and end; --show prints the full messages
 4. app notices: attachment notices and file paths are stripped (no false similar requests or routines, never quoted)
 5. skipped questions: the lead carries the question texts
 6. copy per bot: "copy" as a list of {bot, text} is checked and rendered
 7. counts: the Proposals column excludes "see" pointers and shows them separately
 8. memory/description quotes: allowed with "source", labelled; paths never allowed
"""
import json, os, re, shutil, subprocess, sys, tempfile, datetime as dt
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
S = os.path.join(ROOT, 'skills', 'audit-my-bots', 'scripts')
sys.path.insert(0, HERE)
import make_fixture as mf

A, B, C = (f'bbbbbbbb-0000-4000-8000-00000000000{i}' for i in (1, 2, 3))
NAMES = {A: 'Photo Helper', B: 'Shop Helper', C: 'Daily Helper'}
# Korean text written as escapes (only fixtures carry non-Latin text). A correction with an ending no cue list has.
KO_FIX = '\ub108\ubb34 \uae38\uc5b4\uc694. \uc138 \uc904\ub85c \uc904\uc5ec\uc8fc\uc138\uc694'
KO_ASK = '\uc624\ub298 \ud560 \uc77c \uc815\ub9ac\ud574\uc918'
ADMIT = 'You are right, I missed the deadline you gave me.'
P1 = '/cursor/stores/store-0000/grok-bot/agents/' + A + '/attachments/01FAKEFAKEFAKE.png'
failures = []

def run(*args, ok=True):
    r = subprocess.run([sys.executable, *args], capture_output=True, text=True)
    if ok and r.returncode != 0:
        print(r.stdout, r.stderr); raise SystemExit(f'FAILED: {" ".join(args)}')
    return r

def check(cond, msg):
    print(('PASS ' if cond else 'FAIL ') + msg)
    if not cond: failures.append(msg)

def build(root):
    long_bot = 'Here is the plan. ' + 'Step details and background. ' * 80 + 'Want the short version?'
    long_reply = 'Okay. ' + 'Revised plan with every detail spelled out again. ' * 40 + ADMIT
    a = mf.convo([
        (0, 9, 0, 'u', 'Make this photo brighter\n' + mf.attach_notice(P1)),
        (0, 9, 1, 'b', 'Done, brighter version attached. [fake]'),
        (2, 9, 0, 'u', mf.attach_notice(P1.replace('FAKE.png', 'FAK2.png'))),
        (2, 9, 1, 'b', 'Got the image. [fake]'),
        (4, 9, 0, 'u', mf.attach_notice(P1.replace('FAKE.png', 'FAK3.png'))),
        (4, 9, 1, 'b', 'Got it. [fake]'),
        (5, 9, 0, 'u', 'Plan my week'),
        (5, 9, 1, 'b', long_bot),
        (5, 9, 5, 'u', 'You forgot the deadline I gave you'),
        (5, 9, 6, 'b', long_reply),
        (6, 9, 0, 'skip', 'Which filter next? \u2014 Warm / Cool / None'),
        (6, 9, 1, 'skip', 'Shall I also crop it? \u2014 Yes / No'),
        (6, 9, 2, 'skip', 'Save to which folder? \u2014 Photos / Desktop'),
    ])
    b = mf.convo([
        (0, 10, 0, 'mem', [('2030-02-20', 'The user currently shops on weekends.')]),
        (1, 10, 0, 'u', mf.attach_notice(P1.replace(A, B))),
        (1, 10, 1, 'b', 'Got the receipt. [fake]'),
        (3, 10, 0, 'u', mf.attach_notice(P1.replace(A, B).replace('FAKE', 'FAK9'))),
        (3, 10, 1, 'b', 'Got it. [fake]'),
    ])
    c = mf.convo([
        (1, 8, 0, 'u', KO_ASK),
        (1, 8, 1, 'b', 'A very long list of tasks for today. [fake]'),
        (1, 8, 2, 'u', KO_FIX),
        (1, 8, 3, 'b', 'Three lines: 1) a 2) b 3) c [fake]'),
    ])
    pages = os.path.join(root, 'pages')
    for aid, conv in ((A, a), (B, b), (C, c)):
        mf.write_pages(aid, NAMES[aid], conv, size=6, root=pages)
    return pages

def main():
    root = tempfile.mkdtemp(prefix='bot-audit-reg-'); W = os.path.join(root, 'work')
    try:
        pages = build(root)
        bots = [dict(id=A, name=NAMES[A], description='Edits photos. Fake test bot.'),
                dict(id=B, name=NAMES[B], description=''), dict(id=C, name=NAMES[C], description='')]
        os.makedirs(W); json.dump(bots, open(f'{W}/bots.json', 'w'))
        # 1. batched save: every page of every bot in one call
        files = [f'{bid}={os.path.join(pages, bid, f)}' for bid in (A, B, C) for f in sorted(os.listdir(os.path.join(pages, bid)))]
        r = run(f'{S}/sessions.py', 'save-page', '--work', W, *files)
        check(r.stdout.count('start=') == len(files) and len(os.listdir(f'{W}/transcripts')) == 3,
              f'1. save-page saves {len(files)} pages of 3 bots in one call')
        R = os.path.join(root, 'replay'); os.makedirs(R)
        shutil.copytree(f'{W}/transcripts', f'{R}/transcripts'); shutil.copy(f'{W}/bots.json', R)
        json.dump({'now': '2030-03-11 09:00'}, open(f'{R}/replay.json', 'w'))
        W2 = os.path.join(root, 'work2')
        r = subprocess.run([sys.executable, f'{S}/sessions.py', 'replay', '--work', W2], capture_output=True, text=True,
                           env={**os.environ, 'AUDIT_REPLAY_DIR': R})
        check(r.returncode == 0 and os.path.exists(f'{W2}/replay.json') and len(os.listdir(f'{W2}/transcripts')) == 3,
              '1. replay (AUDIT_REPLAY_DIR) copies bots.json, pages and the pinned date')
        run(f'{S}/sessions.py', 'parse', '--work', W2)
        W = W2
        tl = json.load(open(f'{W}/timelines/{A}.json'))
        users = [e for e in tl['events'] if e['role'] == 'user']
        # 4. notices and paths stripped
        check(users[0]['text'] == 'Make this photo brighter' and users[0].get('attachments') == 1 and users[1]['text'] == '',
              '4. attachment notice and path removed from user messages (count kept)')
        # 2. languages
        run(f'{S}/judge_inputs.py', '--work', W)
        ji = json.load(open(f'{W}/judge_inputs.json'))
        check(KO_FIX not in {x['user'] for x in ji}, '2. without --all the English fallback misses a Korean correction')
        run(f'{S}/judge_inputs.py', '--work', W, '--all')
        ji = json.load(open(f'{W}/judge_inputs.json'))
        check(KO_FIX in {x['user'] for x in ji}, '2. --all exports it')
        check(not any(x['user'] == '' or 'attached a file' in x['user'] for x in ji), '4. attachment-only messages are not judge candidates')
        # 3. judge context
        it = next(x for x in ji if x['user'].startswith('You forgot the deadline'))
        check(it['next_bot'].endswith(ADMIT) and it['prev_bot'].endswith('Want the short version?') and ' … ' in it['prev_bot']
              and len(it['prev_bot']) <= 805, '3. long messages keep start and end (admission at the end survives)')
        r = run(f'{S}/judge_inputs.py', '--work', W, '--show', it['key'])
        check(r.stdout.count('Step details and background.') == 80 and ADMIT in r.stdout, '3. --show prints the full messages')
        labels = {x['key']: dict(label=False, type='new_request', topic=None, confidence='medium', evidence='test') for x in ji}
        json.dump(labels, open(f'{W}/labels.json', 'w'))
        run(f'{S}/diagnostics.py', '--work', W)
        d = json.load(open(f'{W}/diag.json'))
        check(d['now'] == '2030-03-11 09:00', '1. diagnostics uses the replay date')
        check(not d['fleet']['similar_requests_candidates'], '4. no false "same request in several bots" from attachment notices')
        check(not d['bots'][A]['repeated_requests'], '4. no false routine candidate from attachment notices')
        # 5. skipped questions
        run(f'{S}/build_findings.py', 'skeleton', '--work', W, '--lang', 'en')
        dr = json.load(open(f'{W}/findings_draft.json'))
        sq = dr['leads']['skipped_questions'].get(A, {})
        check(sq.get('count') == 3 and any('crop' in q for q in sq.get('questions', [])), '5. skipped-question lead carries count and questions')
        fl = next(f for f in dr['fleet'] if f.get('copy_kind') == 'description')
        check(isinstance(fl['copy'], list) and {x['bot'] for x in fl['copy']} == {NAMES[B], NAMES[C]}, '6. skeleton drafts per-bot copy for a shared description item')
        # host bot edits
        for b in dr['bots']:
            b['issue'] = 'Test issue'; b.pop('needs_review', None)
            for f in b['findings']: f.pop('needs_review', None)
        for f in dr['fleet']: f.pop('needs_review', None)
        for x in fl['copy']: x['text'] = f'Test description for {x["bot"]} (fake).'
        ba = next(b for b in dr['bots'] if b['id'] == A)
        ba['findings'].append(dict(title='Asks which step to take next', fix='Go ahead with the recommended option (test).',
                                   copy='Go ahead with the recommended option and say what you did.', copy_kind='memory',
                                   now=[dict(date='03/06', who='Bot', quote={'orig': 'Shall I also crop it?'}),
                                        dict(date='', source='description', quote={'orig': 'Edits photos.'})],
                                   score=dict(impact=1, confidence='medium', effort=1, reversibility=1.0, basis='test')))
        bb = next(b for b in dr['bots'] if b['id'] == B)
        bb['findings'].append(dict(title='Stale fact in memory', fix='Update it (test).', copy='Shops on weekdays now.', copy_kind='memory',
                                   now=[dict(date='02/20', source='memory', quote={'orig': 'The user currently shops on weekends.'})],
                                   score=dict(impact=1, confidence='medium', effort=1, reversibility=1.0, basis='test')))
        json.dump(dr, open(f'{W}/findings_draft.json', 'w'))
        r = run(f'{S}/build_findings.py', 'finalize', '--work', W, '--strict', ok=False)
        check(r.returncode == 0, '5/8. a skipped question, a memory fact and a description can be quoted (with "source")' + ('' if r.returncode == 0 else ': ' + r.stdout[-300:]))
        # negative cases on copies of the draft
        def bad(mut, needle, msg):
            x = json.loads(json.dumps(dr)); mut(x); json.dump(x, open(f'{W}/bad.json', 'w'))
            rr = run(f'{S}/build_findings.py', 'finalize', '--work', W, '--draft', f'{W}/bad.json', ok=False)
            check(rr.returncode != 0 and needle in rr.stdout, msg)
        def b_of(x, bid): return next(b for b in x['bots'] if b['id'] == bid)
        bad(lambda x: b_of(x, B)['findings'][-1]['now'][0].pop('source'), 'set "source"', '8. a memory quote without "source" is rejected with a hint')
        bad(lambda x: b_of(x, A)['findings'][-1]['now'].append(dict(date='', quote={'orig': 'Make this photo brighter ' + P1})),
            'file path', '4/8. a quote with a file path is rejected')
        bad(lambda x: b_of(x, A)['findings'][-1]['now'].append(dict(date='', quote={'orig': 'The user attached a file.'})),
            'app notice', '4. a quote of the attachment notice is rejected')
        bad(lambda x: next(f for f in x['fleet'] if f.get('copy_kind') == 'description')['copy'].append({'text': 'no bot'}),
            '{"bot", "text"}', '6. a malformed per-bot copy list is rejected')
        # 7. pointers; 6/8 rendering
        fz = json.load(open(f'{W}/findings.json'))
        run(f'{S}/make_report.py', f'{W}/findings.json', '--outdir', f'{W}/report', '--no-pdf')
        h = open(f'{W}/report/fleet_report_{fz["date"]}.html', encoding='utf-8').read()
        rows = dict(re.findall(r'<tr><td class="n"><a href="#bot-([^"]+)">.*?<td class="c">(.*?)</td></tr>', h))
        nb = b_of(fz, B)
        real = sum(1 for f in nb['findings'] + nb.get('more', []) if not f.get('see') and not f.get('info'))
        check(any(f.get('see') for f in nb['findings']) and rows[B].startswith(f'{real} ') and 'class="sh"' in rows[B],
              f'7. Proposals counts real items only ({real}) and shows the shared-item pointer separately')
        check(all(f'<b class="cb">{NAMES[x]}</b>' in h for x in (B, C)) and h.count('class="cp"') >= 4, '6. per-bot copy boxes are rendered with bot names')
        check('<span class="who">Memory</span>' in h and '<span class="who">Description</span>' in h, '8. memory and description quotes are labelled')
        check('attached a file' not in h and '/cursor/stores' not in h, '4. no attachment notice or path in the report')
        if '--keep' in sys.argv: print('kept:', root)
    finally:
        if '--keep' not in sys.argv: shutil.rmtree(root, ignore_errors=True)
    print(f'\n{"ALL PASSED" if not failures else f"{len(failures)} FAILED"}')
    sys.exit(1 if failures else 0)

if __name__ == '__main__':
    main()
