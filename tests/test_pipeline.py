#!/usr/bin/env python3
"""Offline end-to-end test on the synthetic fixture: pages -> timelines -> judge inputs -> labels ->
diagnostics -> findings -> HTML + PDF, in English and in a second language (custom ui labels + lang). Run: python3 tests/test_pipeline.py [--keep]"""
import glob, json, os, re, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); S = os.path.join(ROOT, 'skills', 'audit-my-bots', 'scripts')
FX = os.path.join(HERE, 'fixtures'); SELF = 'aaaaaaaa-0000-4000-8000-0000000000ff'
RECIPE, TRIP, OLD, MEMO = (f'aaaaaaaa-0000-4000-8000-00000000000{i}' for i in (1, 2, 3, 4))
failures = []
JA_QUOTE = '\u9577\u3059\u304e\u308b\u3002\u4e00\u884c\u306b\u3057\u3066'   # the Japanese fixture correction
JA_UI = {'glance': '\u6982\u8981', 'st': {'red': '\u6574\u7406\u5019\u88dc', 'yellow': '\u8981\u6539\u5584', 'green': '\u826f\u597d'}}

def run(*args, ok=True):
    r = subprocess.run([sys.executable, *args], capture_output=True, text=True)
    if ok and r.returncode != 0:
        print(r.stdout, r.stderr); raise SystemExit(f'FAILED: {" ".join(args)}')
    return r

def check(cond, msg):
    print(('PASS ' if cond else 'FAIL ') + msg)
    if not cond: failures.append(msg)

def main():
    if not os.path.isdir(FX):
        run(os.path.join(HERE, 'make_fixture.py'))
    W = tempfile.mkdtemp(prefix='bot-audit-test-')
    try:
        run(f'{S}/sessions.py', 'list-bots', '--work', W, '--self', SELF, '--agents-dir', os.path.join(FX, 'agents'))
        bots = json.load(open(f'{W}/bots.json'))
        check(len(bots) == 4 and SELF not in [b['id'] for b in bots], 'list-bots finds 4 bots and skips the auditing bot')
        check(all(set(b) == {'id', 'name', 'description'} for b in bots), 'only name and description are taken from profiles')
        for raw in sorted(glob.glob(f'{FX}/pages/*/raw_*.txt')):
            r = run(f'{S}/sessions.py', 'save-page', raw, '--work', W, '--bot', os.path.basename(os.path.dirname(raw)))
            check('start=' in r.stdout, f'save-page {os.path.basename(raw)} -> {r.stdout.split()[0]}')
        r = run(f'{S}/sessions.py', 'parse', '--work', W)
        check('WARNING' not in r.stdout, 'all fixture transcripts are complete')
        tl = json.load(open(f'{W}/timelines/{RECIPE}.json'))
        check(sum(e['role'] == 'user' for e in tl['events']) == 9 and tl['events'][0]['ts'] == '2030-03-01 09:00', 'timeline parses user messages and timestamps')
        run(f'{S}/judge_inputs.py', '--work', W)   # no word filter: every reply after a bot message
        ji = json.load(open(f'{W}/judge_inputs.json'))
        gold = json.load(open(f'{FX}/labels_by_text.json'))
        found = {x['user'] for x in ji}
        check(JA_QUOTE in found and all(t in found for t in gold), f'every reply is a judge item, in any language ({len(gold)} planted corrections, {len(ji)} items)')
        labels = {x['key']: gold.get(x['user'], dict(label=False, type='new_request', topic=None, confidence='medium', evidence='test'))
                  for x in ji}
        json.dump(labels, open(f'{W}/labels.json', 'w'), ensure_ascii=False)
        run(f'{S}/diagnostics.py', '--work', W, '--now', '2030-03-11 09:00')
        d = json.load(open(f'{W}/diag.json')); B = d['bots']
        check(not any('status_suggested' in b or 'faded' in b for b in B.values()), 'diagnostics gives facts, no suggested status')
        check(B[OLD]['idle_days'] >= 7 and B[OLD]['share'] < 0.1, f"idle bot: idle and share are facts ({B[OLD]['idle_days']} days, {B[OLD]['share']})")
        g = B[RECIPE]['correction_topics']['format_length']
        check(g['incidents'] == 3 and g['occasions'] == 3 and len(g['refs']) == 3, 'recipe bot: 3 labelled format corrections on 3 occasions, with refs')
        check(B[TRIP]['correction_topics']['misread_intent']['incidents'] == 3, 'trip bot: 3 labelled misreads counted')
        check(d['fleet']['overlapping_waits'] and set(d['fleet']['overlapping_waits'][0]['bots']) == {TRIP, MEMO}, 'overlapping silences in two bots are listed')
        check(B[RECIPE]['memory']['facts'] and all('learned' in f for f in B[RECIPE]['memory']['facts']), 'memory facts come with learned dates')
        check(B[TRIP]['skipped_questions']['count'] == 1, 'skipped question card counted')
        dg = run(f'{S}/judge_inputs.py', '--work', W, '--digest', '--kb', '100').stdout
        n_typed = sum(b['real_requests'] for b in B.values())
        check(sum(1 for ln in dg.splitlines() if re.match(r"^[\w-]+:\d+ ", ln)) == n_typed, f'digest lists every typed message with its id ({n_typed})')
        run(f'{S}/build_findings.py', 'skeleton', '--work', W)
        dr = json.load(open(f'{W}/findings_draft.json'))
        check(dr.get('lang') == 'en' and 'glance' in dr.get('ui', {}) and dr.get('date_label'), 'skeleton carries lang, fallback ui labels and date_label')
        check(all(b['status'] == 'TODO' and not b['findings'] for b in dr['bots']), 'skeleton leaves every status and finding to the host bot')
        r = run(f'{S}/build_findings.py', 'finalize', '--work', W, ok=False)
        check(r.returncode != 0 and 'status must be' in r.stdout, 'finalize refuses a row without a decided status')
        H = __import__('helpers')
        fr = [H.finding(f'Format fix {k} (test)', H.ref_of(W, RECIPE, q), q) for k, q in enumerate(gold, 1) if gold[q]['topic'] == 'format_length' and q != JA_QUOTE]
        fr[0]['now'].append(dict(date='03/07', ref=H.ref_of(W, MEMO, JA_QUOTE), quote=dict(orig=JA_QUOTE, translation='Too long. Make it one line', lang='ja')))
        names = {b['id']: b['name'] for b in dr['bots']}
        cu = dict(title='Stopped being used (test)', cleanup=True, short='Show me how to clean up (test)', fix='See the keep item (test).',
                  now=[dict(date='', ref=H.any_ref(W, OLD), text='Last request (test)')], score=dict(impact=1, confidence='medium', effort=1, reversibility=0.6, basis='test'))
        H.fill(W, status={names[OLD]: 'red', names[RECIPE]: 'yellow'},
               findings={names[RECIPE]: fr + [H.finding('Extra (test)', H.ref_of(W, RECIPE, 'Too long'))], names[OLD]: [cu],
                         names[TRIP]: [H.finding('Trip rule (test)', H.ref_of(W, TRIP, "I meant a hostel"), "I meant a hostel")]})
        r = run(f'{S}/build_findings.py', 'finalize', '--work', W, '--strict')
        fz = json.load(open(f'{W}/findings.json'))
        check(len(fz['top3']) == 3 and all(len([f for f in b['findings'] if f.get('score')]) <= 3 for b in fz['bots']), 'top 3 picked and at most 3 scored proposals per bot')
        check([b['status'] for b in fz['bots']][:2] == ['yellow', 'red'], 'rows in status order: needs work, clean-up, fine')
        def bad(mut, want, msg):
            x = json.load(open(f'{W}/findings_draft.json')); mut(x); json.dump(x, open(f'{W}/bad.json', 'w'), ensure_ascii=False)
            r = run(f'{S}/build_findings.py', 'finalize', '--work', W, '--draft', f'{W}/bad.json', ok=False)
            check(r.returncode != 0 and want in r.stdout, msg)
        rb = lambda x: next(b for b in x['bots'] if b['id'] == RECIPE)
        bad(lambda x: rb(x)['findings'][0]['now'].append({'date': '03/02', 'quote': {'orig': 'This sentence was never said by anyone'}}),
            'not found word for word', 'invented quote is rejected')
        bad(lambda x: rb(x)['findings'][0]['now'][0].update(ref=rb(x)['findings'][0]['now'][0]['ref'].split(':')[0] + ':99999'),
            'is not a message id', 'a message id that does not exist is rejected')
        bad(lambda x: rb(x)['findings'][0]['now'][0].update(ref=rb(x)['findings'][1]['now'][0]['ref']),
            'not found word for word in message', 'a real quote cited with the wrong message id is rejected')
        bad(lambda x: [e.pop('ref') for e in rb(x)['findings'][0]['now']], 'cite at least one message', 'a finding without a message id is rejected')
        run(f'{S}/make_report.py', f'{W}/findings.json', '--outdir', f'{W}/report')
        # second language: the host bot sets lang and translated ui labels (a few here; the rest fall back to English)
        fx = json.load(open(f'{W}/findings.json')); fx['lang'] = 'ja'
        fx['ui'] = dict(glance=JA_UI['glance'], st=JA_UI['st']); fx['date_label'] = '2030/3/11'; fx['fonts'] = {'sans': "'Test Sans', sans-serif"}
        json.dump(fx, open(f'{W}/findings_ja.json', 'w'), ensure_ascii=False)
        run(f'{S}/make_report.py', f'{W}/findings_ja.json', '--outdir', f'{W}/report_ja')
        for f in ('report/fleet_report_2030-03-11.html', 'report/fleet_report_2030-03-11.pdf',
                  'report_ja/fleet_report_2030-03-11.html', 'report_ja/fleet_report_2030-03-11.pdf'):
            p = f'{W}/{f}'
            okf = os.path.exists(p) and os.path.getsize(p) > 5000
            if okf and p.endswith('.pdf'): okf = open(p, 'rb').read(5) == b'%PDF-'
            check(okf, f'{f} produced ({os.path.getsize(p) // 1024 if os.path.exists(p) else 0} KB)')
        h = open(f'{W}/report/fleet_report_2030-03-11.html', encoding='utf-8').read()
        check('<html lang="en"' in h and 'Recipe Helper' in h and 'Too long. Just give me the steps' in h and 'At a glance' in h,
              'English HTML has bots, verbatim quotes and default labels')
        check('Too long. Make it one line' in h and f'<span class="orig" lang="ja">{JA_QUOTE}</span>' in h,
              'a translated quote shows the translation with the original underneath')
        hk = open(f'{W}/report_ja/fleet_report_2030-03-11.html', encoding='utf-8').read()
        check('<html lang="ja"' in hk and JA_UI['glance'] in hk and JA_UI['st']['yellow'] in hk and '2030/3/11' in hk
              and 'Bot by bot' in hk, 'labels, date and lang come from findings.json; missing labels fall back to English')
        check('@font-face' not in h + hk and 'data:font' not in h + hk, 'no embedded fonts (system fonts only)')
        check(':lang(' not in h + hk and 'quotes:auto' in h and 'line-break:auto' in h, 'one script-agnostic style, no per-language CSS')
        check("--sans:'Test Sans', sans-serif" in hk and "Test Sans" not in h, 'host bot can override the font stacks')
        check('white-space:nowrap' in re.search(r'\.ev \.d\{[^}]*\}', h).group(0), 'evidence dates do not wrap')
        check(not re.search(r'token|subagent|executor|transcript', re.sub(r'<[^>]+>|<!--.*?-->', ' ', h, flags=re.S), re.I), 'no internal jargon in the English report')
        if '--keep' in sys.argv:
            print('kept work dir:', W)
    finally:
        if '--keep' not in sys.argv:
            shutil.rmtree(W, ignore_errors=True)
    print(f'\n{"ALL PASSED" if not failures else f"{len(failures)} FAILED"}')
    sys.exit(1 if failures else 0)

if __name__ == '__main__':
    main()
