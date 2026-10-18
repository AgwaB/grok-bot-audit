#!/usr/bin/env python3
"""Bot Audit, step 4: draft and finalize the findings JSON (schema: references/findings-schema.md).

  python3 build_findings.py skeleton --work W [--lang <BCP 47 code of the user's language, default en>]
      W/diag.json -> W/findings_draft.json: the frame you fill. One row per bot (status, issue and why left as TODO,
      no findings), the fleet keep / clean-up item, and the ui labels in English. You decide every status and write
      every finding from the facts in diag.json and the chats (references/criteria.md), in the user's language.
  python3 build_findings.py finalize --work W [--draft FILE] [--strict]
      Checks the structure (statuses, TODO and placeholder text, copy format), the evidence (every finding cites at
      least one real message by "ref"; every quote is found word for word, in the cited message when it has a ref) and
      the safety rules (a bot the user said to keep is never red; a red bot has exactly one clean-up item and only a
      red bot has one). Scores every proposal, keeps at most 3 per bot (rest -> "more"), picks the top 3, orders the
      rows by status -> W/findings.json and W/scores.md. --strict also fails on warnings.
"""
import argparse, math, os, re, sys, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import dump_json, has_app_text, load_json, norm, resolve_ref

CONF = {'high': 1.0, 'medium': 0.7, 'low': 0.4}
QUOTE_SPLIT = re.compile(r'\s*(?:…|\.\.\.)\s*')
STATUS_ORDER = {'yellow': 0, 'red': 1, 'green': 2}   # report rows: needs work, then clean-up candidates, then fine

def corpus(work):
    """Searchable text by source: chat (messages), memory (memory blocks), description (bot names and descriptions)."""
    chat, mem, desc = [], [], []
    for p in glob.glob(os.path.join(work, 'timelines', '*.json')):
        tl = load_json(p)
        chat += [e.get('text') or '' for e in tl['events'] if e.get('kind') != 'memory_write']
        mem += [e.get('text') or '' for e in tl['events'] if e.get('kind') == 'memory_write']
        if tl.get('memory'): mem.append(tl['memory']['text'])
    for b in load_json(os.path.join(work, 'bots.json'), []):
        desc += [b.get('name', ''), b.get('description', '')]
    c = {k: norm('\n'.join(v)) for k, v in (('chat', chat), ('memory', mem), ('description', desc))}
    c['any'] = '\n'.join(c.values())
    return c

SOURCES = ('chat', 'memory', 'description')

def T_(x):
    return ' '.join(map(str, x.values())) if isinstance(x, dict) else str(x or '')

def copy_texts(f):
    """A finding's paste text(s): "copy" is a string, or a list of {"bot": name, "text": ...} for several bots."""
    c = f.get('copy')
    if isinstance(c, list):
        return [str((x or {}).get('text') or '') if isinstance(x, dict) else str(x or '') for x in c]
    return [str(c)] if c else []

def skeleton(a):
    diag = load_json(os.path.join(a.work, 'diag.json'))
    order = sorted(diag['bots'].items(), key=lambda kv: -kv[1]['share'])
    bots = [dict(id=bid, name=b['name'], status='TODO', issue='TODO short issue', why='TODO one sentence: why this status',
                 improving=[], findings=[], needs_review=True) for bid, b in order]
    fleet = [dict(title='Keep / clean-up', keep=True, info=True, needs_review=True,
                  now=[dict(date='', text='TODO which bots to keep, which are clean-up candidates, and any you said to keep')],
                  fix='TODO nothing is deleted automatically; how the user cleans up (SKILL.md step 9), or that nothing needs it')]
    from make_report import UI_DEFAULT
    draft = dict(schema=3, lang=a.lang, title='Bot audit report', date=diag['now'][:10], date_label='TODO ' + diag['now'][:10],
                 ui=dict(UI_DEFAULT), bots=bots, fleet=fleet)
    draft['_skeleton'] = dict(lang='en', texts=sorted(set(placeholder_texts(draft))))
    dump_json(draft, os.path.join(a.work, 'findings_draft.json'))
    print(f'draft: {len(bots)} bots (status TODO), {len(fleet)} fleet item -> {os.path.join(a.work, "findings_draft.json")}')

VISIBLE = ('title', 'fix', 'short', 'issue', 'why', 'text', 'after', 'gloss')

def visible_strings(d):
    """(where, text) for every user-visible string the host bot writes (not quotes, names or ui labels)."""
    yield 'title', d.get('title', '')
    for b in d.get('bots', []):
        for k in ('issue', 'why', 'gloss'): yield f"{b.get('name')} / {k}", b.get(k) or ''
        for x in b.get('improving', []): yield f"{b.get('name')} / improving", x
    for b, f in iter_findings(d):
        w = (b['name'] if b else 'fleet') + ' / '
        for k in ('title', 'fix', 'short'): yield w + k, f.get(k) or ''
        for e in f.get('now', []):
            for k in ('text', 'after', 'who'):
                if isinstance(e.get(k), str) and k != 'who': yield w + 'evidence ' + k, e[k]
        for c in ([f['copy']] if isinstance(f.get('copy'), str) else [x.get('text', '') for x in f.get('copy') or [] if isinstance(x, dict)]):
            yield w + 'copy', c

def names_only(t, names):
    """True for a string made only of bot names, numbers and punctuation (nothing to translate)."""
    rest = t
    for n in sorted(names, key=len, reverse=True): rest = rest.replace(n, ' ')
    return not re.search(r'\w', re.sub(r'[\d_]', ' ', rest))

def placeholder_texts(d):
    names = [b.get('name', '') for b in d.get('bots', []) if b.get('name')]
    return [t for _, t in visible_strings(d) if isinstance(t, str) and len(t) > 3 and not t.startswith('TODO')
            and not names_only(t, names)]

def iter_findings(d):
    for b in d['bots']:
        for i, f in enumerate(b.get('findings', []) + b.get('more', []), 1):
            yield b, f
    for f in d.get('fleet', []):
        yield None, f

def finalize(a):
    draft = load_json(a.draft or os.path.join(a.work, 'findings_draft.json'))
    diag = load_json(os.path.join(a.work, 'diag.json'), {'bots': {}})
    text = corpus(a.work)
    errors, warns = [], []
    if 'TODO' in str(draft.get('date_label', '')): warns.append('date_label still has TODO (write the date as the reader writes it)')
    sk = draft.get('_skeleton') or {}
    if sk and str(draft.get('lang', 'en')).split('-')[0] != sk.get('lang', 'en'):
        left = set(sk.get('texts', []))
        names = [b.get('name', '') for b in draft.get('bots', []) if b.get('name')]
        for where, t in visible_strings(draft):
            if isinstance(t, str) and t in left and not names_only(t, names):
                warns.append(f'{where}: still the skeleton\'s placeholder text ("{t[:50]}"); write it in the report language')
        from make_report import UI_DEFAULT, placeholder_only
        same = [k for k, v in (draft.get('ui') or {}).items() if isinstance(v, str) and len(v) > 3 and v == UI_DEFAULT.get(k)
                and not placeholder_only(v)]
        if same: warns.append('ui labels still in the fallback language: ' + ', '.join(same[:12]))
    tls = {os.path.basename(p)[:-5]: load_json(p) for p in glob.glob(os.path.join(a.work, 'timelines', '*.json'))}
    known = {b.get('id') for b in draft['bots']}
    for bid in diag['bots']:
        if bid not in known: errors.append(f"{diag['bots'][bid]['name']}: no row for this bot (every audited bot is a row)")
    for b in draft['bots']:
        if b.get('status') not in ('green', 'yellow', 'red'):
            errors.append(f"{b.get('name')}: status must be green|yellow|red")
        uk = (diag['bots'].get(b.get('id')) or {}).get('user_keep')
        cleanups = [f for f in b.get('findings', []) + b.get('more', []) if f.get('cleanup')]
        if uk and (b.get('status') == 'red' or cleanups):
            errors.append(f"{b.get('name')}: the user said to keep it ({uk['ts'][:10]}, {uk.get('ref')}); no clean-up status or item (criteria.md §2)")
        elif b.get('status') == 'red' and len(cleanups) != 1:
            errors.append(f"{b.get('name')}: a clean-up bot needs exactly one finding with \"cleanup\": true (its one option)")
        elif b.get('status') != 'red' and cleanups:
            errors.append(f"{b.get('name')}: only a clean-up (red) bot has a \"cleanup\" finding")
        if b.get('needs_review'): warns.append(f"{b['name']}: bot entry still needs review")
        for k in ('issue', 'why'):
            v = b.get(k)
            if 'TODO' in (' '.join(map(str, v.values())) if isinstance(v, dict) else str(v or '')):
                warns.append(f"{b['name']}: {k} still has TODO")
    for b, f in iter_findings(draft):
        ti = f.get('title'); ti = next(iter(ti.values()), '') if isinstance(ti, dict) else ti
        where = (b['name'] if b else 'fleet') + ' / ' + str(ti)
        if f.get('needs_review'): warns.append(where + ': needs review')
        refs = [e.get('ref') for e in f.get('now', []) if e.get('ref')]
        for r in refs:
            if resolve_ref(r, tls)[1] is None: errors.append(f'{where}: ref "{r}" is not a message id in the saved chats')
        has_events = not b or any(tl['events'] for k, tl in tls.items() if k == b.get('id'))
        if not f.get('keep') and not refs and has_events:
            errors.append(where + ': cite at least one message: add "ref" (a message id) to an evidence line')
        c = f.get('copy')
        if isinstance(c, list) and not all(isinstance(x, dict) and x.get('bot') and x.get('text') for x in c):
            errors.append(where + ': "copy" as a list needs {"bot", "text"} in every item')
        if any('TODO' in t for t in copy_texts(f)): warns.append(where + ': copy still has TODO')
        if f.get('kind') == 'group':
            g = f.get('group') or {}
            if 'TODO' in str(g) or not g.get('lead') or not g.get('members') or g.get('blocked') != 'ask_user':
                warns.append(where + ': group needs project, lead, each member\'s part and blocked = ask_user (setup.md)')
        for ls in f.get('lessons') or []:
            if 'TODO' in str(ls.get('copy', '')): warns.append(where + ': a lesson text still has TODO')
        rv = f.get('review')
        if rv is not None and 'TODO' in str(rv.get('copy') if isinstance(rv, dict) else rv):
            warns.append(where + ': review routine text still has TODO')
        if any('TODO' in T_(f.get(k)) for k in ('title', 'fix', 'short')): warns.append(where + ': title, fix or short still has TODO')
        for e in f.get('now', []):
            q = e.get('quote')
            if not b and isinstance(e.get('who'), str) and e['who'].strip().lower() == 'bot':
                errors.append(where + ': "who": "bot" means this bot, but a fleet item has none; write that bot\'s name in "who"')
            if q and e.get('text'):
                errors.append(where + ': an evidence line has both "quote" and "text"; use two lines'); continue
            if not q: continue
            orig = q.get('orig') if isinstance(q, dict) else q
            if not orig:
                errors.append(where + ': quote without "orig" (the exact original words)'); continue
            src = e.get('source') or 'chat'
            if src not in SOURCES:
                errors.append(f'{where}: "source" must be one of {", ".join(SOURCES)}'); continue
            ev_ = resolve_ref(e.get('ref'), tls)[1] if e.get('ref') else None
            if ev_ is not None and (src == 'chat' or ev_.get('kind') == 'memory_write'):
                body = norm(ev_.get('text'))
                miss = next((x for x in QUOTE_SPLIT.split(norm(orig)) if len(x) >= 2 and x not in body), None)
                if miss:
                    hint = ' (it is in a memory or description: set "source")' if src == 'chat' and miss in text['any'] else ''
                    errors.append(f'{where}: quote not found word for word in message {e["ref"]}: "{miss[:60]}"{hint}')
                continue
            if has_app_text(orig):
                errors.append(f'{where}: quote contains a file path or an app notice; quote only words people wrote: "{norm(orig)[:60]}"'); continue
            for seg in [s for s in QUOTE_SPLIT.split(norm(orig)) if len(s) >= 2]:
                if seg not in text[src]:
                    hint = '' if src != 'chat' or seg not in text['any'] else ' (it is in a memory or description: set "source")'
                    errors.append(f'{where}: quote not found word for word in the saved {src if src != "chat" else "chats"}: "{seg[:60]}"{hint}'); break
    # scores, cap, top 3
    share = {bid: b['share'] for bid, b in diag['bots'].items()}
    cands = []
    for b in draft['bots']:
        allf = b.get('findings', []) + b.get('more', [])
        scored = [f for f in allf if f.get('score') and not f.get('see') and not f.get('info')]
        for f in scored:
            s = f['score']
            s['value'] = round(s['impact'] * CONF.get(s.get('confidence', 'medium'), 0.7) * s.get('reversibility', 1.0) / math.sqrt(s.get('effort', 1)), 2)
        scored.sort(key=lambda f: -f['score']['value'])
        rest = [f for f in allf if f not in scored]
        b['findings'], b['more'] = scored[:3] + rest, scored[3:]
        for i, f in enumerate(b['findings'], 1):
            if f in scored: cands.append((f['score']['value'], share.get(b['id'], 0), f"{b['id']}-{i}", f))
    for i, f in enumerate(draft.get('fleet', []), 1):
        if f.get('score') and not f.get('info'):
            s = f['score']; s['value'] = round(s['impact'] * CONF.get(s.get('confidence', 'medium'), 0.7) * s.get('reversibility', 1.0) / math.sqrt(s.get('effort', 1)), 2)
            cands.append((s['value'], 1.0, f'fleet-{i}', f))
    cands.sort(key=lambda x: (-x[0], -x[1]))
    if not draft.get('top3_locked'):
        draft['top3'] = [dict(text=f.get('short') or f['title'], ref=r) for _, _, r, f in cands[:3]]
    draft.pop('leads', None); draft.pop('_skeleton', None)
    for _, f in iter_findings(draft):   # an optional review routine or lesson the host didn't write is dropped
        if 'review' in f and not (isinstance(f['review'], dict) and str(f['review'].get('copy') or '').strip()): f.pop('review')
        if 'lessons' in f:
            f['lessons'] = [x for x in f['lessons'] if isinstance(x, dict) and str(x.get('copy') or '').strip()]
            if not f['lessons']: f.pop('lessons')
    # rows in status order (needs work, clean-up, fine), keeping the draft's order within a status
    draft['bots'] = [b for _, b in sorted(enumerate(draft['bots']), key=lambda ib: (STATUS_ORDER.get(ib[1].get('status'), 3), ib[0]))]
    with open(os.path.join(a.work, 'scores.md'), 'w', encoding='utf-8') as fh:
        fh.write('| rank | ref | title | score | impact | confidence | effort | reversibility | basis |\n|---|---|---|---|---|---|---|---|---|\n')
        for k, (v, _, r, f) in enumerate(cands, 1):
            s = f['score']; t = next(iter(f['title'].values()), '') if isinstance(f['title'], dict) else f['title']
            fh.write(f"| {k} | {r} | {t} | {v} | {s['impact']} | {s.get('confidence')} | {s.get('effort')} | {s.get('reversibility')} | {s.get('basis', '')} |\n")
    for w in warns: print('WARN', w)
    for e in errors: print('ERROR', e)
    if errors or (a.strict and warns):
        sys.exit(1)
    dump_json(draft, os.path.join(a.work, 'findings.json'))
    print(f"findings -> {os.path.join(a.work, 'findings.json')}; top 3: {[x['ref'] for x in draft['top3']]}")

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    p = sp.add_parser('skeleton'); p.add_argument('--work', required=True); p.add_argument('--lang', default='en', help='BCP 47 code of the report language (the user'"'"'s language)')
    p.set_defaults(fn=skeleton)
    p = sp.add_parser('finalize'); p.add_argument('--work', required=True); p.add_argument('--draft'); p.add_argument('--strict', action='store_true')
    p.set_defaults(fn=finalize)
    a = ap.parse_args(); a.fn(a)

if __name__ == '__main__':
    main()
