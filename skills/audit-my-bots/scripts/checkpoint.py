#!/usr/bin/env python3
"""Bot Audit checkpoints: resume each bot after the last message a finished run actually saw.

The checkpoint lives only in the private run area (mode 0700), never in the repo:

  /workspace/bot-audit-run/state/     (override with --state or $AUDIT_STATE_DIR)
      bots/<id>.json                  resume point, name, label version, entry hashes
      pages/<id>/page_*.txt           transcript pages the resume point was built from
      labels/<id>.json                labels carried forward for that bot

  python3 checkpoint.py plan --work W [--full] [--state DIR]
      One line per bot: id, name, full|incremental, reason, anchor.
      Writes W/tmp/plan.json. --full marks every bot full (a from-scratch audit).
      A replay ($AUDIT_REPLAY_DIR or W/replay.json) marks every bot full and does not read state.
  python3 checkpoint.py next --work W [--state DIR] ID [ID ...]
      After save-page. Prints id, mode, action, reason.
      action is stop (this bot's read is done), before=N (ReadTranscript with that before),
      or newest (ReadTranscript with no before). A checkpoint that no longer matches is switched
      to full; keep going until stop.
  python3 checkpoint.py assemble --work W [--state DIR]
      Copies stored pages for bots that are still incremental, writes W/tmp/carried_labels.json
      and W/tmp/scan_mode.txt. Does not copy stored pages for a full bot.
  python3 checkpoint.py commit --work W [--state DIR]
      Snapshots pages and labels into the state dir. Refuses unless this run's report checks
      passed and the pages, timeline and labels agree. A replay commits nothing.

LABEL_VERSION below is the labeling generation. Bump it when the rubric or the label schema
changes what an old label means. Leave it alone for report wording or for facts the diagnostics count.
"""
import argparse, datetime as dt, glob, hashlib, json, os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import dump_json, load_json, page_start
from judge_inputs import TYPES
from sessions import localize, parse_one

# Bump when a stored label would be wrong under the new rubric (new type that must be re-judged,
# or a changed meaning of correction, preference, keep or ack). Not for wording or diagnostic counts.
LABEL_VERSION = 1
RUN_ROOT = '/workspace/bot-audit-run'
DEFAULT_STATE = os.path.join(RUN_ROOT, 'state')

def state_dir(a):
    return os.path.abspath(a.state or os.environ.get('AUDIT_STATE_DIR') or DEFAULT_STATE)

def test_mode(work):
    return bool(os.environ.get('AUDIT_REPLAY_DIR')) or os.path.isfile(os.path.join(work, 'replay.json'))

def sha1(s):
    return hashlib.sha1(s.encode('utf-8')).hexdigest()

def labels_sha(data):
    blob = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return sha1(blob)

def safe_id(bot_id):
    if not isinstance(bot_id, str) or not bot_id or bot_id in ('.', '..'):
        sys.exit('bad bot id')
    if os.sep in bot_id or (os.altsep and os.altsep in bot_id):
        sys.exit('bad bot id')
    return bot_id

def bot_path(state, kind, bot_id, file=False):
    bot_id = safe_id(bot_id)
    root = os.path.abspath(os.path.join(state, kind))
    path = os.path.abspath(os.path.join(root, bot_id + ('.json' if file else '')))
    if os.path.commonpath([root, path]) != root:
        sys.exit('bad bot id')
    return path

def lock(path):
    """Owner-only access (go-rwx) on a directory, and on files under it when it is a tree."""
    if not os.path.exists(path):
        return
    os.chmod(path, 0o700 if os.path.isdir(path) else 0o600)
    if os.path.isdir(path):
        for root, dirs, files in os.walk(path):
            for d in dirs:
                os.chmod(os.path.join(root, d), 0o700)
            for f in files:
                os.chmod(os.path.join(root, f), 0o600)

def prepare_state(state, create):
    """Make the state directory private. Creates it only when asked (commit), so a plan that
    finds nothing does not leave an empty directory behind unless one was already there."""
    if create:
        os.makedirs(state, mode=0o700, exist_ok=True)
    elif not os.path.isdir(state):
        return False
    lock(state)
    if os.path.abspath(state) == os.path.abspath(DEFAULT_STATE) and os.path.isdir(RUN_ROOT):
        os.chmod(RUN_ROOT, 0o700)
    return True

def read_page(path):
    info = page_start(path)
    if not info:
        return None
    start, end, total = info
    lines = []
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            if line.startswith('{'):
                lines.append(line.rstrip('\n'))
    return dict(start=start, end=end, total=total, lines=lines, path=path)

def work_pages(work, bot_id):
    d = os.path.join(work, 'transcripts', safe_id(bot_id))
    out = []
    for f in sorted(glob.glob(os.path.join(d, 'page_*.txt'))):
        p = read_page(f)
        if p:
            out.append(p)
    return out

def index_pages(pages, strict=False):
    """{position: sha1 of that raw entry} and the transcript total.

    A page saved on an earlier run still says the old total in its header. The total that counts is
    the largest one (the read that saw the newest end). strict=True rejects mixed totals: use it for
    pages fetched in this run, which must all describe the same transcript."""
    if not pages:
        raise ValueError('empty')
    totals = {p['total'] for p in pages}
    if strict and len(totals) != 1:
        raise ValueError('totals')
    total = max(totals)
    got = {}
    for p in pages:
        if p['start'] < 0 or p['end'] < p['start'] or p['end'] >= total:
            raise ValueError('range')
        n = p['end'] - p['start'] + 1
        if len(p['lines']) != n:
            raise ValueError('count')
        for i, line in enumerate(p['lines']):
            pos, h = p['start'] + i, sha1(line)
            if pos >= total:
                raise ValueError('range')
            if pos in got and got[pos] != h:
                raise ValueError('conflict')
            got[pos] = h
    return got, total

def covered(got, lo, hi):
    return hi < lo or all(pos in got for pos in range(lo, hi + 1))

def first_gap(got, lo, hi):
    for pos in range(lo, hi + 1):
        if pos not in got:
            return pos
    return None

def before_for(pages, gap):
    """The ReadTranscript action that fetches a hole at `gap` (a position we do not have yet)."""
    starts = sorted(p['start'] for p in pages if p['start'] > gap)
    if starts:
        return 'before=%d' % starts[0]
    if pages and max(p['end'] for p in pages) >= max(p['total'] for p in pages) - 1:
        return 'before=%d' % min(p['start'] for p in pages)
    return 'newest'

def page_action(pages):
    """stop once 0..total-1 is in hand; otherwise the next ReadTranscript call."""
    if not pages:
        return 'newest'
    try:
        got, total = index_pages(pages)
    except ValueError:
        if any(p['start'] == 0 for p in pages) and max(p['end'] for p in pages) >= max(p['total'] for p in pages) - 1:
            return 'stop'
        return 'before=%d' % min(p['start'] for p in pages)
    if covered(got, 0, total - 1):
        return 'stop'
    return before_for(pages, first_gap(got, 0, total - 1))

def labels_valid(data):
    if not isinstance(data, dict):
        return False
    for k, v in data.items():
        bot, _, i = str(k).rpartition(':')
        if not bot or not i.isdigit() or not isinstance(v, dict):
            return False
        if v.get('type') not in TYPES or not isinstance(v.get('label'), bool):
            return False
        if v['label'] != (v['type'] == 'correction'):
            return False
        if v.get('topic') is not None and not isinstance(v.get('topic'), str):
            return False
    return True

def load_checkpoint(state, bot_id):
    p = bot_path(state, 'bots', bot_id, file=True)
    if not os.path.isfile(p):
        return None, 'new bot'
    try:
        cp = json.load(open(p, encoding='utf-8'))
    except Exception:
        return None, 'checkpoint incomplete'
    if not isinstance(cp, dict) or not isinstance(cp.get('entry_shas'), list) or not isinstance(cp.get('total'), int):
        return None, 'checkpoint incomplete'
    return cp, ''

def stored_shas(state, bot_id):
    d = bot_path(state, 'pages', bot_id)
    if not os.path.isdir(d):
        return None
    pages = []
    for f in sorted(glob.glob(os.path.join(d, 'page_*.txt'))):
        p = read_page(f)
        if p:
            pages.append(p)
    if not pages:
        return None
    try:
        got, total = index_pages(pages)
    except ValueError:
        return None
    if not covered(got, 0, total - 1):
        return None
    return [got[i] for i in range(total)]

def classify(state, bot):
    """(mode, reason, anchor or None) before any new page is read."""
    cp, why = load_checkpoint(state, bot['id'])
    if cp is None:
        return 'full', why, None
    if cp.get('label_version') != LABEL_VERSION:
        return 'full', 'labeling changed', None
    if cp.get('name') != bot['name']:
        return 'full', 'renamed', None
    lp = bot_path(state, 'labels', bot['id'], file=True)
    if not os.path.isfile(lp):
        return 'full', 'labels missing', None
    try:
        data = json.load(open(lp, encoding='utf-8'))
    except Exception:
        return 'full', 'labels unreadable', None
    if not labels_valid(data) or labels_sha(data) != cp.get('labels_sha'):
        return 'full', 'labels unreadable', None
    shas = stored_shas(state, bot['id'])
    if not shas or shas != cp.get('entry_shas') or len(shas) != cp.get('total'):
        return 'full', 'checkpoint incomplete', None
    if cp.get('anchor_pos') != cp['total'] - 1 or cp.get('anchor_sha') != shas[-1]:
        return 'full', 'checkpoint incomplete', None
    return 'incremental', 'continued', cp['anchor_pos']

def plan_path(work):
    return os.path.join(work, 'tmp', 'plan.json')

def load_plan(work):
    p = plan_path(work)
    if not os.path.isfile(p):
        sys.exit('no plan; run checkpoint.py plan first')
    plan = load_json(p, None)
    if not isinstance(plan, dict) or not isinstance(plan.get('bots'), dict):
        sys.exit('plan is unreadable; run checkpoint.py plan again')
    return plan

def save_plan(work, plan):
    os.makedirs(os.path.join(work, 'tmp'), exist_ok=True)
    dump_json(plan, plan_path(work))

def cmd_plan(a):
    bots = load_json(os.path.join(a.work, 'bots.json'), None)
    if not isinstance(bots, list):
        sys.exit('no bots.json; run sessions.py list-bots first')
    state = state_dir(a)
    full = bool(a.full) or test_mode(a.work)
    if not full:
        prepare_state(state, create=False)
    plan = dict(label_version=LABEL_VERSION, full_request=bool(a.full), test_mode=test_mode(a.work), bots={})
    for b in bots:
        if full:
            reason = 'replay' if test_mode(a.work) and not a.full else 'full re-run'
            mode, anchor = 'full', None
        else:
            mode, reason, anchor = classify(state, b)
        plan['bots'][b['id']] = dict(id=b['id'], name=b['name'], mode=mode, reason=reason,
                                      anchor_pos=anchor, verified=False)
        anch = '-' if anchor is None else str(anchor)
        print(f"{b['id']}\t{b['name'].replace(chr(9), ' ')}\t{mode}\t{reason}\tanchor={anch}")
    save_plan(a.work, plan)

def flip(info, reason):
    info['mode'] = 'full'
    info['reason'] = reason
    info['verified'] = False
    info['anchor_pos'] = None

def decide(pages, cp):
    """(mode, action, reason) for an incremental bot, from the pages fetched this run."""
    if not pages:
        return 'incremental', 'newest', 'continued'
    try:
        got, total = index_pages(pages, strict=True)
    except ValueError:
        return 'full', page_action(pages), 'compacted'
    if total < cp['total']:
        return 'full', page_action(pages), 'shorter'
    old = cp['entry_shas']
    compared = matches = 0
    mismatch = False
    for pos, h in got.items():
        if pos < cp['total']:
            compared += 1
            if pos < len(old) and h == old[pos]:
                matches += 1
            else:
                mismatch = True
    anchor = cp['anchor_pos']
    if mismatch:
        return 'full', page_action(pages), ('recreated' if matches == 0 else 'compacted')
    if anchor not in got:
        return 'incremental', before_for(pages, anchor), 'continued'
    if got.get(anchor) != cp.get('anchor_sha'):
        return 'full', page_action(pages), 'compacted'
    if covered(got, anchor, total - 1):
        return 'incremental', 'stop', 'continued'
    return 'incremental', before_for(pages, first_gap(got, anchor, total - 1)), 'continued'

def cmd_next(a):
    plan = load_plan(a.work)
    state = state_dir(a)
    if not a.ids:
        sys.exit('give at least one bot id')
    for bot_id in a.ids:
        info = plan['bots'].get(bot_id)
        if not info:
            sys.exit('bot %s is not in the plan' % bot_id)
        pages = work_pages(a.work, bot_id)
        if info['mode'] == 'full':
            action = page_action(pages)
            if action == 'stop':
                info['verified'] = True
        else:
            cp, why = load_checkpoint(state, bot_id)
            if cp is None:
                flip(info, why)
                action = page_action(pages)
            else:
                mode, action, reason = decide(pages, cp)
                if mode == 'full':
                    flip(info, reason)
                elif action == 'stop':
                    info['verified'] = True
                    info['reason'] = reason
        if info['mode'] == 'full' and info['reason'] == 'continued':
            info['reason'] = 'full re-run'
        print(f"{bot_id}\t{info['mode']}\t{action}\t{info['reason']}")
    save_plan(a.work, plan)

def pages_complete(pages):
    try:
        got, total = index_pages(pages)
    except ValueError:
        return False
    return covered(got, 0, total - 1)

def cmd_assemble(a):
    plan = load_plan(a.work)
    bots = load_json(os.path.join(a.work, 'bots.json'), [])
    state = state_dir(a)
    carried, problems = {}, []
    os.makedirs(os.path.join(a.work, 'tmp'), exist_ok=True)
    for b in bots:
        info = plan['bots'].get(b['id'])
        if not info:
            problems.append('%s: not in the plan' % b['name']); continue
        if info['mode'] == 'incremental':
            if not info.get('verified'):
                problems.append('%s: checkpoint not checked yet; run checkpoint.py next' % b['name']); continue
            src = bot_path(state, 'pages', b['id'])
            dst = os.path.join(a.work, 'transcripts', b['id'])
            os.makedirs(dst, exist_ok=True)
            copied = []
            if os.path.isdir(src):
                for name in os.listdir(src):
                    target = os.path.join(dst, name)
                    if name.startswith('page_') and name.endswith('.txt') and not os.path.exists(target):
                        shutil.copyfile(os.path.join(src, name), target)
                        copied.append(target)
            if not pages_complete(work_pages(a.work, b['id'])):
                for f in copied:
                    os.remove(f)
                flip(info, 'checkpoint incomplete')
                problems.append('%s: saved pages do not cover the history; switched to full, keep fetching' % b['name'])
                continue
            cp, _why = load_checkpoint(state, b['id'])
            data = load_json(bot_path(state, 'labels', b['id'], file=True), None)
            if not cp or not isinstance(data, dict) or not labels_valid(data) or labels_sha(data) != cp.get('labels_sha'):
                flip(info, 'labels unreadable')
                problems.append('%s: carried labels are unreadable; switched to full' % b['name'])
                continue
            carried.update({k: v for k, v in data.items() if str(k).rpartition(':')[0] == b['id']})
        elif not pages_complete(work_pages(a.work, b['id'])):
            problems.append('%s: history not complete (%s)' % (b['name'], page_action(work_pages(a.work, b['id']))))
    save_plan(a.work, plan)
    scan = os.path.join(a.work, 'tmp', 'scan_mode.txt')
    with open(scan, 'w', encoding='utf-8') as fh:
        for b in bots:
            info = plan['bots'].get(b['id'], {})
            fh.write(f"{info.get('mode', 'full')}\t{b['id']}\t{b['name']}\t{info.get('reason', '')}\n")
    carry_path = os.path.join(a.work, 'tmp', 'carried_labels.json')
    if any(plan['bots'].get(b['id'], {}).get('mode') == 'incremental' for b in bots):
        dump_json(carried, carry_path)
    elif os.path.exists(carry_path):
        os.remove(carry_path)
    n_inc = sum(1 for b in bots if plan['bots'].get(b['id'], {}).get('mode') == 'incremental')
    print(f'assembled: {n_inc} incremental, {len(bots) - n_inc} full -> {scan}')
    if problems:
        sys.exit('assemble: ' + '; '.join(problems))

def checks_ok(work):
    p = os.path.join(work, 'report', 'checks.txt')
    if not os.path.isfile(p):
        return False
    lines = open(p, encoding='utf-8').read().splitlines()
    return any(ln.strip() == 'OK' for ln in lines) and not any(ln.startswith('CHECK') for ln in lines)

def timeline_matches(work, bot_id):
    path = os.path.join(work, 'timelines', safe_id(bot_id) + '.json')
    saved = load_json(path, None)
    if not isinstance(saved, dict) or not (saved.get('coverage') or {}).get('complete'):
        return False
    d = os.path.join(work, 'transcripts', safe_id(bot_id))
    if not glob.glob(os.path.join(d, 'page_*.txt')):
        return False
    fresh = parse_one(d)
    localize(fresh, dt.timedelta(hours=saved.get('utc_offset_hours') or 0))
    return fresh['events'] == saved.get('events')

def split_labels(labels):
    out = {}
    for k, v in labels.items():
        bot, _, i = str(k).rpartition(':')
        if bot and i.isdigit():
            out.setdefault(bot, {})[k] = v
    return out

def replace_path(src, dst):
    """Move src onto dst. src is removed. A crash keeps the previous dst until the rename."""
    parent = os.path.dirname(dst)
    os.makedirs(parent, exist_ok=True)
    bak = dst + '.bak'
    if os.path.exists(bak):
        shutil.rmtree(bak) if os.path.isdir(bak) else os.remove(bak)
    if os.path.exists(dst):
        os.rename(dst, bak)
    os.rename(src, dst)
    if os.path.exists(bak):
        shutil.rmtree(bak) if os.path.isdir(bak) else os.remove(bak)

def cmd_commit(a):
    if test_mode(a.work):
        print('commit skipped: test mode')
        return
    work, state = a.work, state_dir(a)
    bots = load_json(os.path.join(work, 'bots.json'), None)
    if not isinstance(bots, list) or not bots:
        sys.exit('commit refused: no bots.json')
    if not os.path.isfile(os.path.join(work, 'findings.json')):
        sys.exit('commit refused: no findings.json')
    try:
        json.load(open(os.path.join(work, 'findings.json'), encoding='utf-8'))
    except Exception:
        sys.exit('commit refused: findings.json is unreadable')
    if not glob.glob(os.path.join(work, 'report', 'fleet_report_*.html')):
        sys.exit('commit refused: no report')
    if not checks_ok(work):
        sys.exit('commit refused: report checks failed')
    items = load_json(os.path.join(work, 'judge_inputs.json'), None)
    labels = load_json(os.path.join(work, 'labels.json'), None)
    if not isinstance(items, list) or not isinstance(labels, dict) or not labels_valid(labels):
        sys.exit('commit refused: labels do not cover every item')
    missing = [x.get('key') for x in items if x.get('key') not in labels]
    if missing:
        sys.exit('commit refused: labels do not cover every item')
    by_bot = split_labels(labels)
    for b in bots:
        if not pages_complete(work_pages(work, b['id'])):
            sys.exit('commit refused: history incomplete for %s' % b['name'])
        if not timeline_matches(work, b['id']):
            sys.exit('commit refused: timeline does not match the pages for %s' % b['name'])
        mine = by_bot.get(b['id'], {})
        want = {x['key'] for x in items if str(x.get('key', '')).rpartition(':')[0] == b['id']}
        if set(mine) != want:
            sys.exit('commit refused: labels do not cover every item')
    prepare_state(state, create=True)
    stage = os.path.join(state, '.stage-%d' % os.getpid())
    if os.path.exists(stage):
        shutil.rmtree(stage)
    os.makedirs(stage, mode=0o700)
    try:
        built = []
        for b in bots:
            got, total = index_pages(work_pages(work, b['id']))
            shas = [got[i] for i in range(total)]
            mine = by_bot.get(b['id'], {})
            cp = dict(id=b['id'], name=b['name'], label_version=LABEL_VERSION, total=total,
                      end=total - 1, anchor_pos=total - 1, anchor_sha=shas[-1] if shas else None,
                      head_sha=shas[0] if shas else None, entry_shas=shas, label_count=len(mine),
                      labels_sha=labels_sha(mine),
                      saved_at=dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))
            root = os.path.join(stage, b['id'])
            pages = os.path.join(root, 'pages')
            os.makedirs(pages, mode=0o700)
            for p in work_pages(work, b['id']):
                shutil.copyfile(p['path'], os.path.join(pages, os.path.basename(p['path'])))
            dump_json(mine, os.path.join(root, 'labels.json'))
            dump_json(cp, os.path.join(root, 'checkpoint.json'))
            built.append((b, root))
        for b, root in built:
            replace_path(os.path.join(root, 'pages'), bot_path(state, 'pages', b['id']))
            replace_path(os.path.join(root, 'labels.json'), bot_path(state, 'labels', b['id'], file=True))
            replace_path(os.path.join(root, 'checkpoint.json'), bot_path(state, 'bots', b['id'], file=True))
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    lock(state)
    print(f'checkpoint saved: {len(bots)} bots -> {state}')

def main():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument('--work', required=True)
    common.add_argument('--state', help='checkpoint directory (default $AUDIT_STATE_DIR or the private run area)')
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    p = sp.add_parser('plan', parents=[common]); p.add_argument('--full', action='store_true'); p.set_defaults(fn=cmd_plan)
    p = sp.add_parser('next', parents=[common]); p.add_argument('ids', nargs='+'); p.set_defaults(fn=cmd_next)
    p = sp.add_parser('assemble', parents=[common]); p.set_defaults(fn=cmd_assemble)
    p = sp.add_parser('commit', parents=[common]); p.set_defaults(fn=cmd_commit)
    a = ap.parse_args()
    a.fn(a)

if __name__ == '__main__':
    main()
