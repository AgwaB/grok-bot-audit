#!/usr/bin/env python3
r"""Bot Audit, step 3: pick user messages that might be corrections, export judge inputs, record labels.

  python3 judge_inputs.py --work W
      W/timelines/*.json -> W/judge_inputs.json: every typed user reply after a bot message, for every bot, in any
      language (no word filter: you judge each one). Each item: {n, key, ref, bot, bot_name, ts, request, prev_bot,
      user, next_bot}. "n" is a short number for the item; "ref" is the message id to cite in findings; "request" is
      the user's message that started the exchange; prev_bot ends with the app's question cards the bot showed.
  python3 judge_inputs.py --work W --digest [--from N] [--kb K]
      Every typed user message of every bot, one line each: ref, time, marks, text (first 160 characters). Marks are
      facts: [group G] (a group-chat turn, mirrored into each member's chat), [resend] (the same text as the user's
      previous message within 30 minutes), [same as REF] (the exact same text sent earlier on another day). Batches of
      about 10 KB; the last line gives the --from of the next batch. Read it to find repeated requests, the same job in
      several bots, and anything else that needs the whole history.
  python3 judge_inputs.py --work W --list [--from N] [--to M | --kb K] [--short | --width N]
      Compact view: one block per item with short excerpts, numbered. A bot message already shown as the previous
      item's "next>" is not repeated. --short cuts bot text to 100 characters (user text stays at 400); --width N sets
      the bot excerpt length. Without --to, it prints one batch of about 10 KB (--kb K to change) and its last line
      gives the --from of the next batch. How many items fit depends on the chats (non-Latin scripts take more bytes
      per character), so batches are cut by size, not by a fixed count. With --to, the last line says how many items
      of this size fit in about 10 KB.
  python3 judge_inputs.py --work W --show N|KEY [...]
      The full messages around these items.
  python3 judge_inputs.py --work W --label FILE
      FILE: one line per correction or preference (nothing else needs a line), 7 tab-separated columns:
        n  type  topic  confidence  evidence  promised  user_start
      n = item number (or key); type = correction | preference | keep | ack | topic_rejection | new_request |
      question | clarification | other (keep: the user wants this bot kept or says it is paused on purpose; ack: the
      message only thanks, approves or acknowledges); topic = short snake_case cause for corrections and preferences; confidence = high |
      medium | low; evidence = a few words copied from the user message (never a secret); promised = yes if the bot's
      reply promises a lasting change ("from now on I'll..."), later if it promises to do or send something later
      on its own, else empty; user_start = the first few characters of the
      user message, checked against the item (a mismatch is an error: guards against off-by-one). Empty cell: \N or -.
      Each line is echoed with the item's user text. Lines may be added over several batches; each run rewrites
      W/labels.json from the whole file; items without a line are type "none" (not a correction).
      No candidates at all -> labels.json is {}.
      Incremental run: if W/tmp/carried_labels.json exists (checkpoint.py assemble), those labels are kept and
      --list hides them. A line for an item already in that file is an error. Items in neither are "none".

Items are marked "check" when they are each bot's last 3 user messages (check: last; keeping or pausing a bot is said
there) or a text the user sent word for word on 3+ days outside group chats (check: repeat N days). They need a line
only if they are keep, ack, a correction or a preference.

Excerpts keep the start and the end of
long messages (admissions such as "you're right, I missed…" often come at the end of a reply). App notices
(attachments) and file paths are already removed from user messages by sessions.py parse.
"""
import argparse, glob, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import dump_json, load_json, norm, short_ids, P, RESEND_MIN

PREV_N, USER_N, NEXT_N, REQ_N = 800, 1000, 900, 300
TYPES = ('correction', 'topic_rejection', 'new_request', 'question', 'clarification', 'preference', 'keep', 'ack', 'other', 'none')
TAIL_N, REP_DAYS = 3, 3   # each bot's last user messages; a message repeated on this many days
EMPTY = ('', '\\N', '-')

def ex(t, n, head=0.5):
    """Excerpt: the whole text if short, else its start and its end joined by ' … '."""
    t = norm(t)
    if len(t) <= n:
        return t
    h = int(n * head)
    return t[:h].rstrip() + ' … ' + t[-(n - h):].lstrip()

def pairs(tl):
    """(user event, previous bot event, question cards after it, bot replies after the user, the exchange's request)."""
    ev = [e for e in tl['events'] if e['role'] in ('user', 'bot') or e.get('kind') == 'skipped_question']
    last_req, prev_bot, cards = None, None, []
    for k, e in enumerate(ev):
        if e.get('kind') == 'skipped_question':
            if prev_bot is not None: cards.append(e['text'])
            continue
        if e['role'] == 'bot':
            if prev_bot is None or ev[k - 1]['role'] != 'bot' or cards: cards = []
            prev_bot = e if prev_bot is None or ev[k - 1]['role'] != 'bot' else dict(e, text=prev_bot['text'] + '\n' + e['text'])
            continue
        if prev_bot is not None:
            nxt = []
            for f in ev[k + 1:]:
                if f['role'] == 'user': break
                if f['role'] == 'bot': nxt.append(f['text'])
            yield e, prev_bot, list(cards), nxt, last_req
        last_req, prev_bot, cards = e, None, []

def around(tl, i):
    """(the bot messages just before the user event i, the bot's replies after it)."""
    ev = [e for e in tl['events'] if e['role'] in ('user', 'bot')]
    k = next(n for n, e in enumerate(ev) if e['i'] == i)
    prev = []
    for f in reversed(ev[:k]):
        if f['role'] == 'user': break
        prev.insert(0, f['text'])
    nxt = []
    for f in ev[k + 1:]:
        if f['role'] == 'user': break
        nxt.append(f['text'])
    return '\n'.join(prev), nxt

def resends(users):
    """Indexes of user messages that repeat the user's previous message word for word within RESEND_MIN minutes."""
    out, last = set(), None
    for e in users:
        if last and e.get('ts') and last.get('ts') and norm(e['text']).lower() == norm(last['text']).lower() and \
                (P(e['ts']) - P(last['ts'])).total_seconds() <= RESEND_MIN * 60:
            out.add(e['i'])
        last = e
    return out

def checks(tl):
    """{event index: [reasons]}: the user's last messages to this bot (keeping or pausing it is said there, in any
    language) and the latest copy of each text sent word for word on 3+ days outside group chats."""
    users = [e for e in tl['events'] if e['role'] == 'user' and norm(e['text'])]
    marks = {}
    for e in users[-TAIL_N:]: marks.setdefault(e['i'], []).append('last')
    same = {}
    for e in users:
        if 'group' not in e and e.get('ts'): same.setdefault(norm(e['text']).lower(), []).append(e)
    for es in same.values():
        days = {e['ts'][:10] for e in es}
        if len(days) >= REP_DAYS: marks.setdefault(es[-1]['i'], []).append(f'repeat {len(days)} days')
    return marks

def card_text(cards):
    return ''.join(f'\n[question card: {c}]' for c in cards)

def load_items(work):
    return load_json(os.path.join(work, 'judge_inputs.json'), [])

def find(items, ref):
    return next((x for x in items if str(x.get('n')) == str(ref) or x['key'] == ref), None)

def carried_labels(work):
    """Labels kept from the previous run, or None when this run is not merging a checkpoint.
    A file that exists but isn't a label map is an error: guessing would wipe the carried labels."""
    path = os.path.join(work, 'tmp', 'carried_labels.json')
    plan = load_json(os.path.join(work, 'tmp', 'plan.json'), None)
    incremental = isinstance(plan, dict) and any(b.get('mode') == 'incremental' for b in (plan.get('bots') or {}).values())
    if not os.path.isfile(path):
        if incremental:
            sys.exit('carried labels missing; run checkpoint.py assemble')
        return None
    data = load_json(path, None)
    if not isinstance(data, dict) or any(not isinstance(v, dict) or v.get('type') not in TYPES for v in data.values()):
        sys.exit('carried labels are unreadable: ' + path)
    return data

def show(work, refs):
    items = load_items(work)
    tls = {os.path.basename(p)[:-5]: load_json(p) for p in glob.glob(os.path.join(work, 'timelines', '*.json'))}
    for ref in refs:
        it = find(items, ref)
        bid, _, i = (it['key'] if it else ref).partition(':')
        tl = tls.get(bid)
        hit = next((h for h in pairs(tl) if str(h[0]['i']) == i), None) if tl else None
        if not hit:
            print(f'== {ref}: not found'); continue
        e, p, cards, n, req = hit
        print(f'== {ref} ({tl["name"]}, {e["ts"]})\n-- request:\n{req["text"] if req else "(none)"}\n-- bot before:\n{p["text"]}{card_text(cards)}'
              f'\n-- user:\n{e["text"]}\n-- bot after:\n' + ('\n\n'.join(n) or '(no reply)') + '\n')

def listing(work, lo, hi, width=220, kb=0):
    """Items lo..hi. With kb > 0, stop once the batch reaches about kb KB (bytes, so the count depends on the script and
    length of the messages) and print the --from of the next batch. Items already in the carried labels are hidden."""
    hidden = set((carried_labels(work) or {}))
    prev, size, n, first, last, more = None, 0, 0, None, None, None
    items = load_items(work)
    for x in items:
        if lo <= x['n'] <= hi:
            if x['key'] in hidden:
                continue
            if kb and n and size >= kb * 1024:
                more = x['n']; break
            same = prev and prev['bot'] == x['bot'] and prev['next_bot'] and norm(prev['next_bot'])[:120] == norm(x['prev_bot'])[:120]
            bot = f"(= next> of #{prev['n']})" if same else ex(x['prev_bot'], width, 0.3)
            block = (f"#{x['n']} {x.get('ref', '')} {x['bot_name']} {x['ts']}" + (f" [check: {x['check']}]" if x.get('check') else '') + f"\n  bot> {bot}\n  user> {ex(x['user'], 400, 0.7)}\n"
                     f"  next> {ex(x['next_bot'], width, 0.3) or '(no reply)'}")
            print(block); size += len(block.encode('utf-8')) + 1; n += 1; last = x['n']; first = first or x['n']
        prev = x
    if n:
        per = size / n
        tail = (f'; next batch: --from {more}' if more else '; that was the last item') if kb else \
            f"; about {max(5, int(10240 // per))} items of this size fit in 10 KB"
        print(f"-- {n} items (#{first}-#{last}), {size / 1024:.1f} KB{tail}"
              + ('' if width <= 100 else ' (--short makes items smaller)'))
    elif hidden and not any(x['key'] not in hidden and x['n'] >= lo for x in items):
        print('-- no new items' if not any(x['key'] not in hidden for x in items) or lo <= 1
              else '-- no items from #%d on: that was the last batch' % lo)
    elif kb:
        print('-- no items from #%d on: that was the last batch' % lo)

def label(work, path):
    items = load_items(work); bad = []
    carry = carried_labels(work)
    out = {k: v for k, v in (carry or {}).items() if any(it['key'] == k for it in items)}
    for ln, line in enumerate(open(path, encoding='utf-8'), 1):
        if not line.strip() or line.lstrip().startswith('#'): continue
        parts = [p.strip() for p in line.rstrip('\n').split('\t')] + [''] * 7
        parts = ['' if p in EMPTY else p for p in parts]
        it = find(items, parts[0])
        ty = parts[1].lower()
        if not it or ty not in TYPES:
            bad.append(f'line {ln}: ' + ('unknown item ' + parts[0] if not it else 'unknown type ' + parts[1])); continue
        start = norm(parts[6])
        if start and not norm(it['user']).lower().startswith(start.lower()):
            bad.append(f"line {ln}: item {parts[0]} user text starts \"{norm(it['user'])[:30]}\", not \"{start[:30]}\" (off by one?)"); continue
        if carry is not None and it['key'] in carry:
            bad.append(f'line {ln}: item {parts[0]} was labelled on an earlier run; leave it out'); continue
        if it['key'] in out: bad.append(f'line {ln}: item {parts[0]} labelled twice (the later line wins)')
        out[it['key']] = dict(label=ty == 'correction', type=ty,
                              topic=(parts[2] or 'other') if ty in ('correction', 'preference') else None,
                              confidence=parts[3] or 'medium', evidence=parts[4],
                              **({'fix_promised': True} if parts[5].lower() in ('yes', 'y', '1', 'true') else {}),
                              **({'promise_later': True} if parts[5].lower() == 'later' else {}))
        print(f"#{it['n']} {ty} {out[it['key']]['topic'] or ''} | {it['bot_name']} | user: {norm(it['user'])[:50]}")
    for it in items:
        out.setdefault(it['key'], dict(label=False, type='none', topic=None, confidence=None, evidence=''))
    for b in bad: print('ERROR', b)
    dump_json(out, os.path.join(work, 'labels.json'))
    n = sum(v['label'] for v in out.values())
    carried_n = '' if carry is None else f', {sum(1 for k in carry if k in out)} carried forward'
    print(f'labels.json: {len(out)} items, {n} corrections, {sum(v["type"] == "preference" for v in out.values())} preferences, '
          f'{sum(v["type"] == "keep" for v in out.values())} keep, {sum(v["type"] == "ack" for v in out.values())} ack, '
          f'{sum(bool(v.get("promise_later")) for v in out.values())} promised later{carried_n}')
    if bad: sys.exit(1)

def digest(work, lo=1, kb=10):
    """Every typed user message, one line each, with exact facts as marks (see the module help)."""
    tls = [load_json(p) for p in sorted(glob.glob(os.path.join(work, 'timelines', '*.json')))]
    sid = short_ids([tl['id'] for tl in tls]); lines = []
    for tl in tls:
        users = [e for e in tl['events'] if e['role'] == 'user' and norm(e['text'])]
        rs, first = resends(users), {}
        lines.append(f"== {tl['name']} ({len(users)} typed messages)")
        for e in users:
            t = norm(e['text']).lower(); marks = []
            if 'group' in e: marks.append(f"[group {e['group']}]")
            if e['i'] in rs: marks.append('[resend]')
            elif 'group' not in e and t in first and first[t][1] != (e.get('ts') or '')[:10]: marks.append(f'[same as {first[t][0]}]')
            if 'group' not in e: first.setdefault(t, (f"{sid[tl['id']]}:{e['i']}", (e.get('ts') or '')[:10]))
            lines.append(f"{sid[tl['id']]}:{e['i']} {e.get('ts') or '-'} {' '.join(marks) + ' ' if marks else ''}{ex(e['text'], 160, 0.8)}")
    size, n = 0, 0
    for k, ln in enumerate(lines[lo - 1:], lo):
        if n and size >= kb * 1024:
            print(f'-- lines {lo}-{k - 1} of {len(lines)}; next batch: --from {k}'); return
        print(ln); size += len(ln.encode('utf-8')) + 1; n += 1
    print(f'-- lines {lo}-{len(lines)} of {len(lines)}; that was the last batch')

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--work', required=True)
    for f in ('--all', '--auto'):   # older spellings: every reply is always exported now
        ap.add_argument(f, action='store_true', help=argparse.SUPPRESS)
    ap.add_argument('--show', nargs='+', metavar='N'); ap.add_argument('--list', action='store_true')
    ap.add_argument('--digest', action='store_true')
    ap.add_argument('--from', dest='lo', type=int, default=1); ap.add_argument('--to', dest='hi', type=int, default=10 ** 9)
    ap.add_argument('--short', action='store_true'); ap.add_argument('--width', type=int, default=220)
    ap.add_argument('--kb', type=float, help='with --list (no --to) or --digest: stop after about this many KB (default 10)')
    ap.add_argument('--label', metavar='FILE')
    a = ap.parse_args()
    if a.show: return show(a.work, a.show)
    if a.digest: return digest(a.work, a.lo, a.kb or 10)
    if a.list:
        kb = a.kb if a.kb is not None else (0 if a.hi < 10 ** 9 else 10)
        return listing(a.work, a.lo, a.hi, 100 if a.short else a.width, kb)
    if a.label: return label(a.work, a.label)
    out, per = [], []
    tls = [load_json(p) for p in sorted(glob.glob(os.path.join(a.work, 'timelines', '*.json')))]
    sid = short_ids([tl['id'] for tl in tls])
    for tl in tls:
        n0 = len(out)
        for e, prev, cards, nxt, req in pairs(tl):
            if not norm(e['text']):
                continue   # attachment only, nothing typed
            out.append(dict(n=len(out) + 1, key=f"{tl['id']}:{e['i']}", ref=f"{sid[tl['id']]}:{e['i']}", bot=tl['id'], bot_name=tl['name'],
                            ts=e['ts'], request=ex(req['text'], REQ_N, 0.7) if req and req is not e else '',
                            prev_bot=ex(prev['text'], PREV_N, 0.35) + card_text(cards), user=ex(e['text'], USER_N, 0.7),
                            next_bot=ex('\n'.join(nxt), NEXT_N, 0.4) if nxt else ''))
        per.append(f"{tl['name']}: {len(out) - n0} items")
    by_key, n_check = {x['key']: x for x in out}, 0
    for tl in tls:
        for i, why in checks(tl).items():
            key = f"{tl['id']}:{i}"; n_check += 1
            if key in by_key:
                by_key[key]['check'] = ', '.join(why); continue
            e = next(x for x in tl['events'] if x['i'] == i); prev, nxt = around(tl, i)
            out.append(dict(n=len(out) + 1, key=key, ref=f"{sid[tl['id']]}:{i}", bot=tl['id'], bot_name=tl['name'], ts=e['ts'], request='',
                            prev_bot=ex(prev, PREV_N, 0.35), user=ex(e['text'], USER_N, 0.7),
                            next_bot=ex('\n'.join(nxt), NEXT_N, 0.4) if nxt else '', check=', '.join(why)))
    dump_json(out, os.path.join(a.work, 'judge_inputs.json'))
    print('\n'.join(per))
    print(f'{n_check} items marked "check" (last messages, exact repeats); new ones are at the end of the list')
    print(f'{len(out)} items -> {os.path.join(a.work, "judge_inputs.json")}' + ('' if out else '  (none: labels.json is {})'))

if __name__ == '__main__':
    main()
