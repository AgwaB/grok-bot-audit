#!/usr/bin/env python3
"""Bot Audit, step 2: pick user messages that might be corrections and export judge inputs.

  python3 judge_inputs.py --work W
      W/timelines/*.json -> W/judge_inputs.json
      Each item: {key, bot, bot_name, ts, prev_bot, user, next_bot, signal}
      The host bot then judges every item with references/rubric_correction.md and writes
      W/labels.json = {key: {label, type, topic, confidence, evidence}}.

The filter is wide on purpose (recall over precision); the rubric decides. Cue phrases: a minimal English
fallback plus W/cues.json (references/cues.md). --all skips the cue filter and exports every reply that follows
a bot message, for chats in languages without cues; the host bot then judges them all.
"""
import argparse, glob, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import dump_json, load_cues, load_json, norm

def ex(t, n):
    t = norm(t)
    return t if len(t) <= n else t[:n] + '…'

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--work', required=True)
    ap.add_argument('--all', action='store_true', help='export every reply after a bot message (no cue filter)')
    a = ap.parse_args()
    cues, _ = load_cues(a.work); DIRECTIVE = cues['directive']
    out = []
    for p in sorted(glob.glob(os.path.join(a.work, 'timelines', '*.json'))):
        tl = load_json(p); ev = [e for e in tl['events'] if e['role'] in ('user', 'bot')]
        for k, e in enumerate(ev):
            if e['role'] != 'user' or k == 0 or ev[k - 1]['role'] != 'bot':
                continue
            q = e['text']; first = norm(q.splitlines()[0] if q else '')
            pasted = (len(q) > 300 or len(re.findall(r'^\s*\d+\.', q, re.M)) >= 3) and not DIRECTIVE.search(first[:80])
            m = DIRECTIVE.search(q[:400])
            signal = m.group(0) if m else ('(all replies)' if a.all else None)
            if not signal or pasted:
                continue
            nxt = []
            for f in ev[k + 1:]:
                if f['role'] == 'user': break
                nxt.append(f['text'])
            out.append(dict(key=f"{tl['id']}:{e['i']}", bot=tl['id'], bot_name=tl['name'], ts=e['ts'],
                            prev_bot=ex(ev[k - 1]['text'], 260), user=ex(q, 300),
                            next_bot=ex(max(nxt, key=len), 260) if nxt else '', signal=signal))
    dump_json(out, os.path.join(a.work, 'judge_inputs.json'))
    print(f'{len(out)} candidates -> {os.path.join(a.work, "judge_inputs.json")}')

if __name__ == '__main__':
    main()
