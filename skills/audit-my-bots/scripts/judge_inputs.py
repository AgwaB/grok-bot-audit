#!/usr/bin/env python3
r"""Bot Audit, step 3: pick user messages that might be corrections, export judge inputs, record labels.

  python3 judge_inputs.py --work W [--auto | --all | --all-for BOT [BOT ...]]
      W/timelines/*.json -> W/judge_inputs.json. Each item: {n, key, bot, bot_name, ts, request, prev_bot, user,
      next_bot, signal}. "n" is a short number for the item; "request" is the user's message that started the exchange;
      prev_bot ends with the app's question cards the bot showed (e.g. a choice the user skipped).
      Without --all, a bot's replies are filtered by cue phrases (minimal English fallback + W/cues.json). --all exports
      every reply after a bot message for all bots; --all-for does it for the named bots (id or name) only. A bot whose
      replies match no cue at all gets all its replies exported anyway. --auto picks per bot: every reply unless at
      least 8 in 10 of the bot's typed user messages are written mostly in Latin letters (the only messages the
      built-in English cues can match). Each bot's line prints that share and the recommended mode.
  python3 judge_inputs.py --work W --list [--from N] [--to M]
      Compact view: one block per item with short excerpts, numbered, for reading in batches of about 50. A bot
      message already shown as the previous item's "next>" is not repeated.
  python3 judge_inputs.py --work W --show N|KEY [...]
      The full messages around these items.
  python3 judge_inputs.py --work W --label FILE
      FILE: one line per correction or preference (nothing else needs a line), 7 tab-separated columns:
        n  type  topic  confidence  evidence  promised  user_start
      n = item number (or key); type = correction | preference | topic_rejection | new_request | question |
      clarification | other; topic = short snake_case cause for corrections and preferences; confidence = high |
      medium | low; evidence = a few words copied from the user message (never a secret); promised = yes if the bot's
      reply promises a lasting change ("from now on I'll..."), else empty; user_start = the first few characters of the
      user message, checked against the item (a mismatch is an error: guards against off-by-one). Empty cell: \N or -.
      Each line is echoed with the item's user text. Lines may be added over several batches; each run rewrites
      W/labels.json from the whole file; items without a line are type "none" (not a correction).
      No candidates at all -> labels.json is {}.

The filter is wide on purpose (recall over precision); the rubric decides. Excerpts keep the start and the end of
long messages (admissions such as "you're right, I missed…" often come at the end of a reply). App notices
(attachments) and file paths are already removed from user messages by sessions.py parse.
"""
import argparse, glob, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import dump_json, load_cues, load_json, norm

PREV_N, USER_N, NEXT_N, REQ_N = 800, 1000, 900, 300
TYPES = ('correction', 'topic_rejection', 'new_request', 'question', 'clarification', 'preference', 'other', 'none')
EMPTY = ('', '\\N', '-')

def latin_share(texts):
    """Share of messages written mostly in Latin letters (a script measure, not a language rule)."""
    n = hit = 0
    for t in texts:
        letters = [c for c in t if c.isalpha()]
        if not letters: continue
        n += 1
        hit += sum(1 for c in letters if c.isascii() or '\u00c0' <= c <= '\u024f') / len(letters) >= 0.5
    return hit, n

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

def card_text(cards):
    return ''.join(f'\n[question card: {c}]' for c in cards)

def load_items(work):
    return load_json(os.path.join(work, 'judge_inputs.json'), [])

def find(items, ref):
    return next((x for x in items if str(x.get('n')) == str(ref) or x['key'] == ref), None)

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

def listing(work, lo, hi):
    prev = None
    for x in load_items(work):
        if lo <= x['n'] <= hi:
            same = prev and prev['bot'] == x['bot'] and prev['next_bot'] and norm(prev['next_bot'])[:120] == norm(x['prev_bot'])[:120]
            bot = f"(= next> of #{prev['n']})" if same else ex(x['prev_bot'], 220, 0.3)
            print(f"#{x['n']} {x['bot_name']} {x['ts']}\n  bot> {bot}\n  user> {ex(x['user'], 400, 0.7)}\n"
                  f"  next> {ex(x['next_bot'], 220, 0.3) or '(no reply)'}")
        prev = x

def label(work, path):
    items = load_items(work); out, bad = {}, []
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
        if it['key'] in out: bad.append(f'line {ln}: item {parts[0]} labelled twice (the later line wins)')
        out[it['key']] = dict(label=ty == 'correction', type=ty,
                              topic=(parts[2] or 'other') if ty in ('correction', 'preference') else None,
                              confidence=parts[3] or 'medium', evidence=parts[4],
                              **({'fix_promised': True} if parts[5].lower() in ('yes', 'y', '1', 'true') else {}))
        print(f"#{it['n']} {ty} {out[it['key']]['topic'] or ''} | {it['bot_name']} | user: {norm(it['user'])[:50]}")
    for it in items:
        out.setdefault(it['key'], dict(label=False, type='none', topic=None, confidence=None, evidence=''))
    for b in bad: print('ERROR', b)
    dump_json(out, os.path.join(work, 'labels.json'))
    n = sum(v['label'] for v in out.values())
    print(f'labels.json: {len(out)} items, {n} corrections, {sum(v["type"] == "preference" for v in out.values())} preferences')
    if bad: sys.exit(1)

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--work', required=True)
    ap.add_argument('--all', action='store_true', help='export every reply after a bot message (no cue filter)')
    ap.add_argument('--auto', action='store_true', help='per bot: every reply unless 8 in 10 user messages are mostly Latin script')
    ap.add_argument('--all-for', nargs='+', metavar='BOT', default=[], help='like --all, for these bots (id or name)')
    ap.add_argument('--show', nargs='+', metavar='N'); ap.add_argument('--list', action='store_true')
    ap.add_argument('--from', dest='lo', type=int, default=1); ap.add_argument('--to', dest='hi', type=int, default=10 ** 9)
    ap.add_argument('--label', metavar='FILE')
    a = ap.parse_args()
    if a.show: return show(a.work, a.show)
    if a.list: return listing(a.work, a.lo, a.hi)
    if a.label: return label(a.work, a.label)
    cues, _ = load_cues(a.work); DIRECTIVE = cues['directive']
    out, per = [], []
    for p in sorted(glob.glob(os.path.join(a.work, 'timelines', '*.json'))):
        tl = load_json(p)
        hit, n_typed = latin_share([e['text'] for e in tl['events'] if e['role'] == 'user' and norm(e['text'])])
        share = hit / n_typed if n_typed else 1.0
        rec = 'cues' if share >= 0.8 else 'all'
        every = a.all or tl['id'] in a.all_for or tl['name'] in a.all_for or (a.auto and rec == 'all')
        rows = []
        for e, prev, cards, nxt, req in pairs(tl):
            q = e['text']
            if not norm(q):
                continue   # attachment only, nothing typed
            first = norm(q.splitlines()[0])
            pasted = (len(q) > 300 or len(re.findall(r'^\s*\d+\.', q, re.M)) >= 3) and not DIRECTIVE.search(q)
            m = DIRECTIVE.search(q[:400])
            rows.append((m.group(0) if m else None, pasted, e, prev, cards, nxt, req))
        cued = [r for r in rows if r[0] and not r[1]]
        mode = 'all' if every else 'cues' if cued else 'all (no cue matched)'
        for sig, pasted, e, prev, cards, nxt, req in (cued if mode == 'cues' else rows):
            out.append(dict(n=len(out) + 1, key=f"{tl['id']}:{e['i']}", bot=tl['id'], bot_name=tl['name'], ts=e['ts'],
                            request=ex(req['text'], REQ_N, 0.7) if req and req is not e else '',
                            prev_bot=ex(prev['text'], PREV_N, 0.35) + card_text(cards), user=ex(e['text'], USER_N, 0.7),
                            next_bot=ex('\n'.join(nxt), NEXT_N, 0.4) if nxt else '', signal=sig or '(all replies)',
                            **({'pasted': True} if pasted else {})))
        per.append(f"{tl['name']}: {len(cued) if mode == 'cues' else len(rows)} items ({mode}); user messages the English cues"
                   f" can read: {round(100 * share)}% ({hit}/{n_typed}) -> recommended: {rec}")
    dump_json(out, os.path.join(a.work, 'judge_inputs.json'))
    print('\n'.join(per))
    print(f'{len(out)} candidates -> {os.path.join(a.work, "judge_inputs.json")}' + ('' if out else '  (none: labels.json is {})'))

if __name__ == '__main__':
    main()
