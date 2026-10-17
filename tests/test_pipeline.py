#!/usr/bin/env python3
"""Offline end-to-end test on the synthetic fixture: pages -> timelines -> judge inputs -> labels ->
diagnostics -> findings -> HTML + PDF (en and ko). Run: python3 tests/test_pipeline.py [--keep]"""
import glob, json, os, re, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); S = os.path.join(ROOT, 'skills', 'audit-my-bots', 'scripts')
FX = os.path.join(HERE, 'fixtures'); SELF = 'aaaaaaaa-0000-4000-8000-0000000000ff'
RECIPE, TRIP, OLD, MEMO = (f'aaaaaaaa-0000-4000-8000-00000000000{i}' for i in (1, 2, 3, 4))
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
        check(st[RECIPE] == 'yellow' and d['bots'][RECIPE]['groups']['format_length']['recurred_after_fix'], 'recipe bot: repeated format fix came back after "from now on" -> Needs work')
        check(st[TRIP] == 'yellow' and d['bots'][TRIP]['groups']['misread_intent']['incidents'] == 3, 'trip bot: misreads on 3 days -> Needs work')
        check(st[MEMO] == 'green', 'one-off correction does not change status')
        check(d['fleet']['outages'] and set(d['fleet']['outages'][0]['bots']) == {TRIP, MEMO}, 'overlapping silences in two bots are a fleet outage')
        check(any(len(r['days']) >= 4 for r in d['bots'][RECIPE]['repeated_requests']), 'same request on 4 days -> routine candidate')
        check(d['bots'][RECIPE]['memory']['time_sensitive'], 'time-sensitive memory fact is flagged')
        check(d['bots'][TRIP]['skipped_questions']['count'] == 1, 'skipped question card counted')
        run(f'{S}/build_findings.py', 'skeleton', '--work', W)
        dr = json.load(open(f'{W}/findings_draft.json'))
        for b in dr['bots']:   # what the host bot would do: write plain-language text, then clear review flags
            b['issue'] = {'en': f"Test issue for {b['name']}", 'ko': f"{b['name']} 테스트 문제"}; b.pop('needs_review', None)
            for f in b['findings']:
                f.pop('needs_review', None)
                if f.get('topic'): f['copy'] = {'en': 'Test rule text (fake).', 'ko': '테스트 규칙 문구(가짜).'}
        for f in dr['fleet']: f.pop('needs_review', None)
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
        run(f'{S}/make_report.py', f'{W}/findings.json', '--outdir', f'{W}/report', '--lang', 'all')
        for f in ('fleet_report_2030-03-11.html', 'fleet_report_2030-03-11.pdf', 'fleet_report_2030-03-11.ko.html', 'fleet_report_2030-03-11.ko.pdf'):
            p = f'{W}/report/{f}'
            okf = os.path.exists(p) and os.path.getsize(p) > 5000
            if okf and p.endswith('.pdf'): okf = open(p, 'rb').read(5) == b'%PDF-'
            check(okf, f'{f} produced ({os.path.getsize(p) // 1024 if os.path.exists(p) else 0} KB)')
        h = open(f'{W}/report/fleet_report_2030-03-11.html', encoding='utf-8').read()
        check('<html lang="en"' in h and 'Recipe Helper' in h and 'Too long. Just give me the steps' in h, 'English HTML has bots and verbatim quotes')
        hk = open(f'{W}/report/fleet_report_2030-03-11.ko.html', encoding='utf-8').read()
        check('<html lang="ko"' in hk and '정리 추천' in hk, 'Korean HTML uses Korean labels')
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
