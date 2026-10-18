#!/usr/bin/env python3
"""Regression tests for iteration 7 (synthetic replays: fake bots, fake text). Run: python3 tests/test_iteration7.py [--keep]

A. rhythm facts: a stopped habit shows active days, a short typical gap and a long idle; a routine or hand-offs
   from other bots count as use
B. bot-to-bot messages are parsed (sender and text) and listed per pair with their length
C. a fix with a later incident is listed with incidents_after; a written rule-review routine is kept and rendered,
   an empty one is dropped
D. pasted answers are listed per pair (two chains -> two pairs); finalize refuses a group item without project,
   lead, parts and "blocked -> ask the user"
E. documentation: setup.md describes the three items with documented app paths; SKILL.md stays within 172 lines
"""
import json, os, re, shutil, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
SK = os.path.join(ROOT, 'skills', 'audit-my-bots'); S = os.path.join(SK, 'scripts')
sys.path.insert(0, HERE)
import test_iteration6 as t6
check, run, fleet, anchor, NOW = t6.check, t6.run, t6.fleet, t6.anchor, t6.NOW

def agent_msg(sender, body):
    return ("[agent] A message just arrived from another of your user's agents: " + sender +
            " (id: 00000000-0000-4000-8000-0000000000aa).\nThis is another assistant reaching out, not the user typing here.\n\n"
            + sender + ': ' + body + '\n\nIf it needs an action, do it.')

def test_faded(root):
    habit = [x for d in range(0, 11) for x in ((d, 19, 0, 'u', f'Log a fake run of {d} km'), (d, 19, 1, 'b', 'Logged. [fake]'))]
    monthly = [(0, 20, 0, 'u', 'Summarise fake expenses'), (0, 20, 1, 'b', 'Done. [fake]'), (28, 20, 0, 'u', 'Summarise fake expenses again'),
               (28, 20, 1, 'b', 'Done. [fake]')]
    routine = [(0, 8, 0, 'u', 'Brief me daily')] + [x for d in range(0, 11) for x in ((d, 9, 0, 'u', f'Fake question {d}'), (d, 9, 1, 'b', 'Ok. [fake]'))] + \
              [x for d in range(11, 58) for x in ((d, 7, 0, 'routine', 'brief'), (d, 7, 1, 'b', f'Brief {d}. [fake]'))]
    small = [x for d in range(0, 20) for x in ((d, 12, 0, 'u', f'Everyday fake question {d}'), (d, 12, 1, 'b', 'Ok. [fake]'))] + \
            [x for d in range(20, 58, 2) for x in ((d, 12, 0, 'u', f'Everyday fake question {d}'), (d, 12, 1, 'b', 'Ok. [fake]'))]
    W, B, *_ = fleet(root, 'faded', {'Habit': habit, 'Monthly': monthly, 'Routine Habit': routine, 'Main': small}, NOW)
    h = B['Habit']
    check(h['share'] >= 0.05 and h['active_days'] == 11 and h['typical_gap_days'] == 1 and h['idle_days'] > 40,
          'A. a stopped daily habit: 11 active days, a 1-day rhythm and 46 idle days are facts (share not a factor)')
    check(B['Monthly']['typical_gap_days'] == 28, 'A. a monthly rhythm shows as a 28-day typical gap')
    check(B['Routine Habit']['idle_days'] < 1 and B['Routine Habit']['idle_typed_days'] > 40, 'A. a stopped typing habit whose routine still runs is not idle')
    check(B['Main']['idle_days'] < 2, 'A. a bot in steady use is not idle')

def hidden_script(script):
    """Turn ('agent', sender, body) items into hidden prompts via the routine slot of t6.convo."""
    out = []
    for x in script:
        if x[3] == 'agent':
            out.append((x[0], x[1], x[2], 'routine', '\x00' + agent_msg(*x[4])))
        else:
            out.append(x)
    return out

def test_handoff_rule_review_groups(root):
    long_body = ('Status for the launch page: the hero copy is drafted, the pricing table still needs the annual plan, the FAQ '
                 'has six questions and two are waiting on legal, images are in the shared folder, the footer links are checked, '
                 'and the next step is a full read-through before Thursday; please confirm the tone matches the brand notes and '
                 'flag anything that conflicts with the last review, then send it back with comments inline. ') * 2
    a = [(d, 10, 0, 'agent', ('Drafter', long_body + f' [fake {d}]')) for d in (40, 43, 46, 49)]
    a += [(d, 10, 1, 'b', 'Reviewed. [fake]') for d in (40, 43, 46, 49)]
    short = [(d, 11, 0, 'agent', ('Pinger', f'Fake ping {d * 13}: file {d} done')) for d in (41, 44, 47)] + \
            [(d, 11, 1, 'b', 'Ok. [fake]') for d in (41, 44, 47)]
    drafter = [x for d in range(38, 50) for x in ((d, 9, 0, 'u', f'Draft section {d}'), (d, 9, 1, 'b', 'Drafted. [fake]'))]
    # repeated mistake after a promise: fix candidate with an incident after it
    tutor = [x for d in range(20, 50, 2) for x in ((d, 18, 0, 'u', f'Quiz me on fake topic {d}'), (d, 18, 1, 'b', f'Quiz {d}. [fake]'))]
    tutor += [(22, 18, 2, 'u', 'Too many questions again, five max'), (22, 18, 3, 'b', 'From now on I will ask five questions at most. [fake]'),
              (30, 18, 2, 'u', 'Too many questions again, five max please'), (30, 18, 3, 'b', 'Sorry. [fake]'),
              (38, 18, 2, 'u', 'Too many questions again, I said five'), (38, 18, 3, 'b', 'Sorry. [fake]')]
    labels = {t: 'format_length' for t in ('Too many questions again, five max', 'Too many questions again, five max please', 'Too many questions again, I said five')}
    # two separate projects relayed by hand
    def chain(src, dst, topic, days):
        s1, s2 = [], []
        for i, d in enumerate(days):
            body = (f'{topic} notes {i}: the fake findings cover the main options, the costs, the risks and a short list of '
                    f'open questions for the next step, with sources checked and one disagreement noted. [fake {topic} {i}]')
            s1 += [(d, 10, 0, 'u', f'Look into {topic} part {i}'), (d, 10, 5, 'b', body)]
            s2 += [(d, 15, 0, 'u', 'Use this:\n' + body), (d, 15, 2, 'b', 'Done. [fake]')]
        return s1, s2
    r1, w1 = chain('Scout', 'Scribe', 'garden shed', (20, 27, 34))
    r2, w2 = chain('Finder', 'Planner', 'kitchen tiles', (21, 28, 35))
    bots = {'Reviewer': hidden_script(a + short), 'Drafter': drafter, 'Tutor': tutor, 'Scout': r1, 'Scribe': w1, 'Finder': r2, 'Planner': w2,
            'Main': anchor()}
    W, B, diag, draft, _ = fleet(root, 'setup7', bots, NOW, labels=labels)
    tl = json.load(open(os.path.join(W, 'timelines', next(b for b, v in diag['bots'].items() if v['name'] == 'Reviewer') + '.json')))
    ag = [e for e in tl['events'] if e.get('kind') == 'agent']
    check(len(ag) == 7 and ag[0]['sender'] == 'Drafter' and ag[0]['text'].startswith('Status for the launch page'),
          'B. bot-to-bot messages keep the sender and the message text')
    check(B['Reviewer']['handoffs_received'] == 7 and B['Reviewer']['idle_days'] < 30,
          'A/B. a bot that only works on other bots\' hand-offs counts as in use')
    bb = {(h['src'], h['to']): h for h in diag['fleet']['bot_to_bot']}
    check(bb[('Drafter', 'Reviewer')]['median_chars'] > 600 and bb[('Pinger', 'Reviewer')]['median_chars'] < 60 and bb[('Drafter', 'Reviewer')]['refs'],
          'B. bot-to-bot messages are listed per pair with length and refs')
    g = B['Tutor']['correction_topics']['format_length']
    check(g['incidents'] == 3 and g['occasions'] == 3, 'C. three corrections on three occasions are counted')
    pairs = sorted((p['src'], p['to']) for p in diag['fleet']['pasted_answers'])
    check(pairs == [('Finder', 'Planner'), ('Scout', 'Scribe')], 'D. two separate chains are two pasted-answer pairs')
    import helpers
    sc = dict(impact=2, confidence='medium', effort=2, reversibility=1.0, basis='test')
    groups = [dict(kind='group', title=f'Group {p[0]} (test)', now=[dict(date='', ref=x['examples'][0]['ref'], text='Pasted (test)')],
                   group=dict(project='TODO project name', lead=p[0], order=list(p), members=[dict(bot=n, part='TODO part') for n in p], blocked='ask_user'),
                   fix='Test text (fake).', copy='Test copy (fake).', copy_kind='group', short='Test (fake)', score=sc)
              for x in diag['fleet']['pasted_answers'] for p in [(x['src'], x['to'])]]
    hf = dict(kind='handoff_format', title='Long hand-offs (test)', format=['goal', 'where', 'done_when', 'waiting_on'],
              now=[dict(date='', ref=bb[('Drafter', 'Reviewer')]['refs'][0], text='Long (test)')], fix='Test text (fake).', copy='Test copy (fake).',
              copy_kind='memory', short='Test (fake)', score=dict(sc, effort=1))
    tref = g['refs'][0]
    tf = helpers.finding('Quiz length (test)', tref, 'Too many questions again, five max', review=dict(cadence_days=14, copy=''))
    other = helpers.finding('Other (test)', helpers.any_ref(W, 'Main'), review=dict(cadence_days=14, copy=''))
    draft = helpers.fill(W, findings={'Tutor': [tf], 'Main': [other]}, fleet=groups + [hf])
    r = run(f'{S}/build_findings.py', 'finalize', '--work', W, '--strict', ok=False)
    check(r.returncode != 0 and 'blocked = ask_user' in r.stdout, 'D. finalize --strict refuses a group without project and parts')
    next(b for b in draft['bots'] if b['name'] == 'Tutor')['findings'][0]['review']['copy'] = 'Every two weeks: check new corrections about quiz length; if none, end quietly. (fake)'
    for f in draft['fleet']:
        if f.get('kind') == 'group':
            f['group']['project'] = 'Fake project'
            for m in f['group']['members']: m['part'] = 'Fake part'
    json.dump(draft, open(W + '/findings_draft.json', 'w'))
    r = run(f'{S}/build_findings.py', 'finalize', '--work', W, '--strict', ok=False)
    check(r.returncode == 0, 'D. a filled group and a written review routine finalize' + ('' if r.returncode == 0 else ': ' + r.stdout[-300:]))
    fz = json.load(open(W + '/findings.json'))
    kept = [f for b in fz['bots'] for f in b['findings'] + b.get('more', []) if 'review' in f]
    check(len(kept) == 1 and kept[0]['review']['copy'].startswith('Every two weeks'), 'C. a written review routine is kept; empty ones are dropped')
    run(f'{S}/make_report.py', W + '/findings.json', '--outdir', W + '/report', '--no-pdf')
    h = open([os.path.join(W, 'report', x) for x in os.listdir(W + '/report') if x.endswith('.html')][0], encoding='utf-8').read()
    sec = h[h.index('id="bot-setup"'):]
    check(sec.count('id="fleet-') >= 3, 'D. hand-off and group items render in the setup section')
    check('Optional: a routine that reviews this rule' in h and 'Every two weeks: check new corrections' in h, 'C. the review routine renders next to the rule text')

def test_docs():
    setup = open(os.path.join(SK, 'references', 'setup.md'), encoding='utf-8').read()
    check(all(k in setup for k in ('handoff_format', 'review.copy', 'one group per project', 'stop and ask me', 'goal', 'done when', 'waiting on')),
          'E. setup.md covers the hand-off format, rule review and project groups')
    check('if there is none, end without a message' in setup and 'change nothing until the user says so' in setup,
          'E. the rule-review routine is quiet when nothing is new and changes nothing by itself')
    skill = open(os.path.join(SK, 'SKILL.md'), encoding='utf-8').read()
    check(len(skill.splitlines()) <= 172, f'E. SKILL.md stays within 172 lines ({len(skill.splitlines())})')

def main():
    keep = '--keep' in sys.argv; root = tempfile.mkdtemp(prefix='it7-')
    try:
        test_faded(root); test_handoff_rule_review_groups(root); test_docs()
    finally:
        if keep: print('kept', root)
        else: shutil.rmtree(root, ignore_errors=True)
    print(f'{len(t6.failures)} FAILED' if t6.failures else 'ALL PASSED')
    sys.exit(1 if t6.failures else 0)

if __name__ == '__main__':
    main()
