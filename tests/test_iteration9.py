#!/usr/bin/env python3
"""Regression tests for iteration 9 (synthetic replays: fake bots, fake text). Run: python3 tests/test_iteration9.py [--keep]

1. keep intent: the user's last messages are judge items marked "last"; a keep label is a fact (user_keep, with its
   ref); finalize refuses red or a clean-up item for such a bot, and requires exactly one clean-up item on red bots only
2. exact repeats: the same text on 3+ days is a judge item marked "repeat"; resends within 30 minutes are listed apart;
   group-chat turns mirrored into several member bots are counted once and are not repeats or the same text in two bots
3. promises and stale memory without words: "later" in the promised column lists the promise with the user's next
   message in any language; memory facts come with the messages labelled after them
4. docs: the rubric, criteria and SKILL.md describe the new types; SKILL.md stays within 172 lines
"""
import json, os, shutil, subprocess, sys, tempfile, glob
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
SK = os.path.join(ROOT, 'skills', 'audit-my-bots'); S = os.path.join(SK, 'scripts')
sys.path.insert(0, S); sys.path.insert(0, HERE)
import make_fixture as mf
import test_iteration6 as t6
from test_iteration6 import check, run, convo, anchor, NOW

def fleet(root, name, bots, labels=None):
    """labels: {user text: (type, topic, promised)}; every item with that exact user text gets the line."""
    R = os.path.join(root, name); W = os.path.join(root, 'w-' + name); tmp = R + '/_p'; os.makedirs(R)
    listing = []
    for i, (bn, sc) in enumerate(bots.items(), 1):
        bid = f'eeeeeeee-0000-4000-8000-{i:012d}'
        mf.write_pages(bid, bn, convo(sc), size=200, root=tmp); listing.append(dict(id=bid, name=bn, description=''))
    json.dump(listing, open(R + '/bots.json', 'w')); json.dump({'now': NOW}, open(R + '/replay.json', 'w'))
    for raw in sorted(glob.glob(tmp + '/*/*.txt')):
        run(f'{S}/sessions.py', 'save-page', '--work', R, f'{os.path.basename(os.path.dirname(raw))}={raw}')
    shutil.rmtree(tmp)
    run(f'{S}/sessions.py', 'replay', '--work', W, '--from', R); run(f'{S}/sessions.py', 'parse', '--work', W)
    out = run(f'{S}/judge_inputs.py', '--work', W).stdout
    items = json.load(open(W + '/judge_inputs.json'))
    lines = [f"{it['n']}\t{ty}\t{tp or '-'}\thigh\t-\t{pr or '-'}\t{it['user'][:6]}\n"
             for it in items for t, (ty, tp, pr) in (labels or {}).items() if it['user'] == t]
    open(W + '/labels.tsv', 'w').write(''.join(lines))
    run(f'{S}/judge_inputs.py', '--work', W, '--label', W + '/labels.tsv')
    run(f'{S}/diagnostics.py', '--work', W); run(f'{S}/build_findings.py', 'skeleton', '--work', W, '--lang', 'en')
    diag = json.load(open(W + '/diag.json')); draft = json.load(open(W + '/findings_draft.json'))
    return W, {b['name']: b for b in diag['bots'].values()}, diag, draft, items

def busy():
    return anchor() + [x for d in range(58) for h in (8, 10, 15, 17) for x in ((d, h, 0, 'u', f'Fake task {d}-{h} on shelf {d * h}'), (d, h, 1, 'b', 'Done. [fake]'))]

def habit(last):
    sc = [x for d in range(0, 21, 2) for x in ((d, 19, 0, 'u', f'Add a fake pottery note number {d}'), (d, 19, 1, 'b', 'Noted. [fake]'))]
    return sc + [(20, 19, 5, 'u', last), (20, 19, 6, 'b', 'Understood. [fake]')]

def test_keep(root):
    en = 'Leave this one alone, I will need it again next year'
    it = 'Lascialo pure così, è in pausa di proposito fino al prossimo anno'
    W, B, diag, draft, items = fleet(root, 'keep', {'Main': busy(), 'Kiln Notes': habit(en), 'Loom Notes': habit(it), 'Clay Log': habit('Thanks for the help today')},
                                     labels={en: ('keep', None, None), it: ('keep', None, None)})
    tail = [x for x in items if x['user'] == en]
    check(tail and 'last' in tail[0].get('check', ''), '1. the last user messages are judge items marked last')
    for name in ('Kiln Notes', 'Loom Notes'):
        check(B[name]['user_keep'] and B[name]['user_keep']['ref'] and B[name]['idle_days'] > 30, f'1. {name}: the keep label is a fact with its ref')
    check(not B['Clay Log']['user_keep'], '1. without a keep label there is no user_keep')
    import helpers
    cu = lambda n: dict(title='Barely used (test)', cleanup=True, short='Clean up (test)', fix='Test (fake).', now=[dict(date='', ref=helpers.any_ref(W, n), text='Last (test)')],
                        score=dict(impact=1, confidence='medium', effort=1, reversibility=0.6, basis='t'))
    good = helpers.fill(W, status={'Clay Log': 'red'}, findings={'Clay Log': [cu('Clay Log')]})
    run(f'{S}/build_findings.py', 'finalize', '--work', W, '--strict')
    def bad(st, fd, want, msg):
        d = json.loads(json.dumps(good))
        for x in d['bots']:
            if x['name'] in st: x['status'] = st[x['name']]
            if x['name'] in fd: x['findings'] = fd[x['name']]
        json.dump(d, open(W + '/bad.json', 'w'))
        r = run(f'{S}/build_findings.py', 'finalize', '--work', W, '--draft', W + '/bad.json', ok=False)
        check(r.returncode != 0 and want in r.stdout, msg)
    bad({'Kiln Notes': 'red'}, {'Kiln Notes': [cu('Kiln Notes')]}, 'said to keep it', '1. finalize refuses a red status for a bot the user said to keep')
    bad({}, {'Loom Notes': [cu('Loom Notes')]}, 'said to keep it', '1. finalize refuses a clean-up item for a bot the user said to keep')
    bad({}, {'Clay Log': []}, 'exactly one finding with "cleanup"', '1. a red bot without a clean-up item is refused')
    bad({}, {'Main': [cu('Main')]}, 'only a clean-up (red) bot', '1. a clean-up item on a bot that is not red is refused')

def test_repeats(root):
    ack = 'Thanks, that works perfectly'
    tide = [x for d in (2, 9, 16, 23, 30) for x in ((d, 7, 0, 'u', f'Give me the morning tide table for the north harbour, week {d}'),
                                                    (d, 7, 1, 'b', 'Here is the table. [fake]'), (d, 7, 10, 'u', ack), (d, 7, 11, 'b', 'Glad it helps. [fake]'))]
    resend = [x for d in (3, 11) for x in ((d, 8, 0, 'u', 'Summarise the fake logbook entries of this week'),
                                           (d, 8, 2, 'u', 'Summarise the fake logbook entries of this week'), (d, 8, 5, 'b', 'Summary. [fake]'))]
    resend += [(19, 8, 0, 'u', 'Summarise the fake logbook entries of this week'), (19, 8, 5, 'b', 'Summary. [fake]')]
    grp = [x for d in (5, 12, 19, 26, 33) for x in ((d, 18, 0, 'u', f'[Group chat: "Harbour Crew"] Please check the crew roster and the boat list for day {d}'),
                                                   (d, 18, 2, 'b', 'Checked. [fake]'))]
    bots = {'Main': busy(), 'Tide Desk': tide + resend, 'Crew A': grp, 'Crew B': [(d, h, m + 1 if w == 'b' else m, w, t) for d, h, m, w, t in grp]}
    _, B, diag, draft, items = fleet(root, 'rep1', bots)
    rep_items = [x for x in items if x['user'] == ack]
    check(rep_items and any('repeat 5 days' in x.get('check', '') for x in rep_items), '2. a text sent on 3+ days is a judge item marked repeat')
    rt = {r['text'][:20]: r for r in B['Tide Desk']['repeated_texts']}
    check(len(rt[ack[:20]]['days']) == 5, '2. the acknowledgement is an exact repeat on 5 days (the host labels it ack)')
    lg = rt['Summarise the fake l']
    check(len(B['Tide Desk']['resends']) == 2 and len(lg['refs']) == 3 and len(lg['days']) == 3, f"2. resends within minutes are listed apart ({lg['refs']})")
    check(not B['Crew A']['repeated_texts'] and not B['Crew B']['repeated_texts'], '2. group-chat turns are not repeats of a member bot')
    names = {v['ref_prefix']: v['name'] for v in diag['bots'].values()}
    check(not any({names[r.split(':')[0]] for r in p['refs']} >= {'Crew A', 'Crew B'} for p in diag['fleet']['same_text_in_bots']),
          '2. a mirrored group turn is not "the same text in several bots"')
    gm = diag['fleet']['group_messages']
    check(gm['unique'] == 5 and gm['copies'] == 10, f'2. group messages are counted once across member bots ({gm})')

def test_promise_memory(root):
    ask, later = 'Pode preparar o relatório de vendas de março?', 'Claro, envio o relatório daqui a pouco.'
    pt = [(10, 9, 0, 'u', 'Olá, vamos começar o relatório'), (10, 9, 1, 'b', 'Vamos lá. [fake]'), (10, 9, 5, 'u', ask), (10, 9, 6, 'b', later),
          (10, 15, 0, 'u', 'Ainda estou à espera do relatório de março'), (10, 15, 1, 'b', 'Aqui está. [fake]')]
    pt += [(4, 9, 0, 'mem', [('2030-03-02', 'Mora em Lisboa e trabalha no centro.')])]
    pt += [(30, 9, 0, 'u', 'Diz-me um café perto de casa'), (30, 9, 1, 'b', 'Em Lisboa há este café. [fake]'),
           (30, 9, 3, 'u', 'Já não moro em Lisboa, mudei-me para o Porto em abril'), (30, 9, 4, 'b', 'Entendido. [fake]')]
    pt += [(d, 9, 30, 'u', f'Mais uma nota rápida número {d}') for d in range(31, 56, 3)]
    moved = 'Já não moro em Lisboa, mudei-me para o Porto em abril'
    _, B0, _, d0, _ = fleet(root, 'pm0', {'Main': busy(), 'Escritório': pt})
    _, B, _, draft, _ = fleet(root, 'pm1', {'Main': busy(), 'Escritório': pt},
                              labels={ask: ('new_request', None, 'later'), moved: ('correction', 'missing_context', None)})
    check(not B0['Escritório']['promises'], '3. control: no label, no promise listed')
    pj = B['Escritório']['promises']
    check(len(pj) == 1 and pj[0]['bot'].startswith('Claro') and pj[0]['next_user'].startswith('Ainda'), f'3. "later" lists the promise with the next user message ({pj})')
    m = B['Escritório']['memory']
    check(m['facts'][0]['text'].startswith('Mora em Lisboa') and m['newer_labelled'][0]['text'].startswith('Já não moro'),
          '3. memory facts come with a later labelled correction (any language)')
    check(not B0['Escritório']['memory']['newer_labelled'], '3. control: nothing labelled after the fact, nothing listed')

def test_docs():
    rub = open(os.path.join(SK, 'references', 'rubric_correction.md')).read(); cri = open(os.path.join(SK, 'references', 'criteria.md')).read()
    sk = open(os.path.join(SK, 'SKILL.md')).read()
    check('| keep |' in rub and '| ack |' in rub and '`later`' in rub and '[check: last]' in rub, '4. rubric documents keep, ack, later and check items')
    check('user_keep' in cri and 'within 30 minutes' in cri and 'group turn' in cri and 'newer_labelled' in cri, '4. criteria documents keep, resends, groups, newer_labelled')
    check(len(sk.splitlines()) <= 172 and 'keep or ack' in sk, '4. SKILL.md mentions keep/ack and stays within 172 lines')
    refs = ''.join(open(p).read() for p in glob.glob(os.path.join(SK, '**', '*.md'), recursive=True))
    check(not any(t in refs for t in ('Kiln Notes', 'Tide Desk', 'Harbour Crew', 'Lisboa', 'pottery')), '4. no fixture text in the skill docs')

def main():
    keep = '--keep' in sys.argv; root = tempfile.mkdtemp(prefix='it9-')
    try:
        test_keep(root); test_repeats(root); test_promise_memory(root); test_docs()
    finally:
        if not keep: shutil.rmtree(root, ignore_errors=True)
        else: print('kept', root)
    print(f"\n{len(t6.failures)} failure(s)")
    sys.exit(1 if t6.failures else 0)

if __name__ == '__main__':
    main()
