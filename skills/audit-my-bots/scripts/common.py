"""Shared helpers for the Bot Audit scripts. Standard library only."""
import datetime as dt, glob, hashlib, json, os, re

AGENTS_DIR = os.environ.get('BOT_AUDIT_AGENTS_DIR', '/home/box/agent-data/agents')
TS_RE = re.compile(r'<timestamp>\s*\w+,\s*(\w{3})\w*\s+(\d{1,2}),\s*(\d{4}),\s*(\d{1,2}):(\d{2})\s*([AP]M)\s*\(UTC([+-]\d{1,2}(?::\d{2})?)?\)\s*</timestamp>')
MONTHS = {m: i for i, m in enumerate(['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'], 1)}
HEADER_RE = re.compile(r'positions\s+(\d+)\D+(\d+)\s+of\s+(\d+)')

def norm(s):
    return re.sub(r'\s+', ' ', s or '').strip()

def parse_ts(text):
    """Parse the app's <timestamp> tag into an aware datetime, or None."""
    m = TS_RE.search(text or '')
    if not m:
        return None
    mon, day, year, hh, mm, ap, off = m.groups()
    h = int(hh) % 12 + (12 if ap == 'PM' else 0)
    oh, om = 0, 0
    if off:
        sign = -1 if off.startswith('-') else 1
        parts = off.lstrip('+-').split(':')
        oh, om = sign * int(parts[0]), sign * (int(parts[1]) if len(parts) > 1 else 0)
    tz = dt.timezone(dt.timedelta(hours=oh, minutes=om))
    return dt.datetime(int(year), MONTHS.get(mon[:3], 1), int(day), h, int(mm), tzinfo=tz)

def page_start(path):
    """Start position from a saved ReadTranscript page header ("positions A–B of N")."""
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            m = HEADER_RE.search(line)
            if m:
                return int(m.group(1)), int(m.group(2)), int(m.group(3))
    return None

def load_pages(d):
    """Read page_*.txt files (ReadTranscript output) and return de-duplicated JSON entries in order."""
    pages = []
    for f in glob.glob(os.path.join(d, 'page_*.txt')):
        lines = open(f, encoding='utf-8').read().splitlines()
        info = page_start(f) or (0, -1, -1)
        pages.append((info, [l for l in lines if l.startswith('{')]))
    pages.sort(key=lambda p: p[0][0])
    seen, out = set(), []
    for _, lines in pages:
        for l in lines:
            h = hashlib.sha1(l.encode()).hexdigest()
            if h in seen:
                continue
            seen.add(h)
            try:
                out.append(json.loads(l))
            except ValueError:
                continue
    covered = sorted((p[0][0], p[0][1]) for p in pages if p[0][1] >= 0)
    total = max((p[0][2] for p in pages), default=-1)
    complete = bool(covered) and covered[0][0] == 0 and covered[-1][1] >= total - 1
    return out, dict(pages=len(pages), entries=len(out), total_positions=total, starts_at_zero=bool(covered) and covered[0][0] == 0,
                     complete=complete)

def tool_input(x):
    i = x.get('input')
    if isinstance(i, dict):
        return i
    try:
        v = json.JSONDecoder().raw_decode(str(i).strip())[0]
        return v if isinstance(v, dict) else {}
    except Exception:
        return {}

def call_args(i):
    a = i.get('arguments')
    if isinstance(a, str):
        try:
            return json.JSONDecoder().raw_decode(a.strip())[0]
        except Exception:
            return {}
    return a or {}

def user_kind(t):
    if 'GROK_BOT_HIDDEN_PROMPT' in t or 'SAND_HIDDEN_PROMPT' in t:
        if '[routine]' in t: return 'routine'
        if 'background task' in t.lower(): return 'background_result'
        if '[agent] A message just arrived' in t: return 'agent'
        if 'moved on without responding' in t: return 'skipped_question'
        if 'submitted the form' in t: return 'form_submit'
        if '[first run]' in t: return 'first_run'
        return 'hidden_other'
    if '<memory_context>' in t: return 'context_injection'
    if '<agent_profile_update>' in t: return 'profile_update'
    if '<user_query>' in t: return 'real'
    return 'other'

# Text the app itself adds inside a user message (not typed by the user). These follow the app's fixed transcript
# format, like the <timestamp> tag, so they are matched by shape: a notice line that starts "The user attached/shared…"
# followed by "- <path> …" lines, and any absolute file path. Removed before similarity checks, candidate extraction and
# quote checks, so they can't become leads or quotes.
APP_NOTICE_RE = re.compile(r'^[ \t]*The user (?:attached|shared|uploaded|sent|added) (?:a |an |the |some )?(?:file|files|image|images|attachment|attachments)\b.*$', re.M | re.I)
NOTICE_ITEM_RE = re.compile(r'^[ \t]*[-*•][ \t]*(?:/|[A-Za-z]:\\)\S*.*$', re.M)
# A folder name may hold spaces ("/Users/me/My Project/notes.md"): a part with up to 3 more words counts when another
# "/" follows it and each extra word starts with a capital, a digit or a non-Latin letter ("My Project", "2024 Taxes";
# not "/usr/bin and/or"); a last part with spaces only when it ends in a file extension. The sentence after a path stays.
_SEG = r'[\w.@%+=-]+'
_MID = r'/' + _SEG + r'(?: (?![a-z])' + _SEG + r'){0,3}(?=/)'
PATH_RE = re.compile(r'(?<![\w:/.~])(?:~|[A-Za-z]:)?(?:(?:' + _MID + r'){2,}/(?!\w)|(?:' + _MID + r')+/' + _SEG
                     + r'(?:(?: [\w@%+=-]+){1,3}\.[A-Za-z0-9]{1,6}\b)?/?)|(?<![\w])[A-Za-z]:\\(?:[\w.@ -]+\\)*[\w.@-]+')

def strip_app_text(t):
    """Remove app-injected notices and file paths. Returns (clean text, number of notices removed)."""
    n = len(APP_NOTICE_RE.findall(t or ''))
    t = APP_NOTICE_RE.sub('', t or '')
    t = NOTICE_ITEM_RE.sub('', t)
    t = PATH_RE.sub('', t)
    t = re.sub(r'[ \t]{2,}', ' ', t)
    t = re.sub(r'[ \t]+\n', '\n', t)
    return re.sub(r'\n{3,}', '\n\n', t).strip(), n

def has_app_text(t):
    """True if a text still carries an app notice or a file path (never allowed in quotes)."""
    return bool(APP_NOTICE_RE.search(t or '') or PATH_RE.search(t or ''))

def clean_user(t, with_meta=False):
    m = re.search(r'<user_query>(.*?)</user_query>', t, re.S)
    t = m.group(1) if m else t
    t = re.sub(r'\[t\w+\]|\[Sent from machine [^\]]+\]', '', t)
    t = re.sub(r'^\s*\[Answering your question [^\]]*\]\s*', '', t)
    t, n = strip_app_text(t)
    return (t, n) if with_meta else t

def grams(t):
    t = re.sub(r'\s+', '', norm(t).lower())
    return {t[i:i + 2] for i in range(len(t) - 1)}

def load_json(p, default=None):
    if p and os.path.exists(p):
        with open(p, encoding='utf-8') as fh:
            return json.load(fh)
    return default

def dump_json(obj, p):
    os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
    with open(p, 'w', encoding='utf-8') as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1)

# ---------- message ids ----------
FMT = '%Y-%m-%d %H:%M'
P = lambda s: dt.datetime.strptime(s, FMT)
RESEND_MIN = 30   # the same text sent again this soon is a resend (one request)

def short_ids(ids):
    """{bot id: shortest prefix (4+ characters) that no other bot id starts with}. A message id ("ref") is
    "<prefix>:<i>", i = the event's index in that bot's timeline."""
    ids = list(ids); out = {}
    for x in ids:
        n = min(4, len(x))
        while n < len(x) and any(y != x and y.startswith(x[:n]) for y in ids): n += 1
        out[x] = x[:n]
    return out

def resolve_ref(ref, tls):
    """(timeline, event) for a message id "<bot id or unique prefix>:<i>", or (None, None)."""
    bid, _, i = str(ref or '').rpartition(':')
    if not bid or not i.isdigit(): return None, None
    hits = [tl for k, tl in tls.items() if k == bid] or [tl for k, tl in tls.items() if len(bid) >= 4 and k.startswith(bid)]
    if len(hits) != 1: return None, None
    ev = next((e for e in hits[0]['events'] if e.get('i') == int(i)), None)
    return (hits[0], ev) if ev else (None, None)
