#!/usr/bin/env python3
"""Bot Audit, step 2: pick user messages that might be corrections and export judge inputs.

  python3 judge_inputs.py --work W [--all]
      W/timelines/*.json -> W/judge_inputs.json
      Each item: {key, bot, bot_name, ts, prev_bot, user, next_bot, signal}
      The host bot then judges every item with references/rubric_correction.md and writes
      W/labels.json = {key: {label, type, topic, confidence, evidence}}.
  python3 judge_inputs.py --work W --show KEY [KEY ...]
      Prints the full bot message before, the user message, and the full bot reply after, for when an excerpt
      is not enough to judge.

The filter is wide on purpose (recall over precision); the rubric decides. Cue phrases: a minimal English
fallback plus W/cues.json (references/cues.md). --all skips the cue filter and exports every reply that follows
a bot message; use it whenever the chats are not mostly in English. Excerpts keep the start and the end of long
messages (admissions such as "you're right, I missed…" often come at the end of a reply).
App notices (attachments) and file paths are already removed from user messages by sessions.py parse.
"""
import argparse, glob, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import dump_json, load_cues, load_json, norm

PREV_N, USER_N, NEXT_N = 800, 1000, 900

def ex(t, n, head=0.5):
    """Excerpt: the whole text if short, else its start and its end joined by ' … '."""
    t = norm(t)
    if len(t) <= n:
        return t
    h = int(n * head)
    return t[:h].rstrip() + ' … ' + t[-(n - h):].lstrip()

def pairs(tl):
    """(index in ev, user event, previous bot event, bot replies until the next user message)."""
    ev = [e for e in tl['events'] if e['role'] in ('user', 'bot')]
    for k, e in enumerate(ev):
        if e['role'] != 'user' or k == 0 or ev[k - 1]['role'] != 'bot':
            continue
        nxt = []
        for f in ev[k + 1:]:
            if f['role'] == 'user': break
            nxt.append(f['text'])
        yield e, ev[k - 1], nxt

def show(work, keys):
    tls = {os.path.basename(p)[:-5]: load_json(p) for p in glob.glob(os.path.join(work, 'timelines', '*.json'))}
    for key in keys:
        bid, _, i = key.partition(':')
        tl = tls.get(bid)
        hit = next(((e, p, n) for e, p, n in pairs(tl) if str(e['i']) == i), None) if tl else None
        if not hit:
            print(f'== {key}: not found'); continue
        e, p, n = hit
        print(f'== {key} ({tl["name"]}, {e["ts"]})\n-- bot before:\n{p["text"]}\n-- user:\n{e["text"]}\n-- bot after:\n'
              + ('\n\n'.join(n) or '(no reply)') + '\n')

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--work', required=True)
    ap.add_argument('--all', action='store_true', help='export every reply after a bot message (no cue filter)')
    ap.add_argument('--show', nargs='+', metavar='KEY', help='print the full messages around these keys')
    a = ap.parse_args()
    if a.show:
        return show(a.work, a.show)
    cues, _ = load_cues(a.work); DIRECTIVE = cues['directive']
    out = []
    for p in sorted(glob.glob(os.path.join(a.work, 'timelines', '*.json'))):
        tl = load_json(p)
        for e, prev, nxt in pairs(tl):
            q = e['text']
            if not norm(q):
                continue   # attachment only, nothing typed
            first = norm(q.splitlines()[0])
            pasted = (len(q) > 300 or len(re.findall(r'^\s*\d+\.', q, re.M)) >= 3) and not DIRECTIVE.search(first[:80])
            m = DIRECTIVE.search(q[:400])
            signal = m.group(0) if m else ('(all replies)' if a.all else None)
            if not signal or (pasted and not a.all):
                continue
            out.append(dict(key=f"{tl['id']}:{e['i']}", bot=tl['id'], bot_name=tl['name'], ts=e['ts'],
                            prev_bot=ex(prev['text'], PREV_N, 0.35), user=ex(q, USER_N, 0.7),
                            next_bot=ex('\n'.join(nxt), NEXT_N, 0.4) if nxt else '', signal=signal,
                            **({'pasted': True} if pasted else {})))
    dump_json(out, os.path.join(a.work, 'judge_inputs.json'))
    print(f'{len(out)} candidates -> {os.path.join(a.work, "judge_inputs.json")}'
          + ('' if a.all else '  (cue filter: English fallback' + (' + cues.json)' if os.path.exists(os.path.join(a.work, 'cues.json')) else ')')))

if __name__ == '__main__':
    main()
