#!/usr/bin/env python3
"""Bot Audit, step 2: pick user messages that might be corrections and export judge inputs.

  python3 judge_inputs.py --work W
      W/timelines/*.json -> W/judge_inputs.json
      Each item: {key, bot, bot_name, ts, prev_bot, user, next_bot, signal}
      The host bot then judges every item with references/rubric_correction.md and writes
      W/labels.json = {key: {label, type, topic, confidence, evidence}}.

The filter is wide on purpose (recall over precision); the rubric decides. Cue words are English plus
W/cues.json for other chat languages (references/cues.md). Without cues.json, every reply in a mostly
non-Latin script is kept as a candidate, so nothing is missed in languages the English cues can't see.
"""
import argparse, glob, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import dump_json, load_cues, load_json, mostly_non_latin, norm

def ex(t, n):
    t = norm(t)
    return t if len(t) <= n else t[:n] + '…'

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--work', required=True)
    a = ap.parse_args()
    cues, custom = load_cues(a.work); DIRECTIVE = cues['directive']
    out = []; fallback = 0
    for p in sorted(glob.glob(os.path.join(a.work, 'timelines', '*.json'))):
        tl = load_json(p); ev = [e for e in tl['events'] if e['role'] in ('user', 'bot')]
        for k, e in enumerate(ev):
            if e['role'] != 'user' or k == 0 or ev[k - 1]['role'] != 'bot':
                continue
            q = e['text']; first = norm(q.splitlines()[0] if q else '')
            pasted = (len(q) > 300 or len(re.findall(r'^\s*\d+\.', q, re.M)) >= 3) and not DIRECTIVE.search(first[:80])
            m = DIRECTIVE.search(q[:400])
            signal = m.group(0) if m else None
            if not m and not custom and mostly_non_latin(q[:400]) and not pasted:
                signal = '(non-Latin script, no cues.json)'; fallback += 1
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
    if fallback:
        print(f'NOTE: {fallback} candidates were kept only because they are in a non-Latin script. Write cues.json '
              f'(references/cues.md) for the chat languages to get a tighter list, then run this again.')

if __name__ == '__main__':
    main()
