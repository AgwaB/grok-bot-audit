#!/usr/bin/env python3
"""Bot Audit, step 5: facts about every bot, for you to judge.

  python3 diagnostics.py --work W [--now "YYYY-MM-DD HH:MM"]   (default: now, or "now" in W/replay.json)
      Reads W/bots.json, W/timelines/*.json, W/labels.json (from the judge step) -> W/diag.json

Only facts: counts, dates, gaps, exact repeats, routine run statistics, and the corrections, keep statements and
promises you labelled, grouped and counted. Nothing here decides a status or whether something is a problem: you do
(references/criteria.md). Every message is named by its id ("ref", "<bot prefix>:<i>") so findings can cite it.
"""
import argparse, collections, datetime as dt, glob, os, re, sys, unicodedata
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import FMT, P, PATH_RE, RESEND_MIN, dump_json, grams, load_json, norm, short_ids

INCIDENT_MIN = 60   # corrections on the same topic in the same bot within this many minutes are one incident
WAIT_H = 6          # a gap this long before the bot's reply is listed as a wait
FIX_MAX = 12
SESSION_GAP_H = 6   # messages further apart than this are separate sessions (occasions)
RELAY_DAYS = 3
BURST_MIN = 15      # bot-to-bot messages mostly this close together are one fan-out run
RUN_N = 3           # this many user messages in a row with no reply between them are listed
# Sites with a plugin in the app (Connect apps). Matched on the host name only.
SERVICES = {'mail.google.com': 'Gmail', 'gmail.com': 'Gmail', 'calendar.google.com': 'Google Calendar',
            'drive.google.com': 'Google Drive', 'docs.google.com': 'Google Drive', 'slack.com': 'Slack', 'notion.so': 'Notion',
            'notion.site': 'Notion', 'outlook.office.com': 'Outlook', 'outlook.live.com': 'Outlook', 'onedrive.live.com': 'OneDrive',
            'sharepoint.com': 'SharePoint', 'github.com': 'GitHub', 'linear.app': 'Linear'}
DATE_RE = re.compile(r'\b(20\d\d)[-/.](\d{1,2})[-/.](\d{1,2})\b')


def service_of(host):
    return next((v for k, v in SERVICES.items() if host == k or host.endswith('.' + k)), None)

def median(xs):
    xs = sorted(xs); n = len(xs)
    return None if not n else xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2

def past_dates(text, now):
    """Explicit dates in a text that are already past (any language: digits only)."""
    out = []
    for y, m, d in DATE_RE.findall(text or ''):
        try:
            if dt.datetime(int(y), int(m), int(d)) < now - dt.timedelta(days=1): out.append(f'{y}-{int(m):02d}-{int(d):02d}')
        except ValueError:
            pass
    return out

def days_between(a, b):
    return (b - a).total_seconds() / 86400

def session_days(stamps):
    """{timestamp string: date string of the session it belongs to}. A session runs on while messages come less than
    SESSION_GAP_H apart, so late-night work past midnight counts as one day of use, not two."""
    out, start, prev = {}, None, None
    for t in sorted(set(stamps)):
        x = P(t)
        if prev is None or (x - prev).total_seconds() > SESSION_GAP_H * 3600: start = t[:10]
        out[t] = start; prev = x
    return out

CODE_RE = re.compile(r'```.*?```|`[^`\n]*`|https?://\S+', re.S)
def main_script(text):
    """The writing system a message is mostly in (Hangul, Japanese, Han, Latin, Cyrillic, ...), or None if it has too
    few letters. Code, links and paths are ignored; Hangul or kana count even when mixed with code words."""
    t = PATH_RE.sub(' ', CODE_RE.sub(' ', text or ''))
    c = collections.Counter()
    for ch in t:
        if ch.isalpha():
            n = unicodedata.name(ch, '').split(' ')[0]
            c['Japanese' if n in ('HIRAGANA', 'KATAKANA') else 'Han' if n == 'CJK' else n.title()] += 1
    tot = sum(c.values())
    if tot < 4: return None
    if c['Hangul'] >= 0.15 * tot: return 'Hangul'
    if c['Japanese'] >= 0.1 * tot: return 'Japanese'
    if c['Han'] >= 0.3 * tot: return 'Han'
    return c.most_common(1)[0][0]

HEAD_RE = re.compile(r'^\s{0,3}#{1,6}\s+(\S.*)$', re.M)
def templated(raw_msgs):
    """True when most messages share one heading layout (a machine-made template, already a fixed format)."""
    lay = collections.Counter(tuple(h.strip().lower() for h in HEAD_RE.findall(m)) for m in raw_msgs)
    top, n = lay.most_common(1)[0]
    return len(top) >= 2 and n >= 0.6 * len(raw_msgs)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--work', required=True); ap.add_argument('--now')
    a = ap.parse_args()
    bots = {b['id']: b for b in load_json(os.path.join(a.work, 'bots.json'), [])}
    labels = load_json(os.path.join(a.work, 'labels.json'), {})
    jin = {x['key']: x for x in load_json(os.path.join(a.work, 'judge_inputs.json'), [])}
    tls = {}
    for p in sorted(glob.glob(os.path.join(a.work, 'timelines', '*.json'))):
        tl = load_json(p); tls[tl['id']] = tl
    if not tls:
        sys.exit('no timelines; run sessions.py parse first')
    sid = short_ids(tls)
    R = lambda bid, i: f'{sid[bid]}:{i}'
    all_ts = [e['ts'] for tl in tls.values() for e in tl['events'] if e.get('ts')]
    a.now = a.now or (load_json(os.path.join(a.work, 'replay.json'), {}) or {}).get('now')   # replay tests pin "now"
    if a.now:
        now = P(a.now)
    else:
        off = collections.Counter(tl.get('utc_offset_hours', 0) for tl in tls.values()).most_common(1)[0][0]
        now = dt.datetime.now(dt.timezone(dt.timedelta(hours=off))).replace(tzinfo=None, second=0, microsecond=0)
    fleet_first = min((P(t) for t in all_ts), default=now)
    total_real = sum(sum(1 for e in tl['events'] if e['role'] == 'user') for tl in tls.values())
    out = dict(now=now.strftime(FMT), fleet_first=fleet_first.strftime(FMT), fleet_age_days=round(days_between(fleet_first, now), 1),
               total_real_requests=total_real, bots={}, fleet={})
    waits_all = []
    for bid, tl in tls.items():
        ev = tl['events']; users = [e for e in ev if e['role'] == 'user' and e.get('ts')]
        mine = lambda pred: [(k, v) for k, v in labels.items() if k.startswith(bid + ':') and k in jin and pred(v)]
        stamps = [P(e['ts']) for e in ev if e.get('ts')]
        first = min(stamps) if stamps else now
        last_user = P(users[-1]['ts']) if users else None
        runs = sorted(P(e['ts']) for e in ev if e.get('kind') == 'routine' and e.get('ts'))
        handoffs_in = sorted(P(e['ts']) for e in ev if e.get('kind') == 'agent' and e.get('ts'))
        # use = typed requests, routine runs or hand-offs from other bots
        last_use = max([x for x in (last_user, runs[-1] if runs else None, handoffs_in[-1] if handoffs_in else None) if x], default=None)
        age = days_between(first, now); idle = days_between(last_use, now) if last_use else age
        sday = session_days([e['ts'] for e in users])   # ts -> date of its session (late-night work = one day)
        udays = sorted({dt.date.fromisoformat(d) for d in sday.values()})
        gaps = [(b - a).days for a, b in zip(udays, udays[1:])]
        kept = sorted((jin[k]['ts'], jin[k]['user'], k) for k, v in mine(lambda v: v.get('type') == 'keep') if jin[k].get('ts'))
        user_keep = dict(ts=kept[-1][0], text=norm(kept[-1][1])[:160], ref=R(bid, kept[-1][2].rsplit(':', 1)[1])) if kept else None
        # ---- your correction labels -> incidents (same topic within 60 min) -> topics with occasions and days
        cors = sorted(((jin[k]['ts'], k, v) for k, v in mine(lambda v: v.get('label'))), key=lambda x: x[0] or '')
        incidents = []
        for ts, k, v in cors:
            ref = R(bid, k.rsplit(':', 1)[1])
            if incidents and incidents[-1]['topic'] == v.get('topic') and ts and incidents[-1]['last'] and \
                    (P(ts) - P(incidents[-1]['last'])).total_seconds() <= INCIDENT_MIN * 60:
                incidents[-1]['refs'].append(ref); incidents[-1]['last'] = ts; continue
            incidents.append(dict(topic=v.get('topic') or 'other', first=ts, last=ts, refs=[ref], confidence=v.get('confidence', 'medium')))
        fixes = [dict(ts=e['ts'], kind='memory_write', ref=R(bid, e['i']), text=norm(e['text'])[:300]) for e in ev
                 if e.get('ts') and e.get('kind') == 'memory_write']
        for k, v in mine(lambda v: v.get('fix_promised')):   # replies you marked as promising a lasting change
            if jin[k].get('ts'):
                fixes.append(dict(ts=jin[k]['ts'], kind='bot_promised', ref=R(bid, k.rsplit(':', 1)[1]), text=norm(jin[k].get('next_bot', ''))[:300]))
        fixes = [dict(f, id=f'fx-{i}') for i, f in enumerate(sorted(fixes, key=lambda f: f['ts']), 1)]
        user_days = sorted(set(sday.values()))
        topics = {}
        for inc in incidents:
            g = topics.setdefault(inc['topic'], dict(incidents=0, occasions=0, days=set(), refs=[], first=inc['first'], last=None,
                                                     confidences=[], times=[]))
            if not g['last'] or not inc['first'] or (P(inc['first']) - P(g['last'])).total_seconds() > SESSION_GAP_H * 3600:
                g['occasions'] += 1
            g['incidents'] += 1; g['days'].add(sday.get(inc['first'] or '', (inc['first'] or '')[:10])); g['refs'] += inc['refs']
            g['last'] = inc['last']; g['confidences'].append(inc['confidence']); g['times'].append(inc['first'])
        n_real = max(1, len(users))
        for topic, g in topics.items():
            g['days'] = sorted(d for d in g['days'] if d); g['per_100_requests'] = round(100 * g['incidents'] / n_real, 1)
            # saves and promised fixes from this topic's first incident on, with this topic's incidents and the days
            # of use after each: whether one is about this problem is yours to decide
            cand = [dict(id=f['id'], ts=f['ts'], incidents_after=sum(1 for t in g['times'] if t and t > f['ts']),
                         active_days_after=sum(1 for d in user_days if d > f['ts'][:10]))
                    for f in fixes if g['first'] and f['ts'] >= g['first']]
            late = [c for c in cand if not c['incidents_after']]
            keep = {c['id'] for c in cand if c['incidents_after']} | {c['id'] for c in late[-FIX_MAX:]}
            g['fixes_after'] = [c for c in cand if c['id'] in keep]
            if len(cand) > len(keep): g['fixes_after_omitted'] = len(cand) - len(keep)
            g.pop('times')
        # ---- waits: a user message with no bot reply for WAIT_H+ hours (lower bound from the next timestamp)
        waits, unanswered_runs = [], []; k = 0; seq = [e for e in ev if e['role'] in ('user', 'bot')]
        while k < len(seq):
            if seq[k]['role'] != 'user' or not seq[k].get('ts'):
                k += 1; continue
            j = k
            while j + 1 < len(seq) and seq[j + 1]['role'] == 'user': j += 1
            nxt_bot = seq[j + 1] if j + 1 < len(seq) else None
            run = [x for x in seq[k:j + 1] if x.get('ts') and 'group' not in x]
            if len(run) >= RUN_N:
                unanswered_runs.append(dict(first=run[0]['ts'], last=run[-1]['ts'], messages=len(run), refs=[R(bid, x['i']) for x in run][:6],
                                            minutes=round((P(run[-1]['ts']) - P(run[0]['ts'])).total_seconds() / 60), answered=nxt_bot is not None))
            if nxt_bot is not None and nxt_bot.get('ts'):
                hours = (P(nxt_bot['ts']) - P(seq[k]['ts'])).total_seconds() / 3600
                if hours >= WAIT_H:
                    w = dict(bot=bid, first=seq[k]['ts'], until=nxt_bot['ts'], hours=round(hours, 1), messages=j - k + 1,
                             refs=[R(bid, x['i']) for x in seq[k:j + 1]][:3])
                    waits.append(w); waits_all.append(w)
            k = j + 1
        unanswered_end = [R(bid, x['i']) for x in seq[max([n for n, x in enumerate(seq) if x['role'] == 'bot'], default=-1) + 1:] if x['role'] == 'user']
        skips = [e for e in ev if e.get('kind') == 'skipped_question']
        # ---- promises you marked "later", with the user's next message
        pos = {e['i']: n for n, e in enumerate(seq) if 'i' in e}; promises = []
        for k2, v in mine(lambda v: v.get('promise_later')):
            if not jin[k2].get('ts'): continue
            i = int(k2.rsplit(':', 1)[1]); n0 = pos.get(i)
            nxt_u = next((x for x in seq[n0 + 1:] if x['role'] == 'user'), None) if n0 is not None else None
            promises.append(dict(ts=jin[k2]['ts'], ref=R(bid, i), bot=norm(jin[k2].get('next_bot', ''))[:160],
                                 next_user=norm(nxt_u['text'])[:80] if nxt_u else None, next_user_ref=R(bid, nxt_u['i']) if nxt_u else None,
                                 next_user_ts=nxt_u.get('ts') if nxt_u else None))
        promises.sort(key=lambda p: p['ts'] or '')
        # ---- memory block: facts with their dates; past dates (digits only); exact duplicates; what you labelled later
        mem = None
        if tl.get('memory'):
            txt = tl['memory']['text']
            facts = [dict(learned=d, text=t.strip()) for d, t in re.findall(r'^- \(learned (\d{4}-\d\d-\d\d)\)\s*(.+)$', txt, re.M)]
            for f in facts:
                pd = past_dates(f['text'], now)
                if pd: f['past_dates'] = pd
            cnt = collections.Counter(norm(f['text']).lower() for f in facts)
            oldest = min((f['learned'] for f in facts), default=None)
            newer = sorted((dict(ts=jin[k]['ts'], ref=R(bid, k.rsplit(':', 1)[1]), type=v['type'], topic=v.get('topic'), text=norm(jin[k]['user'])[:160])
                            for k, v in mine(lambda v: v.get('type') in ('correction', 'preference', 'keep'))
                            if jin[k].get('ts') and oldest and jin[k]['ts'][:10] > oldest), key=lambda x: x['ts'])
            mem = dict(shown_facts=len(facts), not_shown=sum(int(n) for n in re.findall(r'\((\d+) more', txt)), facts=facts,
                       exact_duplicates=[t for t, n in cnt.items() if n > 1], newer_labelled=newer[-8:])
        # ---- exact repeats: resends (one request) and the same text on several days (group turns left out)
        resent, last_u = [], None
        for e in users:
            if last_u and norm(e['text']).lower() == norm(last_u['text']).lower() and \
                    (P(e['ts']) - P(last_u['ts'])).total_seconds() <= RESEND_MIN * 60:
                resent.append(R(bid, e['i']))
            last_u = e
        same = collections.defaultdict(list)
        for e in users:
            if 'group' not in e and R(bid, e['i']) not in resent and norm(e['text']): same[norm(e['text']).lower()].append(e)
        repeats = sorted((dict(text=norm(es[0]['text'])[:120], days=sorted({sday.get(e['ts'], e['ts'][:10]) for e in es}),
                               refs=[R(bid, e['i']) for e in es][:8])
                          for es in same.values() if len({e['ts'][:10] for e in es}) >= 2), key=lambda r: -len(r['days']))
        # ---- routine runs: counts, spacing, and how often the reply was missing or the same as the run before
        rstats = None
        if runs:
            noop, prev = 0, None
            for k3, e in enumerate(ev):
                if e.get('kind') != 'routine': continue
                nxt = next((f for f in ev[k3 + 1:] if f['role'] in ('bot', 'user') or f.get('kind') == 'routine'), None)
                r = norm(re.sub(r'\d+', '#', nxt['text'])) if nxt and nxt['role'] == 'bot' else None
                noop += r is None or r == prev; prev = r if r is not None else prev
            recent = [x for x in runs if days_between(x, now) <= 7]
            per = collections.Counter(x.strftime('%Y-%m-%d') for x in runs)
            rstats = dict(runs=len(runs), first=runs[0].strftime(FMT), last=runs[-1].strftime(FMT),
                          median_gap_min=round(median([(y - x).total_seconds() / 60 for x, y in zip(runs, runs[1:])]) or 0, 1),
                          runs_per_day_last7=round(len(recent) / max(1.0, min(7.0, days_between(recent[0], now))), 1) if recent else 0,
                          max_runs_per_day=max(per.values()), no_reply_or_same=round(noop / len(runs), 2),
                          refs=[R(bid, e['i']) for e in ev if e.get('kind') == 'routine'][-3:])
        used_plugins = {re.sub(r'[^a-z]', '', e['text'].lower()) for e in ev if e.get('kind') == 'plugin_call'}
        svc = collections.defaultdict(set)
        for e in ev:
            if e.get('kind') == 'browser' and e.get('ts'):
                for h in e['text'].split():
                    if service_of(h): svc[service_of(h)].add(e['ts'][:10])
        browser = [dict(service=k, days=sorted(v), plugin_used=any(re.sub(r'[^a-z]', '', k.lower()) in u for u in used_plugins))
                   for k, v in sorted(svc.items())]
        # ---- writing system of replies vs the user's chat (code, links and paths ignored)
        langs = collections.Counter(main_script(e['text']) for e in users if 'group' not in e)
        langs.pop(None, None); scripts = None
        if langs:
            chat_s = langs.most_common(1)[0][0]; hits, trig = [], None
            for e in ev:
                if e['role'] == 'bot' and trig is not None and trig['role'] == 'user' and e.get('ts') and 'group' not in trig:
                    rs = main_script(e['text'])
                    if rs and rs != chat_s and main_script(trig['text']) != rs and sum(ch.isalpha() for ch in CODE_RE.sub(' ', e['text'])) >= 30:
                        hits.append(dict(day=sday.get(trig['ts'], e['ts'][:10]), ref=R(bid, e['i']), script=rs))
                if e['role'] == 'user' or e.get('kind') in ('routine', 'agent'): trig = e
                elif e['role'] == 'bot': trig = None
            scripts = dict(user=dict(langs), other_script_replies=len(hits), days=sorted({h['day'] for h in hits}), refs=[h['ref'] for h in hits][:4])
        groups_seen = collections.defaultdict(set)
        for e in users:
            if 'group' in e: groups_seen[e['group']].add(e['ts'][:10])
        b = bots.get(bid, dict(name=tl['name'], description=''))
        out['bots'][bid] = dict(
            name=b['name'], ref_prefix=sid[bid], description=b.get('description', ''), description_empty=not b.get('description'),
            first_seen=first.strftime(FMT), last_request=last_user.strftime(FMT) if last_user else None,
            last_request_ref=R(bid, users[-1]['i']) if users else None, last_use=last_use.strftime(FMT) if last_use else None,
            real_requests=len(users), share=round(len(users) / max(1, total_real), 3), active_days=len(udays),
            age_days=round(age, 1), idle_days=round(idle, 1), idle_typed_days=round(days_between(last_user, now) if last_user else age, 1),
            typical_gap_days=median(gaps), longest_gap_days=max(gaps, default=None), coverage=tl.get('coverage'),
            bot_replies=sum(1 for e in ev if e['role'] == 'bot'), handoffs_received=len(handoffs_in), routines=rstats,
            user_keep=user_keep, corrections=len(cors), incidents=incidents, correction_topics=topics,
            preferences=[R(bid, k.rsplit(':', 1)[1]) for k, v in mine(lambda v: v.get('type') == 'preference')],
            fixes=fixes, waits=waits, unanswered_runs=unanswered_runs, unanswered_at_end=unanswered_end,
            skipped_questions=dict(count=len(skips), questions=[s['text'][:120] for s in skips][:10]),
            promises=promises, memory=mem, resends=resent, repeated_texts=repeats[:10], browser_sites=browser,
            scripts=scripts, group_chats={k: sorted(v) for k, v in groups_seen.items()})
    # ---- fleet: waits that overlap in 2+ bots
    span = lambda w: (P(w['first']), P(w['until']))
    for w in waits_all:
        s, e = span(w)
        w['overlaps_other_bot'] = any(x['bot'] != w['bot'] and span(x)[0] < e and span(x)[1] > s for x in waits_all)
    ow = [w for w in waits_all if w['overlaps_other_bot']]
    out['fleet']['overlapping_waits'] = [dict(start=min(w['first'] for w in ow), bots=sorted({w['bot'] for w in ow}), waits=ow)] if ow else []
    # ---- fleet: group-chat messages (one turn is mirrored into every member's chat) and exact same texts across bots
    gmsg = {(e['group'], e['ts'][:16], norm(e['text']).lower()) for tl in tls.values() for e in tl['events']
            if e['role'] == 'user' and 'group' in e and e.get('ts')}
    out['fleet']['group_messages'] = dict(unique=len(gmsg), copies=sum(1 for tl in tls.values() for e in tl['events']
                                                                    if e['role'] == 'user' and 'group' in e and e.get('ts')))
    across = collections.defaultdict(list)
    for bid, tl in tls.items():
        for e in tl['events']:
            if e['role'] == 'user' and 'group' not in e and len(norm(e['text'])) >= 12: across[norm(e['text']).lower()].append(R(bid, e['i']))
    out['fleet']['same_text_in_bots'] = [dict(text=t[:120], refs=r[:8]) for t, r in across.items()
                                         if len({x.split(':')[0] for x in r}) >= 2][:30]
    # ---- fleet: a bot's answer pasted by the user into another bot (most of its text, within 3 days)
    names = {bid: out['bots'][bid]['name'] for bid in out['bots']}
    botmsgs = {bid: [(P(e['ts']), grams(e['text']), e['i']) for e in tl['events'] if e['role'] == 'bot' and e.get('ts') and len(norm(e['text'])) >= 80]
               for bid, tl in tls.items()}
    edges = collections.defaultdict(list)
    for bid, tl in tls.items():
        for e in tl['events']:
            if e['role'] != 'user' or not e.get('ts') or len(norm(e['text'])) < 80: continue
            t, gu = P(e['ts']), grams(e['text'])
            best = max(((len(gb & gu) / max(1, len(gb)), ob, bi) for ob, msgs in botmsgs.items() if ob != bid
                        for bt, gb, bi in msgs if t - dt.timedelta(days=RELAY_DAYS) <= bt <= t), default=(0, None, None))
            if best[0] >= 0.6:
                edges[(best[1], bid)].append(dict(ref=R(bid, e['i']), from_ref=R(best[1], best[2]), ts=e['ts'], chars=len(norm(e['text']))))
    shared = lambda x, y: sorted(set(out['bots'][x]['group_chats']) & set(out['bots'][y]['group_chats']) - {''})
    out['fleet']['pasted_answers'] = [dict(src=names[x], to=names[y], count=len(v), days=sorted({i['ts'][:10] for i in v}),
                                           median_chars=int(median([i['chars'] for i in v])), shared_groups=shared(x, y), examples=v[:3])
                                      for (x, y), v in edges.items()]
    # ---- fleet: bot-to-bot messages per pair (length, template, burst)
    hand = []
    for bid, tl in tls.items():
        msgs = collections.defaultdict(list)
        for e in tl['events']:
            if e.get('kind') == 'agent' and e.get('sender') and norm(e.get('text')): msgs[e['sender']].append(e)
        for snd, ms in msgs.items():
            tsl = sorted(P(e['ts']) for e in ms if e.get('ts'))
            close = sum(1 for x, y in zip(tsl, tsl[1:]) if (y - x).total_seconds() <= BURST_MIN * 60)
            hand.append(dict(src=snd, to=names[bid], messages=len(ms), median_chars=int(median([len(norm(e['text'])) for e in ms])),
                             same_headings=templated([e['text'] for e in ms]), within_15_min_share=round(close / max(1, len(tsl) - 1), 2),
                             refs=[R(bid, e['i']) for e in ms][:3]))
    out['fleet']['bot_to_bot'] = hand
    # ---- fleet: group chats with exactly the same members (only groups seen in the saved chats)
    members = collections.defaultdict(set); gdays = collections.defaultdict(set)
    for bid, b in out['bots'].items():
        for gname, days in b['group_chats'].items():
            if gname: members[gname].add(bid); gdays[gname].update(days)
    gl = sorted(members)
    out['fleet']['same_member_groups'] = [dict(groups=[g1, g2], bots=sorted(names[x] for x in members[g1]),
                                               last={g1: max(gdays[g1]), g2: max(gdays[g2])})
                                          for i, g1 in enumerate(gl) for g2 in gl[i + 1:] if len(members[g1]) >= 2 and members[g1] == members[g2]]
    dump_json(out, os.path.join(a.work, 'diag.json'))
    for bid, b in out['bots'].items():
        print(f"{b['name']} [{b['ref_prefix']}]: {b['real_requests']} typed on {b['active_days']} days, {b['first_seen'][:10]} to "
              f"{(b['last_request'] or '-')[:10]}, idle {b['idle_days']} of {b['age_days']} days, share {b['share']}"
              + (f", {b['routines']['runs']} routine runs" if b['routines'] else '')
              + (f", corrections {dict((t, g['incidents']) for t, g in b['correction_topics'].items())}" if b['correction_topics'] else '')
              + (f", {len(b['waits'])} waits" if b['waits'] else '') + (', you said keep' if b['user_keep'] else ''))
    print('->', os.path.join(a.work, 'diag.json'))

if __name__ == '__main__':
    main()
