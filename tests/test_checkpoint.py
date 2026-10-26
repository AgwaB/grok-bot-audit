#!/usr/bin/env python3
"""Checkpoint save/load, merge, and every fallback to a full read. Synthetic chats only.

  python3 tests/test_checkpoint.py [--keep]
"""
import glob, json, os, re, shutil, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
SK = os.path.join(ROOT, 'skills', 'audit-my-bots'); S = os.path.join(SK, 'scripts')
sys.path.insert(0, S); sys.path.insert(0, HERE)
import checkpoint as CP
import make_fixture as mf

failures = []
AID = 'bbbbbbbb-0000-4000-8000-0000000000c1'
NAME = 'Apple Notes'
NEW_ID = 'bbbbbbbb-0000-4000-8000-0000000000c2'

def check(cond, msg):
    print(('PASS ' if cond else 'FAIL ') + msg)
    if not cond:
        failures.append(msg)

def run(*args, ok=True, env=None):
    e = os.environ.copy()
    e.pop('AUDIT_REPLAY_DIR', None); e.pop('AUDIT_STATE_DIR', None)
    if env:
        e.update(env)
    r = subprocess.run([sys.executable, *args], capture_output=True, text=True, env=e)
    if ok and r.returncode != 0:
        print(r.stdout, r.stderr)
        raise SystemExit('FAILED: ' + ' '.join(args))
    return r

def script_old():
    return [
        (0, 9, 0, 'u', 'Draft a fake note about apples'),
        (0, 9, 1, 'b', 'Here is a very long note about apples. [fake]'),
        (0, 9, 5, 'u', 'Too long, cut the apple note'),
        (0, 9, 6, 'b', 'Short note. [fake]'),
        (1, 9, 0, 'u', 'Add a line about pears'),
        (1, 9, 1, 'b', 'Pears added. [fake]'),
    ]

def script_new():
    return script_old() + [
        (2, 9, 0, 'u', 'Also too long, drop the pear story'),
        (2, 9, 1, 'b', 'Dropped the extra story. [fake]'),
    ]

def script_short():
    return script_old()[:-2]

def script_other():
    return [(d, 10, 0, 'u', 'Unrelated fake question %d' % d) for d in range(5)] + \
           [(d, 10, 1, 'b', 'Unrelated fake answer %d. [fake]' % d) for d in range(5)]

def pages_of(root, tag, script, size):
    base = os.path.join(root, 'pages-' + tag)
    mf.write_pages(AID, NAME, mf.convo(script), size=size, root=base)
    return os.path.join(base, AID)

def work(root, tag, name=NAME, aid=AID):
    W = os.path.join(root, 'w-' + tag)
    os.makedirs(os.path.join(W, 'tmp'))
    json.dump([dict(id=aid, name=name, description='')], open(os.path.join(W, 'bots.json'), 'w'))
    return W

def page_files(d):
    return sorted(glob.glob(os.path.join(d, '*.txt')))

def start_of(path):
    for line in open(path, encoding='utf-8'):
        m = re.search(r'positions\s+(\d+)', line)
        if m:
            return int(m.group(1))
    raise AssertionError('no header in ' + path)

def newest(d):
    return max(page_files(d), key=start_of)

def fetch(W, d, aid=AID, only=None):
    files = [only] if only else page_files(d)
    run(os.path.join(S, 'sessions.py'), 'save-page', '--work', W, *[f'{aid}={f}' for f in files])

def seal(W):
    os.makedirs(os.path.join(W, 'report'), exist_ok=True)
    json.dump(dict(ok=True), open(os.path.join(W, 'findings.json'), 'w'))
    open(os.path.join(W, 'report', 'fleet_report_2030-03-01.html'), 'w').write('<html></html>\n')
    open(os.path.join(W, 'report', 'checks.txt'), 'w').write('OK\n')

def export_and_label(W, needles):
    run(os.path.join(S, 'judge_inputs.py'), '--work', W)
    items = json.load(open(os.path.join(W, 'judge_inputs.json')))
    lines = []
    for it in items:
        for needle, topic in needles:
            if needle in it['user']:
                lines.append(f"{it['n']}\tcorrection\t{topic}\thigh\t-\t-\t{it['user'][:8]}\n")
    open(os.path.join(W, 'labels.tsv'), 'w').write(''.join(lines))
    return run(os.path.join(S, 'judge_inputs.py'), '--work', W, '--label', os.path.join(W, 'labels.tsv'))

def events(W, aid=AID):
    tl = json.load(open(os.path.join(W, 'timelines', aid + '.json')))
    return [(e['i'], e['role'], e.get('text'), e.get('ts')) for e in tl['events']]

def field(text, aid, col):
    for line in text.splitlines():
        p = line.split('\t')
        if p and p[0] == aid and len(p) > col:
            return p[col]
    return ''

def ckpt(state, aid=AID):
    return json.load(open(os.path.join(state, 'bots', aid + '.json')))

def seed(root):
    """One finished full run. Returns (state dir, work dir)."""
    state = os.path.join(root, 'state')
    W = work(root, 'seed')
    fetch(W, pages_of(root, 'old', script_old(), 4))
    run(os.path.join(S, 'sessions.py'), 'parse', '--work', W)
    export_and_label(W, [('Too long, cut the apple note', 'format_length')])
    seal(W)
    run(os.path.join(S, 'checkpoint.py'), 'commit', '--work', W, '--state', state)
    return state, W

def clone(root, state, tag):
    dest = os.path.join(root, 'state-' + tag)
    shutil.copytree(state, dest)
    return dest

def plan(W, state, full=False):
    args = [os.path.join(S, 'checkpoint.py'), 'plan', '--work', W, '--state', state]
    if full:
        args.append('--full')
    return run(*args)

def resume(root, state, tag, script, size, only_newest=True):
    """plan, fetch, next. Returns (work, plan stdout, next stdout)."""
    W = work(root, tag)
    pr = plan(W, state)
    d = pages_of(root, tag, script, size)
    fetch(W, d, only=newest(d) if only_newest else None)
    nx = run(os.path.join(S, 'checkpoint.py'), 'next', '--work', W, '--state', state, AID)
    return W, pr.stdout, nx.stdout

def test_save_load(root, state):
    cp = ckpt(state)
    check(cp['label_version'] == CP.LABEL_VERSION and cp['name'] == NAME and cp['anchor_pos'] == cp['total'] - 1
          and cp['anchor_sha'] == cp['entry_shas'][-1] and cp['head_sha'] == cp['entry_shas'][0]
          and len(cp['entry_shas']) == cp['total'] == len(mf.convo(script_old())),
          'save: checkpoint records the anchor, the entry hashes and the label version')
    labels = json.load(open(os.path.join(state, 'labels', AID + '.json')))
    check(any(v.get('type') == 'correction' and v.get('topic') == 'format_length' for v in labels.values())
          and CP.labels_sha(labels) == cp['labels_sha'] and len(labels) == cp['label_count'],
          'save: carried labels round-trip and match the stored hash')
    mode = os.stat(state).st_mode & 0o777
    file_mode = os.stat(os.path.join(state, 'bots', AID + '.json')).st_mode & 0o777
    check(mode == 0o700 and file_mode == 0o600, f'save: state dir is 0700 and the checkpoint file is 0600 ({oct(mode)}, {oct(file_mode)})')
    check(CP.DEFAULT_STATE == '/workspace/bot-audit-run/state' and 'skills' not in CP.DEFAULT_STATE,
          'save: the default checkpoint dir is the private run area, not the plugin')

def test_unchanged(root, state):
    W, pr, nx = resume(root, state, 'same', script_old(), 4)
    check(field(pr, AID, 2) == 'incremental' and field(pr, AID, 3) == 'continued', 'unchanged: plan continues')
    before = os.listdir(os.path.join(W, 'transcripts', AID))
    check(len(before) == 1, 'unchanged: only the newest page was fetched (%s)' % before)
    check(field(nx, AID, 1) == 'incremental' and field(nx, AID, 2) == 'stop', 'unchanged: next stops after that page (%s)' % nx.strip())
    run(os.path.join(S, 'checkpoint.py'), 'assemble', '--work', W, '--state', state)
    check(len(os.listdir(os.path.join(W, 'transcripts', AID))) > 1, 'unchanged: assemble restores the pages that were not re-read')
    run(os.path.join(S, 'sessions.py'), 'parse', '--work', W)
    seed_events = events(os.path.join(root, 'w-seed'))
    check(events(W) == seed_events, 'unchanged: the timeline matches the previous run')
    run(os.path.join(S, 'judge_inputs.py'), '--work', W)
    listed = run(os.path.join(S, 'judge_inputs.py'), '--work', W, '--list', '--short')
    check('-- no new items' in listed.stdout, 'unchanged: nothing new to label')
    export_and_label(W, [])
    old = json.load(open(os.path.join(state, 'labels', AID + '.json')))
    new = json.load(open(os.path.join(W, 'labels.json')))
    check(new == old, 'unchanged: labels.json is the carried labels')

def test_merge(root, state):
    W, pr, nx = resume(root, state, 'more', script_new(), 4)
    check(field(nx, AID, 1) == 'incremental' and field(nx, AID, 2) == 'stop', 'merge: the new tail overlaps the anchor, so next stops')
    run(os.path.join(S, 'checkpoint.py'), 'assemble', '--work', W, '--state', state)
    run(os.path.join(S, 'sessions.py'), 'parse', '--work', W)
    old, new = events(os.path.join(root, 'w-seed')), events(W)
    check(new[:len(old)] == old and len(new) > len(old), 'merge: old events keep their indexes and the new messages follow')
    run(os.path.join(S, 'judge_inputs.py'), '--work', W)
    listed = run(os.path.join(S, 'judge_inputs.py'), '--work', W, '--list', '--short')
    check('Also too long' in listed.stdout and 'cut the apple' not in listed.stdout, 'merge: the list shows the new reply only')
    export_and_label(W, [('Also too long, drop the pear story', 'format_length')])
    labels = json.load(open(os.path.join(W, 'labels.json')))
    topics = sorted(v.get('topic') for v in labels.values() if v.get('type') == 'correction')
    check(topics == ['format_length', 'format_length'], 'merge: the old correction and the new one are both labelled (%s)' % topics)
    run(os.path.join(S, 'diagnostics.py'), '--work', W, '--now', '2030-04-01 12:00')
    diag = json.load(open(os.path.join(W, 'diag.json')))
    check(diag['bots'][AID]['corrections'] == 2, 'merge: diagnostics counts both corrections across the whole chat')
    # labelling an old item is refused, and the carried label stays
    items = json.load(open(os.path.join(W, 'judge_inputs.json')))
    old_item = next(it for it in items if 'cut the apple' in it['user'])
    open(os.path.join(W, 'labels.tsv'), 'w').write(f"{old_item['n']}\tcorrection\tother\thigh\t-\t-\t{old_item['user'][:8]}\n")
    r = run(os.path.join(S, 'judge_inputs.py'), '--work', W, '--label', os.path.join(W, 'labels.tsv'), ok=False)
    kept = json.load(open(os.path.join(W, 'labels.json')))
    check(r.returncode != 0 and 'earlier run' in r.stdout and kept[old_item['key']]['topic'] == 'format_length',
          'merge: a line for an old item is refused and the carried label stays')

def test_shorter(root, state):
    W, _, nx = resume(root, state, 'short', script_short(), 20)
    check(field(nx, AID, 1) == 'full' and field(nx, AID, 3) == 'shorter' and field(nx, AID, 2) == 'stop',
          'fallback shorter: a smaller total is a full read (%s)' % nx.strip())
    run(os.path.join(S, 'checkpoint.py'), 'assemble', '--work', W, '--state', state)
    run(os.path.join(S, 'sessions.py'), 'parse', '--work', W)
    texts = ' '.join(t or '' for _, _, t, _ in events(W))
    check('pears' not in texts and 'apple' in texts, 'fallback shorter: stored pages are not merged back in')
    open(os.path.join(W, 'labels.tsv'), 'w').write('')
    export_and_label(W, [])
    labels = json.load(open(os.path.join(W, 'labels.json')))
    check(all(v.get('type') == 'none' for v in labels.values()) and labels, 'fallback shorter: old labels are not carried')

def test_compacted(root, state):
    entries = mf.convo(script_old())
    for e in reversed(entries):
        if e.get('role') == 'assistant':
            e['message']['content'][0]['input']['content'] += ' REWRITTEN'
            break
    base = os.path.join(root, 'pages-compact')
    mf.write_pages(AID, NAME, entries, size=20, root=base)
    W = work(root, 'compact')
    plan(W, state)
    fetch(W, os.path.join(base, AID))
    nx = run(os.path.join(S, 'checkpoint.py'), 'next', '--work', W, '--state', state, AID)
    check(field(nx.stdout, AID, 1) == 'full' and field(nx.stdout, AID, 3) == 'compacted',
          'fallback compacted: a rewritten entry in the overlap is a full read (%s)' % nx.stdout.strip())
    run(os.path.join(S, 'checkpoint.py'), 'assemble', '--work', W, '--state', state)
    run(os.path.join(S, 'sessions.py'), 'parse', '--work', W)
    texts = ' '.join(t or '' for _, _, t, _ in events(W))
    check('REWRITTEN' in texts, 'fallback compacted: the timeline is the pages just fetched')

def test_recreated(root, state):
    W, _, nx = resume(root, state, 'other', script_other(), 20)
    check(field(nx, AID, 1) == 'full' and field(nx, AID, 3) == 'recreated',
          'fallback recreated: a chat that shares no entry is a full read (%s)' % nx.strip())
    run(os.path.join(S, 'checkpoint.py'), 'assemble', '--work', W, '--state', state)
    run(os.path.join(S, 'sessions.py'), 'parse', '--work', W)
    texts = ' '.join(t or '' for _, _, t, _ in events(W))
    check('apple' not in texts and 'Unrelated fake question' in texts, 'fallback recreated: stored pages are not merged')

def test_plan_fallbacks(root, state):
    W = work(root, 'renamed', name='Renamed Fake Bot')
    pr = plan(W, clone(root, state, 'renamed'))
    check(field(pr.stdout, AID, 2) == 'full' and field(pr.stdout, AID, 3) == 'renamed', 'fallback renamed: a new profile name is a full read')

    st = clone(root, state, 'missing')
    os.remove(os.path.join(st, 'labels', AID + '.json'))
    pr = plan(work(root, 'missing'), st)
    check(field(pr.stdout, AID, 3) == 'labels missing', 'fallback labels missing')

    st = clone(root, state, 'badjson')
    open(os.path.join(st, 'labels', AID + '.json'), 'w').write('{')
    pr = plan(work(root, 'badjson'), st)
    check(field(pr.stdout, AID, 3) == 'labels unreadable', 'fallback labels unreadable: not JSON')

    st = clone(root, state, 'tamper')
    lp = os.path.join(st, 'labels', AID + '.json')
    data = json.load(open(lp))
    next(iter(data.values()))['evidence'] = 'tampered'
    json.dump(data, open(lp, 'w'))
    pr = plan(work(root, 'tamper'), st)
    check(field(pr.stdout, AID, 3) == 'labels unreadable', 'fallback labels unreadable: hash no longer matches')

    st = clone(root, state, 'version')
    cp = ckpt(st)
    cp['label_version'] = CP.LABEL_VERSION + 1
    json.dump(cp, open(os.path.join(st, 'bots', AID + '.json'), 'w'))
    pr = plan(work(root, 'version'), st)
    check(field(pr.stdout, AID, 3) == 'labeling changed', 'fallback labeling changed: label version mismatch')

    st = clone(root, state, 'hole')
    os.remove(newest(os.path.join(st, 'pages', AID)))
    pr = plan(work(root, 'hole'), st)
    check(field(pr.stdout, AID, 3) == 'checkpoint incomplete', 'fallback checkpoint incomplete: a saved page is missing')

    W = work(root, 'fresh')
    bots = json.load(open(os.path.join(W, 'bots.json')))
    bots.append(dict(id=NEW_ID, name='Pear Notes', description=''))
    json.dump(bots, open(os.path.join(W, 'bots.json'), 'w'))
    pr = plan(W, clone(root, state, 'fresh'))
    check(field(pr.stdout, AID, 2) == 'incremental' and field(pr.stdout, NEW_ID, 2) == 'full'
          and field(pr.stdout, NEW_ID, 3) == 'new bot', 'fallback new bot: an id with no checkpoint is a full read, the known bot continues')

    pr = plan(work(root, 'scratch'), clone(root, state, 'scratch'), full=True)
    check(field(pr.stdout, AID, 2) == 'full' and field(pr.stdout, AID, 3) == 'full re-run',
          'full re-run: plan --full ignores a valid checkpoint')

def test_commit_gates(root, state):
    st = clone(root, state, 'refuse')
    before = open(os.path.join(st, 'bots', AID + '.json'), encoding='utf-8').read()
    W = os.path.join(root, 'w-seed')
    open(os.path.join(W, 'report', 'checks.txt'), 'w').write('CHECK leftover\n')
    r = run(os.path.join(S, 'checkpoint.py'), 'commit', '--work', W, '--state', st, ok=False)
    after = open(os.path.join(st, 'bots', AID + '.json'), encoding='utf-8').read()
    check(r.returncode != 0 and 'commit refused: report checks failed' in r.stderr and after == before,
          'commit refused: failed report checks leave the checkpoint untouched')
    open(os.path.join(W, 'report', 'checks.txt'), 'w').write('OK\n')  # seed work is shared; put it back

    empty = os.path.join(root, 'state-empty')
    r = run(os.path.join(S, 'checkpoint.py'), 'commit', '--work', work(root, 'nofindings'), '--state', empty, ok=False)
    check(r.returncode != 0 and 'no findings.json' in r.stderr and not os.path.exists(os.path.join(empty, 'bots')),
          'commit refused: no report yet, so no checkpoint is created')

    replay = work(root, 'replay')
    json.dump(dict(now='2030-03-01 09:00'), open(os.path.join(replay, 'replay.json'), 'w'))
    seal(replay)
    st = clone(root, state, 'replay')
    before = open(os.path.join(st, 'bots', AID + '.json'), encoding='utf-8').read()
    r = run(os.path.join(S, 'checkpoint.py'), 'commit', '--work', replay, '--state', st)
    after = open(os.path.join(st, 'bots', AID + '.json'), encoding='utf-8').read()
    check('commit skipped: test mode' in r.stdout and after == before, 'commit skipped in test mode, checkpoint unchanged')

def test_full_replaces(root, state):
    st = clone(root, state, 'replace')
    W = work(root, 'replace')
    plan(W, st, full=True)
    fetch(W, pages_of(root, 'replace', script_new(), 4), only=None)
    run(os.path.join(S, 'sessions.py'), 'parse', '--work', W)
    export_and_label(W, [('Too long, cut the apple note', 'format_length'), ('Also too long, drop the pear story', 'format_length')])
    seal(W)
    run(os.path.join(S, 'checkpoint.py'), 'commit', '--work', W, '--state', st)
    cp = ckpt(st)
    check(cp['total'] == len(mf.convo(script_new())) and cp['anchor_pos'] == cp['total'] - 1,
          'full re-run: commit replaces the checkpoint with the new history')

def test_docs():
    skill = open(os.path.join(SK, 'SKILL.md'), encoding='utf-8').read()
    ref = open(os.path.join(SK, 'references', 'checkpoint.md'), encoding='utf-8').read()
    setup = open(os.path.join(SK, 'references', 'setup.md'), encoding='utf-8').read()
    check(len(skill.splitlines()) <= 172, f'SKILL.md stays within 172 lines ({len(skill.splitlines())})')
    check('checkpoint.py' in skill and 'plan --full' in skill and 'scan_mode.txt' in skill and 'no new items' in skill,
          'SKILL.md points at the checkpoint, a from-scratch run, and the chat summary')
    for reason in ('shorter', 'compacted', 'recreated', 'renamed', 'labels missing', 'labels unreadable',
                   'labeling changed', 'new bot', 'full re-run', 'checkpoint incomplete'):
        check(reason in ref, f'checkpoint.md documents the {reason} fallback')
    check('Second run, nothing new' in ref and 'UNCHANGED' in ref and '0700' in ref, 'checkpoint.md describes an unchanged second run')
    check('Incremental' in setup and 'UNCHANGED' in setup and 'plan --full' in setup and 'Safe to re-run' in setup,
          'setup.md: the weekly routine is incremental and still quiet when unchanged')

def main():
    keep = '--keep' in sys.argv
    root = tempfile.mkdtemp(prefix='ckpt-')
    try:
        state, _ = seed(root)
        test_save_load(root, state)
        test_unchanged(root, state)
        test_merge(root, state)
        test_shorter(root, state)
        test_compacted(root, state)
        test_recreated(root, state)
        test_plan_fallbacks(root, state)
        test_commit_gates(root, state)
        test_full_replaces(root, state)
        test_docs()
    finally:
        if keep:
            print('kept', root)
        else:
            shutil.rmtree(root, ignore_errors=True)
    print(f'{len(failures)} FAILED' if failures else 'ALL PASSED')
    sys.exit(1 if failures else 0)

if __name__ == '__main__':
    main()
