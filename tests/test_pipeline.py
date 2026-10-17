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
        run(f'{S}/judge_inputs.py', '--work', W, '--all')   # no cue filter: every reply after a bot message
        check(JA_QUOTE in {x['user'] for x in json.load(open(f'{W}/judge_inputs.json'))}, '--all exports replies in any language')
        shutil.copy(f'{FX}/cues_ja.json', f'{W}/cues.json')   # cue phrases supplied by the host bot
        run(f'{S}/judge_inputs.py', '--work', W)
        ji = json.load(open(f'{W}/judge_inputs.json'))
        gold = json.load(open(f'{FX}/labels_by_text.json'))
        found = {x['user'] for x in ji}
        check(all(t in found for t in gold), f'candidate filter catches every planted correction ({len(gold)}/{len(gold)}; {len(ji)} candidates)')
        labels = {x['key']: gold.get(x['user'], dict(label=False, type='new_request', topic=None, confidence='medium', evidence='test'))
                  for x in ji}
        json.dump(labels, open(f'{W}/labels.json', 'w'), ensure_ascii=False)
        run(f'{S}/diagnostics.py', '--work', W, '--now', '2030-03-11 09:00')
        d = json.load(open(f'{W}/diag.json'))
        st = {b: d['bots'][b]['status_suggested'] for b in d['bots']}
        check(st[OLD] == 'red', 'idle bot -> Clean up')
        g = d['bots'][RECIPE]['groups']['format_length']; fxt = {f['id']: f for f in d['bots'][RECIPE]['fix_candidates']}
        check(st[RECIPE] == 'yellow' and any('From now on' in fxt[c['id']]['text'] and c['incidents_after'] >= 1 for c in g['fix_candidates']),
              'recipe bot: repeated format fix -> Needs work; the "from now on" in between is a fix candidate')
        check(st[TRIP] == 'yellow' and d['bots'][TRIP]['groups']['misread_intent']['incidents'] == 3, 'trip bot: misreads on 3 days -> Needs work')
        check(st[MEMO] == 'green', 'one-off correction does not change status')
        check(d['fleet']['outages'] and set(d['fleet']['outages'][0]['bots']) == {TRIP, MEMO}, 'overlapping silences in two bots are a fleet outage')
        check(any(len(r['days']) >= 4 for r in d['bots'][RECIPE]['repeated_requests']), 'same request on 4 days -> routine candidate')
        check(d['bots'][RECIPE]['memory']['time_sensitive'], 'time-sensitive memory fact is flagged')
        check(d['bots'][TRIP]['skipped_questions']['count'] == 1, 'skipped question card counted')
        run(f'{S}/build_findings.py', 'skeleton', '--work', W)
        dr = json.load(open(f'{W}/findings_draft.json'))
        check(dr.get('lang') == 'en' and 'glance' in dr.get('ui', {}) and dr.get('date_label'), 'skeleton carries lang, fallback ui labels and date_label')
        rf = next(f for b in dr['bots'] if b['id'] == RECIPE for f in b['findings'] if f.get('topic') == 'format_length')
        check(rf.get('fix_check') and rf['score']['impact'] == 2, 'fix candidates are left for the bot to confirm; impact not raised')
        check(any(f.get('cleanup') for b in dr['bots'] if b['id'] == OLD for f in b['findings']), "a clean-up bot's finding is marked cleanup (one option)")
        dr['date_label'] = 'March 11, 2030'
        for b in dr['bots']:   # what the host bot would do: write plain-language text, then clear review flags
            b['issue'] = f"Test issue for {b['name']}"; b.pop('needs_review', None)
            for f in b['findings']:
                f.pop('needs_review', None); f.pop('fix_check', None)
                if f.get('topic'): f['copy'] = 'Test rule text (fake).'
                if 'TODO' in f.get('fix', ''): f['fix'] = 'Before booking, confirm lodging type, meal and time of day (fake).'
        for f in dr['fleet']:
            f.pop('needs_review', None)
            if isinstance(f.get('copy'), list):
                for x in f['copy']: x['text'] = f"Test description for {x['bot']} (fake)."
        dr['fleet'].append(dict(title='Test translated quote', info=True, fix='Nothing to do (test).',
                                now=[dict(date='03/07', quote=dict(orig=JA_QUOTE, translation='Too long. Make it one line', lang='ja'))]))
        json.dump(dr, open(f'{W}/findings_draft.json', 'w'), ensure_ascii=False)
        r = run(f'{S}/build_findings.py', 'finalize', '--work', W, '--strict')
        fz = json.load(open(f'{W}/findings.json'))
        check(len(fz['top3']) == 3 and all(len([f for f in b['findings'] if f.get('score')]) <= 3 for b in fz['bots']), 'top 3 picked and at most 3 scored proposals per bot')
        # negative test: an invented quote must be rejected
        bad = json.load(open(f'{W}/findings_draft.json'))
        bad['bots'][0]['findings'][0]['now'].append({'date': '03/02', 'quote': {'orig': 'This sentence was never said by anyone'}})
        json.dump(bad, open(f'{W}/bad.json', 'w'))
        r = run(f'{S}/build_findings.py', 'finalize', '--work', W, '--draft', f'{W}/bad.json', ok=False)
        check(r.returncode != 0 and 'not found word for word' in r.stdout, 'invented quote is rejected')
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
