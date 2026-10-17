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

def clean_user(t):
    m = re.search(r'<user_query>(.*?)</user_query>', t, re.S)
    t = m.group(1) if m else t
    t = re.sub(r'\[t\w+\]|\[Sent from machine [^\]]+\]', '', t)
    t = re.sub(r'^\s*\[Answering your question [^\]]*\]\s*', '', t)
    return t.strip()

def grams(t):
    t = re.sub(r'\s+', '', norm(t).lower())
    return {t[i:i + 2] for i in range(len(t) - 1)}

def jaccard(a, b):
    return len(a & b) / max(1, len(a | b))

def load_json(p, default=None):
    if p and os.path.exists(p):
        with open(p, encoding='utf-8') as fh:
            return json.load(fh)
    return default

def dump_json(obj, p):
    os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
    with open(p, 'w', encoding='utf-8') as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1)

# ---------- cue phrases ----------
# A minimal English fallback so the pipeline runs without input. For other languages the host bot either writes
# W/cues.json with the same keys (added to these), or skips the cue filter and judges every reply itself
# (judge_inputs.py --all). See references/cues.md.
CUES_EN = {
    'directive': [r"\bno\b", r"\bnot (that|this|what)\b", r"\binstead\b", r"\bdon'?t\b", r"\bdo not\b", r"\bstop\b",
                  r"\bwrong\b", r"\bisn'?t\b", r"\bthat'?s not\b", r"\bi meant\b", r"\bi asked\b",
                  r"\btoo (long|short|much|many|formal|casual|complex|vague)\b", r"\balready\b", r"\bshorter\b", r"\bsimpler\b",
                  r"\bwhy didn'?t\b", r"\byou said\b", r"\bactually\b", r"\bagain\b", r"\bfrom now on\b",
                  r"\bplease (fix|change|remove)\b", r"\bremove\b", r"\bis that (all|right|correct)\b", r"\bare you sure\b"],
    'fix': [r"from now on", r"i'?ll remember", r"i'?ve (saved|updated|noted)", r"saved (that|this|it)",
            r"updated my (instructions|notes|guide|rules)", r"going forward"],
    'promise': [r"i'?ll (let you know|send|get back|report back|follow up)", r"working on it", r"give me a (moment|minute)", r"in progress"],
    'nudge': [r"^(hi|hello|hey)\b", r"^\?+$", r"^any update", r"^update\?", r"^status\?"],
    'timely': [r"\b(currently|now|at the moment|as of)\b"],
}

def load_cues(work):
    """Compiled cue patterns: English plus W/cues.json (if the host bot wrote one). Returns (patterns, has_custom)."""
    extra = load_json(os.path.join(work, 'cues.json'), {}) if work else {}
    pats = {}
    for k, base in CUES_EN.items():
        frags = list(base) + [str(x) for x in (extra.get(k) or []) if str(x).strip()]
        pats[k] = re.compile('(' + '|'.join(f'(?:{f})' for f in frags) + ')', re.I | re.M)
    return pats, bool(extra)
