#!/usr/bin/env python3
"""Bot Audit, step 3: usage, repeated corrections, suggested status, and extra checks for every bot.

  python3 diagnostics.py --work W [--now "YYYY-MM-DD HH:MM"]   (default: now, or "now" in W/replay.json)
      Reads W/bots.json, W/timelines/*.json, W/labels.json (from the judge step) -> W/diag.json

Everything is computed from data inside Grok Bot (saved transcript pages, profile name/description,
the memory block the app injects). Rules and thresholds: references/criteria.md.
Fields marked "candidates" are leads for the host bot to read and confirm, not findings.
"""
import argparse, collections, datetime as dt, glob, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import dump_json, grams, jaccard, load_cues, load_json, norm

FMT = '%Y-%m-%d %H:%M'
P = lambda s: dt.datetime.strptime(s, FMT)
INCIDENT_MIN = 60
WAIT_H = 6
FIX_MAX = 6

def days_between(a, b):
    return (b - a).total_seconds() / 86400

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--work', required=True); ap.add_argument('--now')
    a = ap.parse_args()
    cues, _ = load_cues(a.work); FIX, PROMISE, NUDGE, TIMELY = cues['fix'], cues['promise'], cues['nudge'], cues['timely']
    bots = {b['id']: b for b in load_json(os.path.join(a.work, 'bots.json'), [])}
    labels = load_json(os.path.join(a.work, 'labels.json'), {})
    jin = {x['key']: x for x in load_json(os.path.join(a.work, 'judge_inputs.json'), [])}
    tls = {}
    for p in sorted(glob.glob(os.path.join(a.work, 'timelines', '*.json'))):
        tl = load_json(p); tls[tl['id']] = tl
    if not tls:
        sys.exit('no timelines; run sessions.py parse first')
    all_ts = [e['ts'] for tl in tls.values() for e in tl['events'] if e.get('ts')]
    a.now = a.now or (load_json(os.path.join(a.work, 'replay.json'), {}) or {}).get('now')   # replay tests pin "now"
    if a.now:
        now = P(a.now)
    else:
        off = collections.Counter(tl.get('utc_offset_hours', 0) for tl in tls.values()).most_common(1)[0][0]
        now = dt.datetime.now(dt.timezone(dt.timedelta(hours=off))).replace(tzinfo=None, second=0, microsecond=0)
    total_real = sum(sum(1 for e in tl['events'] if e['role'] == 'user') for tl in tls.values())
    out = dict(now=now.strftime(FMT), total_real_requests=total_real, bots={}, fleet={})
    waits_all = []
    for bid, tl in tls.items():
        ev = tl['events']; users = [e for e in ev if e['role'] == 'user' and e.get('ts')]
        stamps = [P(e['ts']) for e in ev if e.get('ts')]
        first = min(stamps) if stamps else now
        last_user = P(users[-1]['ts']) if users else None
        age = days_between(first, now); idle = days_between(last_user, now) if last_user else age
        # ---- corrections -> incidents -> groups
        cors = sorted(((jin[k]['ts'], k, v) for k, v in labels.items()
                       if k.startswith(bid + ':') and v.get('label') and k in jin), key=lambda x: x[0] or '')
        incidents = []
        for ts, k, v in cors:
            if incidents and incidents[-1]['topic'] == v.get('topic') and ts and incidents[-1]['last'] and \
                    (P(ts) - P(incidents[-1]['last'])).total_seconds() <= INCIDENT_MIN * 60:
                incidents[-1]['keys'].append(k); incidents[-1]['last'] = ts; continue
            incidents.append(dict(topic=v.get('topic') or 'other', first=ts, last=ts, keys=[k], confidence=v.get('confidence', 'medium')))
        fixes = [dict(ts=e['ts'], kind='memory_write' if e.get('kind') == 'memory_write' else 'bot_said',
                      text=norm(e['text'])[:200]) for e in ev
                 if e.get('ts') and ((e['role'] == 'bot' and FIX.search(e['text'] or '')) or e.get('kind') == 'memory_write')]
        groups = {}
        for inc in incidents:
            g = groups.setdefault(inc['topic'], dict(incidents=0, days=set(), keys=[], first=inc['first'], last=None, confidences=[]))
            g['incidents'] += 1; g['days'].add((inc['first'] or '')[:10]); g['keys'] += inc['keys']
            g['last'] = inc['last']; g['confidences'].append(inc['confidence'])
        n_real = max(1, len(users))
        for topic, g in groups.items():
            g['days'] = sorted(d for d in g['days'] if d)
            g['rate'] = round(g['incidents'] / n_real, 3)
            g['repeated'] = (g['incidents'] >= 2 and len(g['days']) >= 2) or g['incidents'] >= 3
            # Fix candidates: memory saves and announced fixes in the same bot after the group's first incident.
            # Whether one is about this group's problem can't be told from words (memory and chats may be in different
            # languages), so they are candidates only: they change neither status nor impact until the host bot confirms.
            g['fix_candidates_between'] = [f for f in fixes if g['first'] and g['last'] and g['first'] <= f['ts'] < g['last']][-FIX_MAX:]
            g['fix_candidates_after_last'] = [f for f in fixes if g['last'] and f['ts'] >= g['last']][:FIX_MAX]
            g['strong'] = g['repeated'] and (g['incidents'] >= 3 or g['rate'] >= 0.05) and any(c != 'low' for c in g['confidences'])
        prefs = [k for k, v in labels.items() if k.startswith(bid + ':') and v.get('type') == 'preference']
        # ---- waits: user message(s) with no bot reply for >= WAIT_H hours (lower bound from the next timestamp)
        waits = []; k = 0; seq = [e for e in ev if e['role'] in ('user', 'bot')]
        while k < len(seq):
            if seq[k]['role'] != 'user' or not seq[k].get('ts'):
                k += 1; continue
            j = k
            while j + 1 < len(seq) and seq[j + 1]['role'] == 'user': j += 1
            nxt_bot = seq[j + 1] if j + 1 < len(seq) else None
            t0 = P(seq[k]['ts'])
            if nxt_bot is None:
                until, hours = None, days_between(t0, now) * 24
            else:
                last_seen = max(P(x['ts']) for x in seq[k:j + 2] if x.get('ts'))
                until, hours = last_seen.strftime(FMT), (last_seen - t0).total_seconds() / 3600
            if hours >= WAIT_H:
                w = dict(bot=bid, first=seq[k]['ts'], until=until, hours_at_least=round(hours, 1), messages=j - k + 1,
                         texts=[norm(x['text'])[:80] for x in seq[k:j + 1]][:3], answered=nxt_bot is not None)
                waits.append(w); waits_all.append(w)
            k = j + 1
        # ---- skipped choice questions
        skips = [e for e in ev if e.get('kind') == 'skipped_question']
        # ---- promises followed by a nudge
        promises = []
        for k2, e in enumerate(seq):
            if e['role'] == 'bot' and len(e['text']) < 240 and PROMISE.search(e['text']) and k2 + 1 < len(seq) \
                    and seq[k2 + 1]['role'] == 'user' and NUDGE.search(norm(seq[k2 + 1]['text'])) and len(norm(seq[k2 + 1]['text'])) <= 20:
                promises.append(dict(ts=e['ts'], bot=norm(e['text'])[:120], next_user=norm(seq[k2 + 1]['text'])[:40]))
        # ---- memory block
        mem = None
        if tl.get('memory'):
            txt = tl['memory']['text']
            facts = [dict(learned=d, text=t.strip()) for d, t in re.findall(r'^- \(learned (\d{4}-\d\d-\d\d)\)\s*(.+)$', txt, re.M)]
            for f in facts:
                f['time_sensitive'] = bool(TIMELY.search(f['text'])) and days_between(P(f['learned'] + ' 00:00'), now) >= 3
            dups = [(f1['text'][:100], f2['text'][:100]) for i, f1 in enumerate(facts) for f2 in facts[i + 1:]
                    if jaccard(grams(f1['text']), grams(f2['text'])) >= 0.45]
            mem = dict(shown_facts=len(facts), not_shown=sum(int(n) for n in re.findall(r'\((\d+) more', txt)),
                       time_sensitive=[f for f in facts if f['time_sensitive']], near_duplicates=dups, facts=facts)
        # ---- repeated requests across days (routine candidates)
        items = [(e['ts'][:10], grams(e['text']), norm(e['text'])[:80]) for e in users if len(norm(e['text'])) >= 6]
        rep, seen = [], set()
        for d0, g0, t0 in items:
            sim = [(d, t) for d, g, t in items if jaccard(g0, g) >= 0.3]
            dset = sorted({d for d, _ in sim})
            if len(dset) >= 3 and t0 not in seen:
                seen.update(t for _, t in sim)
                rep.append(dict(days=dset, examples=sorted({t for _, t in sim})[:4]))
        rep.sort(key=lambda r: -len(r['days']))
        b = bots.get(bid, dict(name=tl['name'], description=''))
        out['bots'][bid] = dict(
            name=b['name'], description=b.get('description', ''), description_empty=not b.get('description'),
            first_seen=first.strftime(FMT), last_request=last_user.strftime(FMT) if last_user else None,
            real_requests=len(users), share=round(len(users) / max(1, total_real), 3),
            active_days=len({e['ts'][:10] for e in users}), age_days=round(age, 1), idle_days=round(idle, 1),
            coverage=tl.get('coverage'), corrections=len(cors), incidents=incidents, groups=groups, preferences=prefs,
            fix_events=fixes, waits=waits, skipped_questions=dict(count=len(skips), questions=[s['text'][:120] for s in skips][:10]),
            promise_candidates=promises, memory=mem, repeated_requests=rep[:5],
            routines_seen=sum(1 for e in ev if e.get('kind') == 'routine'))
    # ---- fleet: outage windows (waits overlapping in >= 2 bots)
    def span(w):
        s = P(w['first']); e = P(w['until']) if w['until'] else now
        return s, e
    outages = []
    for w in waits_all:
        s, e = span(w)
        others = [x for x in waits_all if x['bot'] != w['bot'] and span(x)[0] < e and span(x)[1] > s]
        if others:
            w['fleet_outage'] = True
    for w in waits_all:
        w.setdefault('fleet_outage', False)
    if any(w['fleet_outage'] for w in waits_all):
        ow = [w for w in waits_all if w['fleet_outage']]
        outages.append(dict(start=min(w['first'] for w in ow), bots=sorted({w['bot'] for w in ow}), waits=ow))
    out['fleet']['outages'] = outages
    # ---- fleet: similar requests in different bots (candidates)
    keys = [(bid, e['ts'], grams(e['text']), norm(e['text'])[:80]) for bid, tl in tls.items()
            for e in tl['events'] if e['role'] == 'user' and len(norm(e['text'])) >= 12 and e.get('ts')]
    pairs = []
    for i, x in enumerate(keys):
        for y in keys[i + 1:]:
            if x[0] != y[0] and jaccard(x[2], y[2]) >= 0.35:
                pairs.append(dict(a=x[0], a_ts=x[1], a_text=x[3], b=y[0], b_ts=y[1], b_text=y[3]))
    out['fleet']['similar_requests_candidates'] = pairs[:30]
    # ---- fleet: requests that look like another bot's job (needs descriptions; candidates)
    desc = {bid: grams(bots[bid]['name'] + ' ' + bots[bid]['description']) for bid in tls if bid in bots and bots[bid].get('description')}
    other = []
    for bid, tl in tls.items():
        if bid not in desc: continue
        for e in tl['events']:
            if e['role'] != 'user' or len(norm(e['text'])) < 8: continue
            g = grams(e['text']); own = jaccard(g, desc[bid])
            best = max(((jaccard(g, dg), ob) for ob, dg in desc.items() if ob != bid), default=(0, None))
            if best[1] and best[0] >= 0.12 and best[0] > own + 0.05 and e['ts'] >= out['bots'][best[1]]['first_seen']:
                other.append(dict(bot=bid, looks_like=best[1], ts=e['ts'], text=norm(e['text'])[:80]))
    out['fleet']['other_bots_job_candidates'] = other[:40]
    # ---- suggested status (references/criteria.md §2); the host bot may override with a stated reason
    for bid, b in out['bots'].items():
        reasons = []
        if b['age_days'] >= 3 and b['idle_days'] >= max(3, b['age_days'] / 2) and b['share'] < 0.05:
            st = 'red'; reasons.append('barely used: idle {idle_days} of {age_days} days, under 5% of use'.format(**b))
        else:
            strong = [t for t, g in b['groups'].items() if g['strong']]
            own_waits = [w for w in b['waits'] if not w['fleet_outage']]
            if strong: reasons.append('repeated corrections not fixed: ' + ', '.join(strong))
            if own_waits: reasons.append(f'{len(own_waits)} unanswered request(s) not explained by a fleet outage')
            st = 'yellow' if reasons else 'green'
            if not reasons: reasons.append('no strong repeated problem')
        b['status_suggested'] = st; b['status_reasons'] = reasons
    dump_json(out, os.path.join(a.work, 'diag.json'))
    for bid, b in out['bots'].items():
        print(f"{b['name']}: {b['status_suggested']} ({'; '.join(b['status_reasons'])})")
    print('->', os.path.join(a.work, 'diag.json'))

if __name__ == '__main__':
    main()
