#!/usr/bin/env python3
"""Regression tests for iteration 8 (synthetic replays: fake bots, fake text). Run: python3 tests/test_iteration8.py [--keep]

1. the time zone comes from any timestamped entry (a bot that only gets routine runs or messages from other bots), and a
   bot with no timestamps at all takes the fleet's zone (never UTC by default)
2. messages the judge labelled as corrections are not also a "same request on many days" item; the same follow-up
   after the bot's answers ("test it too") becomes a standing-rule draft (kind follow_up), not a routine
3. a stopped habit has its own reason and clean-up title (any share), and its repeated corrections become optional
   "if you come back to it" lessons in the clean-up item (dropped when left empty, rendered when written)
4. days of use are counted by working session: late-night work past midnight is one day
5. file paths with spaces in folder or file names are recognised (never quoted, stripped from similarity)
6. stall lead: 3+ short user messages in a row with no reply, over 10+ minutes; quick bursts and group chats are not stalls
7. hand-off format: skipped for a machine-made template or one fan-out burst, kept for long free-form hand-offs
8. report rows in status order (needs work, clean-up, fine); long bot names wrap in the table
9. chat-language lead (low priority): replies in another writing system than the chat's on 2+ days; not for one day,
   code-mixed chats or a user who mostly writes the reply's language
D. documentation and limits (SKILL.md within 172 lines, references describe the new leads, no Hangul in the repo)
"""
import glob, json, os, re, shutil, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
SK = os.path.join(ROOT, 'skills', 'audit-my-bots'); S = os.path.join(SK, 'scripts')
sys.path.insert(0, HERE); sys.path.insert(0, S)
import test_iteration6 as t6
from test_iteration7 import agent_msg, hidden_script
check, run, fleet, NOW = t6.check, t6.run, t6.fleet, t6.NOW
from common import PATH_RE, has_app_text, strip_app_text

def daily(name, days, h=12):
    return [x for d in days for x in ((d, h, 0, 'u', f'{name} fake question number {d} about item {d * 7}'), (d, h, 1, 'b', f'Answer {d}. [fake]'))]

def test_tz(root):
    only_agent = hidden_script([x for d in range(40, 56, 3) for x in ((d, 10, 0, 'agent', ('Sender', f'Fake status {d} for the page')),
                                                                       (d, 10, 1, 'b', 'Ok. [fake]'))])
    only_routine = [x for d in range(30, 56) for x in ((d, 7, 0, 'routine', 'brief'), (d, 7, 1, 'b', f'Brief {d}. [fake]'))]
    W, B, *_ = fleet(root, 'tz', {'Main': daily('Main', range(0, 58)), 'Agent Only': only_agent, 'Routine Only': only_routine}, NOW)
    off = {json.load(open(p))['name']: json.load(open(p))['utc_offset_hours'] for p in glob.glob(W + '/timelines/*.json')}
    check(off['Agent Only'] == -5 and off['Routine Only'] == -5, f'1. bots with no typed messages take the zone of their timestamped entries ({off})')
    # a bot with no timestamp at all: the fleet's zone
    sys.path.insert(0, S); import sessions
    d = os.path.join(root, 'nots', 'transcripts', 'x'); os.makedirs(d)
    open(os.path.join(d, 'page_00000.txt'), 'w').write(json.dumps(dict(start=0, end=1, total=1, entries=[
        dict(role='assistant', message=dict(content=[dict(type='text', text='Hello. [fake]')]))])))
    tl = sessions.parse_one(d)
    check(tl['tz'] is None, '1. a chat with no timestamps has no zone of its own (parse gives it the fleet zone)')

def test_dedupe_followup(root):
    cor = {f'Too long again, steps only please (round {i})': 'format_length' for i in range(4)}
    s = daily('Cook', range(0, 58))
    for i, d in enumerate((10, 20, 30, 40)):
        s += [(d, 18, 0, 'u', f'Recipe for fake dish {d}'), (d, 18, 1, 'b', 'A long recipe. [fake]'),
              (d, 18, 3, 'u', f'Too long again, steps only please (round {i})'), (d, 18, 4, 'b', 'Steps only. [fake]')]
    f = daily('Coder', range(0, 58), h=9)
    for d in (5, 15, 25, 35, 45):
        f += [(d, 14, 0, 'u', f'Change the fake parser number {d} to accept dates'), (d, 14, 1, 'b', 'Changed it. [fake]'),
              (d, 14, 5, 'u', 'Test it too, really run it'), (d, 14, 6, 'b', 'Ran the tests. [fake]')]
    W, B, diag, draft, _ = fleet(root, 'dedupe', {'Cook': s, 'Coder': f}, NOW, labels=cor)
    reps = [e for r in B['Cook']['repeated_requests'] for e in r['examples']]
    check(B['Cook']['groups']['format_length']['repeated'] and not any('Too long again' in e for e in reps),
          '2. corrections in a correction group are not also a repeated-request item')
    fu = [r for r in B['Coder']['repeated_requests'] if any('Test it too' in e for e in r['examples'])]
    check(fu and fu[0]['follow_up'], '2. the same follow-up after the bot\'s answers is marked follow_up')
    db = {b['name']: b for b in draft['bots']}
    kinds = [(x.get('kind'), x.get('copy_kind')) for x in db['Coder']['findings']]
    check(('follow_up', 'memory') in kinds and not any(k[1] == 'routine' and 'Test it too' in json.dumps(x)
                                                         for k, x in zip(kinds, db['Coder']['findings'])),
          f'2. a follow-up becomes a standing-rule draft, not a routine ({kinds})')

def test_stopped(root):
    habit = [x for d in range(0, 21, 2) for x in ((d, 19, 0, 'u', f'Log a fake ride of {d} km'), (d, 19, 1, 'b', 'Logged a very long story. [fake]'))]
    cor = {f'Too long, just log it (number {i})': 'format_length' for i in range(3)}
    for i, d in enumerate((4, 10, 16)):
        habit += [(d, 19, 3, 'u', f'Too long, just log it (number {i})'), (d, 19, 4, 'b', 'Shorter. [fake]')]
    W, B, diag, draft, _ = fleet(root, 'stopped', {'Main': t6.anchor() + [x for h in (8, 10, 15, 17, 20) for x in daily(f'Main{h}', range(0, 58), h=h)], 'Ride Log': habit}, NOW, labels=cor)
    b = B['Ride Log']
    check(b['share'] < 0.05 and b['faded'] and b['status_reasons'][0].startswith('stopped'),
          f"3. a stopped habit with a small share is 'stopped', not 'barely used' ({b['status_reasons'][0][:40]})")
    db = {x['name']: x for x in draft['bots']}['Ride Log']
    cu = db['findings'][0]
    check(cu.get('cleanup') and cu['title'] == 'Stopped being used' and len(db['findings']) == 1,
          '3. the clean-up item has its own title and is the bot\'s only finding')
    check(cu.get('lessons') and cu['lessons'][0]['topic'] == 'format_length' and cu['lessons'][0]['copy'] == '',
          '3. its repeated correction is an optional lesson with an empty copy')
    # finalize drops an empty lesson; a written one is rendered under ui.lessons
    d = json.loads(json.dumps(draft))
    run(f'{S}/build_findings.py', 'finalize', '--work', W)
    fin = {x['name']: x for x in json.load(open(W + '/findings.json'))['bots']}['Ride Log']
    check('lessons' not in fin['findings'][0], '3. finalize drops lessons left empty')
    for x in d['bots']:
        if x['name'] == 'Ride Log': x['findings'][0]['lessons'][0]['copy'] = 'Log rides in one line: date, distance.'
    json.dump(d, open(W + '/draft2.json', 'w'))
    run(f'{S}/build_findings.py', 'finalize', '--work', W, '--draft', W + '/draft2.json')
    run(f'{S}/make_report.py', W + '/findings.json', '--outdir', W + '/report', '--no-pdf')
    h = open(glob.glob(W + '/report/*.html')[0], encoding='utf-8').read()
    check('If you come back to it' in h and 'Log rides in one line: date, distance.' in h, '3. a written lesson is rendered with its copy box')

def test_session_days(root):
    night = [x for d in range(0, 50, 5) for x in ((d, 23, 30, 'u', f'Night fake task {d}, part one'), (d, 23, 31, 'b', 'Done. [fake]'),
                                                  (d, 25, 10, 'u', f'Night fake task {d}, part two'), (d, 25, 11, 'b', 'Done. [fake]'))]
    W, B, *_ = fleet(root, 'night', {'Main': t6.anchor(), 'Night Owl': night}, NOW)
    check(B['Night Owl']['active_days'] == 10, f"4. work past midnight is one day of use ({B['Night Owl']['active_days']} days, want 10)")
    check(B['Night Owl']['typical_gap_days'] == 5, f"4. the rhythm follows sessions ({B['Night Owl']['typical_gap_days']})")

def test_paths():
    cases = {'open /Users/fake/My Project/notes.md please': '/Users/fake/My Project/notes.md',
             'the folder /Users/fake/My Project/ has it': '/Users/fake/My Project/',
             '~/Library/Application Support/Code/User/settings.json is broken': '~/Library/Application Support/Code/User/settings.json',
             'see /Users/fake/2024 Taxes/x.pdf now': '/Users/fake/2024 Taxes/x.pdf',
             'file /Users/fake/Docs/\ud68c\uc758 \uba54\ubaa8.txt ok': '/Users/fake/Docs/\ud68c\uc758 \uba54\ubaa8.txt'}
    for t, want in cases.items():
        check(PATH_RE.findall(t) == [want], f'5. path with spaces found whole: {want!r} in {PATH_RE.findall(t)}')
    check(PATH_RE.findall('run /usr/bin and/or the tests') == ['/usr/bin'] and not has_app_text('apples/oranges and pears'),
          '5. the words after a path stay prose')
    check(strip_app_text('open /Users/fake/My Project/notes.md please')[0] == 'open please', '5. spaced paths are stripped whole')

def test_stall(root):
    s = daily('Memo', range(0, 58))
    s += [(30, 22, 0, 'u', 'Make the fake shopping list from last week'), (30, 22, 1, 'b', 'Working on it. [fake]'),
          (30, 22, 15, 'u', 'still there?'), (30, 22, 30, 'u', 'hello?'), (30, 22, 45, 'u', 'answer please'), (30, 23, 5, 'b', 'Here it is. [fake]')]
    quick = daily('Quick', range(0, 58), h=9)
    quick += [(31, 15, 0, 'u', 'one more thing'), (31, 15, 0, 'u', 'the file is the blue one'), (31, 15, 1, 'u', 'and keep it short'), (31, 15, 2, 'b', 'Ok. [fake]')]
    grp = daily('Grp', range(0, 58), h=16)
    grp += [(32, 18, m, 'u', f'[Group chat: "Fake Team"] short note {m}') for m in (0, 10, 20, 30)] + [(32, 18, 40, 'b', 'Noted. [fake]')]
    W, B, *_ = fleet(root, 'stall', {'Memo': s, 'Quick': quick, 'Grp': grp}, NOW)
    st = B['Memo']['stall_candidates']
    check(len(st) == 1 and st[0]['answered'] and len(st[0]['texts']) == 3, f'6. three short nudges with no reply are a stall lead ({st})')
    check(not B['Quick']['stall_candidates'] and not B['Grp']['stall_candidates'], '6. a quick burst or a group chat is not a stall')
    draft = json.load(open(W + '/findings_draft.json'))
    check(list(draft['leads']['stalls']) == [B['Memo']['id']] if 'id' in B['Memo'] else len(draft['leads']['stalls']) == 1, '6. stalls are listed in the draft leads')

def test_handoff_templates(root):
    tmpl = ('# Task\nCollect fake sources for section {i}.\n\n# Stage\nstage=collect item={i}\n\n# Instructions\n'
            + 'Read the assigned folder and list every source with title and date; keep notes short. ' * 8)
    free = ('Hi, here is where the fake newsletter stands: the opening was rewritten twice, the second story has no photo yet, '
            'the events list is complete except the market, and the footer address is old, please fix it. ' * 3)
    worker = hidden_script([(30, 14, i, 'agent', ('Orchestrator', tmpl.format(i=i))) for i in range(10)] + [(30, 14, i, 'b', f'DONE {i}. [fake]') for i in range(10)])
    burst = hidden_script([(33, 9, i * 2, 'agent', ('Fanout', free + f' part {i * 37}')) for i in range(6)] + [(33, 9, i * 2 + 1, 'b', 'Ok. [fake]') for i in range(6)])
    editor = hidden_script([(d, 17, 0, 'agent', ('Scout', free + f' [fake {d}]')) for d in (40, 44, 48, 52)] + [(d, 17, 1, 'b', 'Editing. [fake]') for d in (40, 44, 48, 52)])
    W, B, diag, draft, _ = fleet(root, 'tmpl', {'Main': t6.anchor(), 'Worker': worker + daily('W', range(20, 58, 3)),
                                                'Sink': burst + daily('S', range(20, 58, 3)), 'Editor': editor + daily('E', range(20, 58, 3))}, NOW)
    pairs = [(h['src_name'], h['to_name']) for h in diag['fleet']['handoff_format_candidates']]
    skipped = {h['src_name']: h['reason'] for h in diag['fleet']['handoff_format_skipped']}
    check(('Scout', 'Editor') in pairs, '7. long free-form hand-offs still suggest a short format')
    check(('Orchestrator', 'Worker') not in pairs and skipped.get('Orchestrator') == 'template', f'7. a machine-made template is skipped ({skipped})')
    check(('Fanout', 'Sink') not in pairs and skipped.get('Fanout') == 'burst', '7. one fan-out burst is skipped')

def test_sort_and_css(root):
    W, B, diag, draft, _ = fleet(root, 'sort', {'Main': t6.anchor(), 'Old One': daily('Old', (0, 1)),
                                                'Wordy': daily('Wordy', range(0, 58), h=8) + [x for i, d in enumerate((10, 20, 30, 40))
                                                for x in ((d, 8, 5, 'u', f'Way too wordy again, cut it (take {i})'), (d, 8, 6, 'b', 'Cut. [fake]'))]},
                                 NOW, labels={f'Way too wordy again, cut it (take {i})': 'format_length' for i in range(4)})
    run(f'{S}/build_findings.py', 'finalize', '--work', W)
    order = [b['status'] for b in json.load(open(W + '/findings.json'))['bots']]
    check(order == ['yellow', 'red', 'green'], f'8. rows in status order: needs work, clean-up, fine ({order})')
    css = open(os.path.join(S, 'make_report.py'), encoding='utf-8').read()
    check('td.n a{text-decoration:none;white-space:nowrap}' not in css and 'td.n{width:30%;font-weight:600;overflow-wrap:anywhere}' in css,
          '8. long bot names wrap in the table')

def test_language(root):
    ja_q = '\u4eca\u65e5\u306e\u30e1\u30e2\u3092\u6574\u7406\u3057\u3066\u4fdd\u5b58\u3057\u3066'   # fake Japanese request
    ja_a = '\u30e1\u30e2\u3092\u4e09\u4ef6\u4fdd\u5b58\u3057\u307e\u3057\u305f\u3002'
    def ja(days_en):
        return [x for d in range(0, 58) for x in ((d, 21, 0, 'u', f'{ja_q} ({d})'),
                (d, 21, 1, 'b', f'Here are your notes for day {d}: three items were saved to the list. [fake]' if d in days_en else ja_a + f'[fake {d}]'))]
    ko_q = '`fetch_user()` \uc5d0 retry logic add \ud574\uc918, `pytest -k test_retry` \ub85c check'   # fake code-mixed Korean
    ko = [x for d in range(0, 58) for x in ((d, 11, 0, 'u', ko_q + f' {d}'), (d, 11, 1, 'b', f'`fetch_user` \uc5d0 retry \ub97c \ucd94\uac00\ud588\uc5b4\uc694 \ud14c\uc2a4\ud2b8\ub3c4 \ud1b5\uacfc\ud588\uc5b4\uc694 {d}'))]
    mixed = [x for d in range(0, 58) for x in ((d, 13, 0, 'u', f'Write a caption for fake photo {d} of the shop'), (d, 13, 1, 'b', f'Caption {d}: fresh and warm, made by hand today. [fake]'))]
    mixed += [x for d in (5, 15, 25) for x in ((d, 13, 3, 'u', '\ub108\ubb34 \ub531\ub531\ud574, \ud3b8\ud558\uac8c \uc368\uc918'), (d, 13, 4, 'b', 'Okay, here is a more casual caption for you. [fake]'))]
    W, B, *_ = fleet(root, 'lang', {'Memo': ja((8, 16, 24)), 'Once': ja((30,)), 'Coder': ko, 'Caption': mixed}, NOW)
    lm = B['Memo']['language_mismatch']
    check(lm and lm['chat_script'] == 'Japanese' and lm['reply_scripts'] == ['Latin'] and len(lm['days']) == 3, f'9. replies in another script on 3 days are a lead ({lm})')
    check(not B['Once']['language_mismatch'], '9. one day is not a lead')
    check(not B['Coder']['language_mismatch'], '9. a code-mixed Korean chat answered in Korean is not a lead')
    check(not B['Caption']['language_mismatch'], '9. a user who mostly writes English, answered in English, is not a lead')

def test_docs():
    sk = open(os.path.join(SK, 'SKILL.md'), encoding='utf-8').read()
    check(len(sk.splitlines()) <= 172, f'D. SKILL.md within 172 lines ({len(sk.splitlines())})')
    check('stalls' in sk and 'chat language' in sk, 'D. SKILL.md names the new leads')
    ref = ''.join(open(p, encoding='utf-8').read() for p in glob.glob(os.path.join(SK, 'references', '*.md')))
    for w in ('Stalls', 'Chat language', 'follow_up', 'lessons', 'working session'):
        check(w in ref, f'D. references describe {w!r}')
    bad = [p for p in glob.glob(ROOT + '/**/*', recursive=True) if os.path.isfile(p) and not p.endswith(('.png', '.pyc'))
           and re.search('[\uac00-\ud7a3\u1100-\u11ff\u3130-\u318f]', open(p, encoding='utf-8', errors='ignore').read())]
    check(not bad, f'D. no Hangul in repo files ({bad[:3]})')

def main():
    keep = '--keep' in sys.argv; root = tempfile.mkdtemp(prefix='it8-')
    try:
        test_tz(root); test_dedupe_followup(root); test_stopped(root); test_session_days(root); test_paths()
        test_stall(root); test_handoff_templates(root); test_sort_and_css(root); test_language(root); test_docs()
    finally:
        if not keep: shutil.rmtree(root, ignore_errors=True)
        else: print('kept', root)
    print(f"\n{len(t6.failures)} failure(s)")
    sys.exit(1 if t6.failures else 0)

if __name__ == '__main__':
    main()
