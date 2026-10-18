"""Test helpers: play the host bot's part on the skeleton (decide statuses, write findings with message ids)."""
import glob, json, os

def timelines(W):
    return {os.path.basename(p)[:-5]: json.load(open(p)) for p in glob.glob(os.path.join(W, 'timelines', '*.json'))}

def ref_of(W, bot, text, role='user'):
    """The message id ("<prefix>:<i>") of the first event in this bot's chat (id or name) whose text contains `text`."""
    d = json.load(open(os.path.join(W, 'diag.json')))
    for bid, tl in timelines(W).items():
        if bot in (bid, tl['name'], None):
            e = next((e for e in tl['events'] if text in (e.get('text') or '') and (role is None or e['role'] == role)), None)
            if e: return f"{d['bots'][bid]['ref_prefix']}:{e['i']}"
    raise KeyError(f'{bot}: {text}')

def any_ref(W, bot):
    """A message id of this bot's last typed message (or any event)."""
    d = json.load(open(os.path.join(W, 'diag.json'))); b = next(v for k, v in d['bots'].items() if bot in (k, v['name']))
    if b['last_request_ref']: return b['last_request_ref']
    bid = next(k for k, v in d['bots'].items() if v is b)
    return f"{b['ref_prefix']}:{timelines(W)[bid]['events'][0]['i']}"

def fill(W, status=None, findings=None, fleet=None, lang=None):
    """Load the skeleton, set statuses (default green) and plain text, add findings {bot name: [finding]}, add fleet
    items, clear review flags, write the draft back, and return it."""
    p = os.path.join(W, 'findings_draft.json'); dr = json.load(open(p))
    status, findings = status or {}, findings or {}
    dr['date_label'] = dr['date']
    if lang: dr['lang'] = lang
    for b in dr['bots']:
        b['status'] = status.get(b['name'], 'green'); b['issue'] = f"Test issue for {b['name']}"
        b['why'] = f"Test reason for {b['name']}."; b.pop('needs_review', None)
        b['findings'] = list(findings.get(b['name'], []))
    keep = dr['fleet'][0]; keep.pop('needs_review', None)
    keep['title'] = 'Keep / clean-up (test)'; keep['now'] = [dict(date='', text='Keep: test bots (test)')]; keep['fix'] = 'Nothing is deleted automatically (test).'
    dr['fleet'] += list(fleet or [])
    json.dump(dr, open(p, 'w'), ensure_ascii=False)
    return dr

def finding(title, ref, quote=None, **kw):
    """A scored proposal citing one message (quoted when `quote` is given)."""
    ev = dict(date='03/01', ref=ref, **({'quote': {'orig': quote}} if quote else {'text': 'Test fact line'}))
    f = dict(title=title, now=[ev], fix='Pick this and a rule is saved (test).', copy='Test rule text (fake).', copy_kind='memory',
             score=dict(impact=2, confidence='high', effort=1, reversibility=1.0, basis='test'))
    f.update(kw); return f
