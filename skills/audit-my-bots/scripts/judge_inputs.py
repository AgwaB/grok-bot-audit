#!/usr/bin/env python3
"""Bot Audit, step 2: pick user messages that might be corrections and export judge inputs.

  python3 judge_inputs.py --work W
      W/timelines/*.json -> W/judge_inputs.json
      Each item: {key, bot, bot_name, ts, prev_bot, user, next_bot, signal}
      The host bot then judges every item with references/rubric_correction.md and writes
      W/labels.json = {key: {label, type, topic, confidence, evidence}}.

The filter is wide on purpose (recall over precision); the rubric decides.
"""
import argparse, glob, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import dump_json, load_json, norm

DIRECTIVE_KO = (r'말고|빼|하지\s*마|앞으로|^아니|아니\s|로\s*하자|로\s*가자|별로|안\s*맞|안맞|너무|이미|기본이야|틀|아닌|금지|쓰지|'
                r'없애|바꿔|고쳐|대신|줄여|안\s*써|싫|넘어야|아니야|아님|각색|쉽게|축약|쪽으로|거였어|건데\?|인데\?|맞아\?|'
                r'안\s*한\s*거|된다면서|끝인가|아니지\s*않|그니까|^ㄴㄴ|다른\s*걸로|다시')
DIRECTIVE_EN = (r"\bno\b|\bnot (that|this|what)\b|\binstead\b|\bdon'?t\b|\bdo not\b|\bstop\b|\bwrong\b|\bisn'?t\b|"
                r"\bthat'?s not\b|\bi meant\b|\bi asked\b|\btoo (long|short|much|many|formal|casual|complex|vague)\b|"
                r"\balready\b|\bshorter\b|\bsimpler\b|\bwhy didn'?t\b|\byou said\b|\bactually\b|\bagain\b|\bfrom now on\b|"
                r"\bplease (fix|change|remove)\b|\bremove\b|\bis that (all|right|correct)\b|\bare you sure\b")
DIRECTIVE = re.compile(f'({DIRECTIVE_KO}|{DIRECTIVE_EN})', re.I | re.M)

def ex(t, n):
    t = norm(t)
    return t if len(t) <= n else t[:n] + '…'

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--work', required=True)
    a = ap.parse_args()
    out = []
    for p in sorted(glob.glob(os.path.join(a.work, 'timelines', '*.json'))):
        tl = load_json(p); ev = [e for e in tl['events'] if e['role'] in ('user', 'bot')]
        for k, e in enumerate(ev):
            if e['role'] != 'user' or k == 0 or ev[k - 1]['role'] != 'bot':
                continue
            q = e['text']; first = norm(q.splitlines()[0] if q else '')
            pasted = (len(q) > 300 or len(re.findall(r'^\s*\d+\.', q, re.M)) >= 3) and not DIRECTIVE.search(first[:80])
            m = DIRECTIVE.search(q[:400])
            if not m or pasted:
                continue
            nxt = []
            for f in ev[k + 1:]:
                if f['role'] == 'user': break
                nxt.append(f['text'])
            out.append(dict(key=f"{tl['id']}:{e['i']}", bot=tl['id'], bot_name=tl['name'], ts=e['ts'],
                            prev_bot=ex(ev[k - 1]['text'], 260), user=ex(q, 300),
                            next_bot=ex(max(nxt, key=len), 260) if nxt else '', signal=m.group(0)))
    dump_json(out, os.path.join(a.work, 'judge_inputs.json'))
    print(f'{len(out)} candidates -> {os.path.join(a.work, "judge_inputs.json")}')

if __name__ == '__main__':
    main()
