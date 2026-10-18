#!/usr/bin/env python3
"""Bot Audit, step 3: usage, repeated corrections, suggested status, and extra checks for every bot.

  python3 diagnostics.py --work W [--now "YYYY-MM-DD HH:MM"]   (default: now, or "now" in W/replay.json)
      Reads W/bots.json, W/timelines/*.json, W/labels.json (from the judge step) -> W/diag.json

Everything is computed from data inside Grok Bot (saved transcript pages, profile name/description,
the memory block the app injects). Rules and thresholds: references/criteria.md.
Fields marked "candidates" are leads for the host bot to read and confirm, not findings.
"""
import argparse, collections, datetime as dt, glob, os, re, sys, unicodedata
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import dump_json, grams, jaccard, load_cues, load_json, norm

FMT = '%Y-%m-%d %H:%M'
P = lambda s: dt.datetime.strptime(s, FMT)
INCIDENT_MIN = 60
WAIT_H = 6
FIX_MAX = 12
SESSION_GAP_H = 6   # incidents further apart than this are separate occasions
FADE_GAP = 7        # "used regularly": a typical gap of at most this many days between active days
RATE_FLOOR = 0.01   # "3+ incidents" makes a group strong only at 1 incident per 100 real requests or more
NEW_DAYS = 14       # a bot younger than this, that joined in the later half of the history, is too new to judge
RELAY_DAYS = 3
HANDOFF_LONG = 600  # bot-to-bot messages this long (median), or mostly repeating the previous one, suggest a short format
HANDOFF_PASTE = 400 # pasted hand-offs this long (median) suggest it too
BURST_MIN = 15      # bot-to-bot messages mostly this close together are one fan-out run (already machine-made), not hand-offs
RESEND_MIN = 30     # the same text sent again this soon is a resend (one request)
FOLLOW_MIN = 30     # a user message this soon after the bot's reply continues that conversation (a follow-up, not a new task)
STALL_N, STALL_CHARS, STALL_SPAN_MIN = 3, 40, 10   # stall: 3+ short user messages in a row with no reply, over 10+ minutes
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

SENT_SPLIT = re.compile(r'(?<=[.!?\u3002\uff01\uff1f])\s+')

def addressed_sentence(text, rx, long_draft=600, edge=250):
    """The sentence where the bot tells the user about a lasting change, or None if the cue only appears inside
    content the bot drafted: code blocks, quoted or table lines, or the middle of a long draft."""
    text = drop_links(text)
    lines, fence = [], False
    for ln in text.splitlines():
        if ln.strip().startswith('```'): fence = not fence; continue
        if fence or re.match(r'\s*(>|\|)', ln): continue
        lines.append(ln)
    body = '\n'.join(lines)
    m = rx.search(body)
    if not m: return None
    if len(body) > long_draft and edge < m.start() < len(body) - edge: return None
    start = max(body.rfind('\n', 0, m.start()), *(body.rfind(x, 0, m.start()) for x in ('. ', '! ', '? ', '\u3002'))) + 1
    ends = [i for i in (body.find(x, m.end()) for x in ('. ', '! ', '? ', '\n', '\u3002')) if i >= 0]
    sent = norm(body[start:(min(ends) + 1 if ends else len(body))])
    if sent.count('"') % 2 or sent.count('\u201c') != sent.count('\u201d'): return None   # inside a quotation
    return sent[:300]

LINK_RE = re.compile(r'\[([^\]\n]*)\]\([^)\s]+\)|<?\bhttps?://\S+|\bwww\.\S+')
LIST_RE = re.compile(r'^\s*(?:[-*\u2022]|\d+[.)])\s+')

def drop_links(text):
    """Text without link lists: list lines that hold a link are dropped, and remaining links lose their target and
    title, so words inside a link title ("Going forward: ...") or a list of sources never read as a promise or a fix."""
    out = []
    for ln in (text or '').splitlines():
        if LINK_RE.search(ln) and LIST_RE.match(ln): continue
        out.append(LINK_RE.sub(' ', ln))
    return '\n'.join(out)

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
    from common import PATH_RE
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

def last_sentence(text):
    parts = [norm(x) for x in SENT_SPLIT.split(norm(text)) if norm(x)]
    return (parts[-1] if parts else '')[:300]

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--work', required=True); ap.add_argument('--now')
    a = ap.parse_args()
    cues, _ = load_cues(a.work); FIX, PROMISE, NUDGE, TIMELY, SAFETY = cues['fix'], cues['promise'], cues['nudge'], cues['timely'], cues['safety']
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
    fleet_first = min((P(t) for t in all_ts), default=now)
    fleet_age = days_between(fleet_first, now)
    total_real = sum(sum(1 for e in tl['events'] if e['role'] == 'user') for tl in tls.values())
    out = dict(now=now.strftime(FMT), total_real_requests=total_real, bots={}, fleet={})
    waits_all = []
    for bid, tl in tls.items():
        ev = tl['events']; users = [e for e in ev if e['role'] == 'user' and e.get('ts')]
        stamps = [P(e['ts']) for e in ev if e.get('ts')]
        first = min(stamps) if stamps else now
        last_user = P(users[-1]['ts']) if users else None
        runs = sorted(P(e['ts']) for e in ev if e.get('kind') == 'routine' and e.get('ts'))
        handoffs_in = sorted(P(e['ts']) for e in ev if e.get('kind') == 'agent' and e.get('ts'))
        # Use = typed requests, routine runs or hand-offs from other bots: a bot that works by routine or for other
        # bots is in use even if the user never types to it.
        last_use = max([x for x in (last_user, runs[-1] if runs else None, handoffs_in[-1] if handoffs_in else None) if x], default=None)
        age = days_between(first, now); idle = days_between(last_use, now) if last_use else age
        idle_typed = days_between(last_user, now) if last_user else age
        sday = session_days([e['ts'] for e in users])   # ts -> date of its session (late-night work = one day)
        udays = sorted({dt.date.fromisoformat(d) for d in sday.values()})
        typical_gap = median([(b - a).days for a, b in zip(udays, udays[1:])])
        # its own rhythm: a monthly bot is not idle after three weeks (needs 2+ active days to know the rhythm)
        within_rhythm = bool(typical_gap) and idle <= 1.5 * typical_gap + 1
        # a habit that stopped: used regularly (5+ days, typically at most a week apart), now idle far beyond that rhythm
        faded = len(udays) >= 5 and typical_gap is not None and typical_gap <= FADE_GAP and idle >= max(14, 4 * typical_gap)
        too_new = age < NEW_DAYS and age < fleet_age / 2
        run_gap_days = median([days_between(x, y) for x, y in zip(runs, runs[1:])]) or 0
        routine_active = bool(runs) and days_between(runs[-1], now) <= max(3, 2 * run_gap_days)
        # the user said to keep this bot or that it is paused on purpose (judge type keep, any language): latest one
        kept = sorted((jin[k]['ts'], jin[k]['user']) for k, v in labels.items()
                      if k.startswith(bid + ':') and v.get('type') == 'keep' and k in jin and jin[k].get('ts'))
        user_keep = dict(ts=kept[-1][0], text=norm(kept[-1][1])[:160]) if kept else None
        # ---- corrections -> incidents -> groups
        cors = sorted(((jin[k]['ts'], k, v) for k, v in labels.items()
                       if k.startswith(bid + ':') and v.get('label') and k in jin), key=lambda x: x[0] or '')
        incidents = []
        for ts, k, v in cors:
            if incidents and incidents[-1]['topic'] == v.get('topic') and ts and incidents[-1]['last'] and \
                    (P(ts) - P(incidents[-1]['last'])).total_seconds() <= INCIDENT_MIN * 60:
                incidents[-1]['keys'].append(k); incidents[-1]['last'] = ts; continue
            incidents.append(dict(topic=v.get('topic') or 'other', first=ts, last=ts, keys=[k], confidence=v.get('confidence', 'medium')))
        fixes = [dict(ts=e['ts'], kind='memory_write', text=norm(e['text'])[:300]) for e in ev
                 if e.get('ts') and e.get('kind') == 'memory_write']
        for e in ev:   # "from now on…" said to the user (not inside drafted content)
            if e.get('ts') and e['role'] == 'bot':
                sent = addressed_sentence(e['text'], FIX)
                if sent: fixes.append(dict(ts=e['ts'], kind='bot_said', text=sent))
        # promises of a lasting change that the judge marked on a correction's reply (any language)
        for k, v in labels.items():
            if k.startswith(bid + ':') and v.get('fix_promised') and k in jin and jin[k].get('ts'):
                nb = jin[k].get('next_bot', '')
                fixes.append(dict(ts=jin[k]['ts'], kind='bot_promised', text=addressed_sentence(nb, FIX) or last_sentence(drop_links(nb)) or last_sentence(nb)))
        seen, uniq = set(), []
        for f in sorted(fixes, key=lambda f: f['ts']):   # one entry per distinct save or promise
            sig = (f['kind'] == 'memory_write', norm(f['text']).lower())
            if sig in seen: continue
            seen.add(sig); uniq.append(f)
        fixes = [dict(f, id=f'fx-{i}') for i, f in enumerate(uniq, 1)]
        user_days = sorted(set(sday.values()))
        groups = {}
        for inc in incidents:
            g = groups.setdefault(inc['topic'], dict(incidents=0, days=set(), sessions=0, keys=[], first=inc['first'], last=None,
                                                     confidences=[], incident_times=[]))
            if not g['last'] or not inc['first'] or (P(inc['first']) - P(g['last'])).total_seconds() > SESSION_GAP_H * 3600:
                g['sessions'] += 1
            g['incidents'] += 1; g['days'].add(sday.get(inc['first'] or '', (inc['first'] or '')[:10])); g['keys'] += inc['keys']
            g['last'] = inc['last']; g['confidences'].append(inc['confidence']); g['incident_times'].append(inc['first'])
        n_real = max(1, len(users))
        for topic, g in groups.items():
            g['days'] = sorted(d for d in g['days'] if d)
            g['rate'] = round(g['incidents'] / n_real, 3)
            # Repeated = 2+ incidents on 2+ separate occasions (gaps over SESSION_GAP_H). Incidents that all fall in one
            # working session are steering of one task (one_session), never a repeated problem on their own.
            g['one_session'] = g['sessions'] < 2
            g['repeated'] = g['incidents'] >= 2 and g['sessions'] >= 2
            # Fix candidates: memory saves, announced fixes and judged promises in the same bot from the group's first
            # incident on. Whether one is about this group's problem can't be told from words, so they are candidates:
            # they change neither status nor impact until the host bot confirms. Each carries the facts the decision
            # needs: incidents of this group after it, and days of use after it.
            # The window starts at this topic's first incident in the whole history, in time order. Full texts are
            # listed once per bot (fix_candidates).
            cand = [dict(id=f['id'], ts=f['ts'], incidents_after=sum(1 for t in g['incident_times'] if t and t > f['ts']),
                         active_days_after=sum(1 for d in user_days if d > f['ts'][:10]))
                    for f in fixes if g['first'] and f['ts'] >= g['first']]
            # Every candidate an incident came after (a fix that may have failed) is kept, however old; of the rest
            # (no incident after them), the FIX_MAX latest. Any left out are counted, so nothing is hidden silently.
            late = [c for c in cand if not c['incidents_after']]
            keep = {c['id'] for c in cand if c['incidents_after']} | {c['id'] for c in late[-FIX_MAX:]}
            g['fix_candidates'] = [c for c in cand if c['id'] in keep]
            if len(cand) > len(keep):
                g['fix_candidates_omitted'] = dict(count=len(cand) - len(keep), first=cand[0]['ts'],
                                                   last=max(c['ts'] for c in cand if c['id'] not in keep))
            # came back after a possible fix: a candidate with an incident of this group after it (unconfirmed)
            g['came_back_candidate'] = any(c['incidents_after'] for c in g['fix_candidates'])
            g['strong'] = g['repeated'] and ((g['incidents'] >= 3 and g['rate'] >= RATE_FLOOR) or g['rate'] >= 0.05) \
                and any(c != 'low' for c in g['confidences'])
            g.pop('incident_times')
        skips_n = sum(1 for e in ev if e.get('kind') == 'skipped_question')
        for g in groups.values():
            # the user often moves past this bot's question cards: a "confirm / ask first" rule would make that worse
            # (criteria.md section 5, step 1), so it is never this group's shared cause
            g['confirm_conflict'] = skips_n >= 2
        prefs = [k for k, v in labels.items() if k.startswith(bid + ':') and v.get('type') == 'preference']
        # ---- waits: user message(s) with no bot reply for >= WAIT_H hours (lower bound from the next timestamp)
        waits, stalls = [], []; k = 0; seq = [e for e in ev if e['role'] in ('user', 'bot')]
        while k < len(seq):
            if seq[k]['role'] != 'user' or not seq[k].get('ts'):
                k += 1; continue
            j = k
            while j + 1 < len(seq) and seq[j + 1]['role'] == 'user': j += 1
            nxt_bot = seq[j + 1] if j + 1 < len(seq) else None
            t0 = P(seq[k]['ts'])
            run = [x for x in seq[k:j + 1] if x.get('ts') and 'group' not in x]
            short = [x for x in run if len(norm(x['text'])) <= STALL_CHARS]
            reply_h = (P(nxt_bot['ts']) - t0).total_seconds() / 3600 if nxt_bot and nxt_bot.get('ts') else None
            if len(short) >= STALL_N and (P(run[-1]['ts']) - P(short[0]['ts'])).total_seconds() >= STALL_SPAN_MIN * 60 \
                    and (reply_h is None or reply_h < WAIT_H):
                # several short nudges with no reply in between, shorter than a wait: the bot looked stuck
                stalls.append(dict(first=run[0]['ts'], last=run[-1]['ts'], messages=len(run), texts=[norm(x['text'])[:60] for x in short][:4],
                                   answered=nxt_bot is not None))
            if nxt_bot is None:   # the last message in the data: the bot may not have had time to answer
                k = j + 1; continue
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
            if e['role'] == 'bot' and len(e['text']) < 240 and PROMISE.search(drop_links(e['text'])) and k2 + 1 < len(seq) \
                    and seq[k2 + 1]['role'] == 'user' and NUDGE.search(norm(seq[k2 + 1]['text'])) and len(norm(seq[k2 + 1]['text'])) <= 20:
                promises.append(dict(ts=e['ts'], bot=norm(e['text'])[:120], next_user=norm(seq[k2 + 1]['text'])[:40]))
            elif e['role'] == 'bot' and len(e['text']) < 240 and k2 + 1 < len(seq) and seq[k2 + 1]['role'] == 'user' \
                    and e.get('ts') and seq[k2 + 1].get('ts') and len(norm(seq[k2 + 1]['text'])) <= 6 \
                    and re.search(r'[?\uff1f]$', norm(seq[k2 + 1]['text'])) and not re.search(r'[?\uff1f]$', norm(e['text'])) \
                    and (P(seq[k2 + 1]['ts']) - P(e['ts'])).total_seconds() >= 3600:
                # any language: a very short check-in question ("…?") after an hour or more of silence following a short bot
                # message that was not itself a question
                promises.append(dict(ts=e['ts'], bot=norm(e['text'])[:120], next_user=norm(seq[k2 + 1]['text'])[:40], by='silence'))
        # promises the judge marked (promised = later): the bot said it would do something later, in any language
        pos = {e['i']: n for n, e in enumerate(seq) if 'i' in e}
        for k, v in labels.items():
            if k.startswith(bid + ':') and v.get('promise_later') and k in jin and jin[k].get('ts'):
                i = int(k.rsplit(':', 1)[1]); n0 = pos.get(i)
                nxt_u = next((x for x in seq[n0 + 1:] if x['role'] == 'user'), None) if n0 is not None else None
                if not any(p['bot'][:60] and p['bot'][:60] in norm(jin[k].get('next_bot', '')) for p in promises):   # cue found it too
                    promises.append(dict(ts=jin[k]['ts'], bot=norm(jin[k].get('next_bot', ''))[:120], by='judge',
                                         next_user=norm(nxt_u['text'])[:40] if nxt_u else None,
                                         next_user_ts=nxt_u.get('ts') if nxt_u else None))
        promises.sort(key=lambda p: p['ts'] or '')
        # ---- memory block
        mem = None
        if tl.get('memory'):
            txt = tl['memory']['text']
            facts = [dict(learned=d, text=t.strip()) for d, t in re.findall(r'^- \(learned (\d{4}-\d\d-\d\d)\)\s*(.+)$', txt, re.M)]
            for f in facts:
                f['time_sensitive'] = bool(TIMELY.search(f['text'])) and days_between(P(f['learned'] + ' 00:00'), now) >= 3
                if past_dates(f['text'], now): f['time_sensitive'] = True; f['past_dates'] = past_dates(f['text'], now)
            dups = [(f1['text'][:100], f2['text'][:100]) for i, f1 in enumerate(facts) for f2 in facts[i + 1:]
                    if jaccard(grams(f1['text']), grams(f2['text'])) >= 0.45]
            # any language: what the judge found in this chat after the oldest fact was learned (corrections, preferences,
            # keep); the host compares the facts with these to find stale ones
            oldest = min((f['learned'] for f in facts), default=None)
            newer = sorted((dict(ts=jin[k]['ts'], type=v['type'], topic=v.get('topic'), text=norm(jin[k]['user'])[:160])
                            for k, v in labels.items() if k.startswith(bid + ':') and k in jin and jin[k].get('ts') and oldest
                            and v.get('type') in ('correction', 'preference', 'keep') and jin[k]['ts'][:10] > oldest),
                           key=lambda x: x['ts'])
            mem = dict(shown_facts=len(facts), not_shown=sum(int(n) for n in re.findall(r'\((\d+) more', txt)),
                       time_sensitive=[f for f in facts if f['time_sensitive']], near_duplicates=dups, facts=facts,
                       newer_judged=newer[-8:])
        # ---- repeated requests across days (routine candidates)
        # messages the judge labelled (corrections, preferences) belong to the correction groups, never also here
        # (and keep or ack: a keep statement or an acknowledgement is not a request); texts like an acknowledgement go too
        judged = {k for k, v in labels.items() if k.startswith(bid + ':') and (v.get('label') or v.get('type') in ('keep', 'ack'))}
        acks = [grams(jin[k]['user']) for k, v in labels.items() if k.startswith(bid + ':') and v.get('type') == 'ack' and k in jin]
        resent, last_u = set(), None   # the same text sent again within RESEND_MIN minutes: one request, not two
        for e in users:
            if last_u and norm(e['text']).lower() == norm(last_u['text']).lower() and \
                    (P(e['ts']) - P(last_u['ts'])).total_seconds() <= RESEND_MIN * 60:
                resent.add(e['i'])
            last_u = e
        follow = set()   # sent soon after the bot's reply: continues that conversation
        prev = None
        for e in ev:
            if e['role'] == 'user' and prev is not None and prev['role'] == 'bot' and e.get('ts') and prev.get('ts') \
                    and (P(e['ts']) - P(prev['ts'])).total_seconds() <= FOLLOW_MIN * 60:
                follow.add(e['i'])
            if e['role'] in ('user', 'bot') or e.get('kind') in ('routine', 'agent'): prev = e
        # group-chat turns are left out: the same message is mirrored into every member bot's chat
        items = [(sday.get(e['ts'], e['ts'][:10]), grams(e['text']), norm(e['text'])[:80], e['i'] in follow) for e in users
                 if len(norm(e['text'])) >= 6 and f"{bid}:{e['i']}" not in judged and 'group' not in e and e['i'] not in resent
                 and not any(jaccard(grams(e['text']), ag) >= 0.5 for ag in acks)]
        rep, seen = [], set()
        for d0, g0, t0, _ in items:
            sim = [(d, t, fu) for d, g, t, fu in items if jaccard(g0, g) >= 0.3]
            dset = sorted({d for d, _, _ in sim})
            if len(dset) >= 3 and t0 not in seen:
                seen.update(t for _, t, _ in sim)
                # mostly follow-ups ("test it too", "continue"): a standing rule fits, not a scheduled routine
                rep.append(dict(days=dset, examples=sorted({t for _, t, _ in sim})[:4], messages=len(sim),
                                follow_up=sum(fu for _, _, fu in sim) >= 0.5 * len(sim)))
        rep.sort(key=lambda r: -len(r['days']))
        # ---- setup (references/setup.md): routine cost, browser work on a site with a plugin, safety rules in memory
        rcost = None
        if len(runs) >= 6:
            replies, prev, noop = [], None, 0
            for k3, e in enumerate(ev):
                if e.get('kind') != 'routine': continue
                nxt = next((f for f in ev[k3 + 1:] if f['role'] == 'bot' or f['role'] == 'user' or f.get('kind') == 'routine'), None)
                r = norm(re.sub(r'\d+', '#', nxt['text'])) if nxt and nxt['role'] == 'bot' else None
                noop += r is None or r == prev; prev = r if r is not None else prev
            gap_min = median([(y - x).total_seconds() / 60 for x, y in zip(runs, runs[1:])])
            recent = [x for x in runs if days_between(x, now) <= 7]
            per_day = round(len(recent) / max(1.0, min(7.0, days_between(recent[0], now))), 1) if recent else 0
            share_noop = round(noop / len(runs), 2)
            if gap_min <= 15 or (per_day >= 24 and share_noop >= 0.5):
                rcost = dict(runs=len(runs), median_gap_min=round(gap_min, 1), runs_per_day=per_day, unchanged_or_silent=share_noop,
                             first=runs[0].strftime(FMT), last=runs[-1].strftime(FMT))
        used_plugins = {re.sub(r'[^a-z]', '', e['text'].lower()) for e in ev if e.get('kind') == 'plugin_call'}
        svc = collections.defaultdict(set)
        for e in ev:
            if e.get('kind') == 'browser' and e.get('ts'):
                for h in e['text'].split():
                    if service_of(h): svc[service_of(h)].add(e['ts'][:10])
        connectors = [dict(service=k, days=sorted(v)) for k, v in sorted(svc.items())
                      if len(v) >= 2 and not any(re.sub(r'[^a-z]', '', k.lower()) in u for u in used_plugins)]
        mem_texts = [(f['learned'], f['text'], 'memory') for f in (mem or {}).get('facts', [])] + \
                    [(e['ts'][:10], e['text'], 'memory_write') for e in ev if e.get('kind') == 'memory_write' and e.get('ts')]
        safety, seen_s = [], set()
        for d0, t0, src in mem_texts:
            if SAFETY.search(t0) and norm(t0) not in seen_s:
                seen_s.add(norm(t0)); safety.append(dict(date=d0, text=norm(t0)[:200], source=src))
        # ---- chat language: replies in another writing system than the user's chat (low-priority lead)
        langs = collections.Counter(main_script(e['text']) for e in users if 'group' not in e)
        langs.pop(None, None); mism = None
        if langs and langs.most_common(1)[0][1] >= 0.6 * sum(langs.values()):
            chat_lang = langs.most_common(1)[0][0]; trig, hits = None, []
            for e in ev:
                if e['role'] == 'bot' and trig is not None and trig['role'] == 'user' and e.get('ts') and 'group' not in trig:
                    rs = main_script(e['text']); us = main_script(trig['text'])
                    letters = sum(ch.isalpha() for ch in CODE_RE.sub(' ', e['text']))
                    if rs and letters >= 30 and rs != chat_lang and us != rs:
                        hits.append(dict(ts=e['ts'], day=sday.get(trig['ts'], e['ts'][:10]), reply_script=rs))
                if e['role'] == 'user' or e.get('kind') in ('routine', 'agent'): trig = e
                elif e['role'] == 'bot': trig = None
            hd = sorted({h['day'] for h in hits})
            if len(hd) >= 2:
                mism = dict(chat_script=chat_lang, reply_scripts=sorted({h['reply_script'] for h in hits}), replies=len(hits),
                            days=hd, examples=[h['ts'] for h in hits[:4]])
        groups_seen = collections.defaultdict(set)
        for e in users:
            if 'group' in e: groups_seen[e['group']].add(e['ts'][:10])
        b = bots.get(bid, dict(name=tl['name'], description=''))
        out['bots'][bid] = dict(
            name=b['name'], description=b.get('description', ''), description_empty=not b.get('description'),
            first_seen=first.strftime(FMT), last_request=last_user.strftime(FMT) if last_user else None,
            real_requests=len(users), share=round(len(users) / max(1, total_real), 3),
            active_days=len(udays), age_days=round(age, 1), idle_days=round(idle, 1),
            coverage=tl.get('coverage'), corrections=len(cors), incidents=incidents, groups=groups, preferences=prefs,
            fix_events=fixes, fix_candidates=[f for f in fixes if any(f['id'] in {c['id'] for c in g['fix_candidates']} for g in groups.values())], waits=waits, skipped_questions=dict(count=len(skips), questions=[s['text'][:120] for s in skips][:10]),
            promise_candidates=promises, memory=mem, repeated_requests=rep[:5],
            handoffs_received=len(handoffs_in), routines_seen=len(runs), last_routine_run=runs[-1].strftime(FMT) if runs else None, routine_active=routine_active,
            idle_typed_days=round(idle_typed, 1), typical_gap_days=typical_gap, within_rhythm=within_rhythm, too_new=too_new, faded=faded,
            user_keep=user_keep,
            routine_cost=rcost, connector_candidates=connectors, memory_safety_rules=safety,
            group_chats={k: sorted(v) for k, v in groups_seen.items()},
            stall_candidates=stalls, language_mismatch=mism)
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
    # a group-chat turn is mirrored into every member's chat: it is one message, not the same request in several bots
    keys = [(bid, e['ts'], grams(e['text']), norm(e['text'])[:80]) for bid, tl in tls.items()
            for e in tl['events'] if e['role'] == 'user' and len(norm(e['text'])) >= 12 and e.get('ts') and 'group' not in e]
    gmsg = {(e['group'], e['ts'][:16], norm(e['text']).lower()) for tl in tls.values() for e in tl['events']
            if e['role'] == 'user' and 'group' in e and e.get('ts')}
    out['fleet']['group_messages'] = dict(unique=len(gmsg), copies=sum(1 for tl in tls.values() for e in tl['events']
                                                                    if e['role'] == 'user' and 'group' in e and e.get('ts')))
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
    # ---- fleet: hand-offs the user does by hand (a bot's answer pasted into another bot) -> group chat candidates
    names = {bid: out['bots'][bid]['name'] for bid in out['bots']}
    botmsgs = {bid: [(P(e['ts']), grams(e['text'])) for e in tl['events'] if e['role'] == 'bot' and e.get('ts') and len(norm(e['text'])) >= 80]
               for bid, tl in tls.items()}
    edges = collections.defaultdict(list)
    for bid, tl in tls.items():
        for e in tl['events']:
            if e['role'] != 'user' or not e.get('ts') or len(norm(e['text'])) < 80: continue
            t, gu = P(e['ts']), grams(e['text'])
            # the pasted answer comes from the one bot message it matches best (templated answers look alike)
            best = max(((len(gb & gu) / max(1, len(gb)), ob) for ob, msgs in botmsgs.items() if ob != bid
                        for bt, gb in msgs if t - dt.timedelta(days=RELAY_DAYS) <= bt <= t), default=(0, None))
            if best[0] >= 0.6:
                edges[(best[1], bid)].append(dict(ts=e['ts'], text=norm(e['text'])[:80], chars=len(norm(e['text']))))
    shared = lambda x, y: bool(set(out['bots'][x]['group_chats']) & set(out['bots'][y]['group_chats']) - {''})
    strong_edges = {k: v for k, v in edges.items() if len({x['ts'][:10] for x in v}) >= 2 and not shared(*k)}
    comps = []
    for (x, y) in strong_edges:
        hit = [c for c in comps if x in c or y in c]
        merged = set().union({x, y}, *hit); comps = [c for c in comps if c not in hit] + [merged]
    cands = []
    for c in comps:
        es = [dict(src=x, to=y, src_name=names[x], to_name=names[y], count=len(v), days=sorted({i['ts'][:10] for i in v}), examples=v[:3])
              for (x, y), v in strong_edges.items() if x in c]
        flow = {b: sum(e['count'] for e in es if e['src'] == b) - sum(e['count'] for e in es if e['to'] == b) for b in c}
        lead = max(sorted(c), key=lambda b: flow[b])   # the most upstream bot: its answers start the chain
        order = sorted(c, key=lambda b: -flow[b])
        cands.append(dict(bots=order, bots_names=[names[b] for b in order], lead=lead, lead_name=names[lead], handoffs=es))
    out['fleet']['group_candidates'] = cands
    # ---- fleet: long or repetitive hand-offs (bot-to-bot messages, or answers the user pastes) -> a fixed short format
    byname = {v['name']: k for k, v in out['bots'].items()}
    hand, skipped_h = [], []
    for bid, tl in tls.items():
        msgs, raw, when = collections.defaultdict(list), collections.defaultdict(list), collections.defaultdict(list)
        for e in tl['events']:
            if e.get('kind') == 'agent' and e.get('sender') and norm(e.get('text')):
                msgs[e['sender']].append(norm(e['text'])); raw[e['sender']].append(e['text']); when[e['sender']].append(e.get('ts'))
        for snd, ms in msgs.items():
            if len(ms) < 3: continue
            tsl = sorted(P(t) for t in when[snd] if t)
            close = sum(1 for x, y in zip(tsl, tsl[1:]) if (y - x).total_seconds() <= BURST_MIN * 60)
            why_skip = 'template' if templated(raw[snd]) else 'burst' if len(tsl) >= 3 and close >= 0.5 * (len(tsl) - 1) else None
            if why_skip:   # a machine-made template or one fan-out run: already a fixed format, nothing to suggest
                skipped_h.append(dict(src_name=snd, to_name=names[bid], messages=len(ms), reason=why_skip)); continue
            rep_ = [jaccard(grams(x), grams(y)) for x, y in zip(ms, ms[1:])]
            med, rpt = median([len(x) for x in ms]), sum(rep_) / len(rep_)
            if med >= HANDOFF_LONG or (rpt >= 0.5 and med >= HANDOFF_PASTE / 2):   # short repeated pings are fine
                hand.append(dict(via='bot_message', src_name=snd, to_name=names[bid], src=byname.get(snd), to=bid, messages=len(ms),
                                 median_chars=int(med), repetitive=round(rpt, 2)))
    for (x, y), v in strong_edges.items():
        med = median([i['chars'] for i in v])
        if med >= HANDOFF_PASTE:
            hand.append(dict(via='pasted', src_name=names[x], to_name=names[y], src=x, to=y, messages=len(v), median_chars=int(med), repetitive=None))
    out['fleet']['handoff_format_candidates'] = hand
    out['fleet']['handoff_format_skipped'] = skipped_h
    # ---- fleet: group chats with the same members (only groups seen in the saved chats)
    members = collections.defaultdict(set); gdays = collections.defaultdict(set)
    for bid, b in out['bots'].items():
        for gname, days in b['group_chats'].items():
            if gname: members[gname].add(bid); gdays[gname].update(days)
    gl = sorted(members)
    out['fleet']['redundant_groups'] = [dict(groups=[g1, g2], bots=sorted(names[x] for x in members[g1]),
                                             last={g1: max(gdays[g1]), g2: max(gdays[g2])})
                                        for i, g1 in enumerate(gl) for g2 in gl[i + 1:] if len(members[g1]) >= 2 and members[g1] == members[g2]]
    # ---- suggested status (references/criteria.md §2); the host bot may override with a stated reason
    for bid, b in out['bots'].items():
        reasons = []
        if b['age_days'] >= 3 and b['idle_days'] >= max(3, b['age_days'] / 2) and (b['share'] < 0.05 or b['faded']) \
                and not b['too_new'] and not b['within_rhythm'] and not b['user_keep']:
            st = 'red'
            reasons.append('stopped: used about every {typical_gap_days} days, now idle {idle_days} days'.format(**b) if b['faded'] else
                           'barely used: idle {idle_days} of {age_days} days, under 5% of use'.format(**b))
        else:
            strong = [t for t, g in b['groups'].items() if g['strong']]
            own_waits = [w for w in b['waits'] if not w['fleet_outage']]
            if strong: reasons.append('repeated corrections not fixed: ' + ', '.join(strong))
            if own_waits: reasons.append(f'{len(own_waits)} unanswered request(s) not explained by a fleet outage')
            st = 'yellow' if reasons else 'green'
            if not reasons: reasons.append('no strong repeated problem')
            if b['user_keep']:
                reasons.append(f"paused by you: on {b['user_keep']['ts'][:10]} you said to keep it")
            if b['too_new']: reasons.append(f"too new to judge its use (first message {b['age_days']} days ago)")
            elif b['within_rhythm'] and b['idle_days'] >= max(3, b['age_days'] / 2):
                reasons.append(f"quiet for {b['idle_days']} days, within its usual rhythm (about every {b['typical_gap_days']} days)")
            if b['routine_active'] and b['idle_typed_days'] >= max(3, b['age_days'] / 2):
                reasons.append('used by its routine (last run ' + b['last_routine_run'] + ')')
        b['status_suggested'] = st; b['status_reasons'] = reasons
    dump_json(out, os.path.join(a.work, 'diag.json'))
    for bid, b in out['bots'].items():
        print(f"{b['name']}: {b['status_suggested']} ({'; '.join(b['status_reasons'])})")
    print('->', os.path.join(a.work, 'diag.json'))

if __name__ == '__main__':
    main()
