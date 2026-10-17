#!/usr/bin/env python3
"""Bot Audit, step 4: draft and finalize the findings JSON (schema: references/findings-schema.md).

  python3 build_findings.py skeleton --work W [--lang <BCP 47 code of the user's language, default en>]
      W/diag.json (+ timelines, labels) -> W/findings_draft.json
      A starting point: statuses from the criteria, one draft finding per repeated correction group or
      repeated request, verbatim evidence quotes, and "leads" to check. Memory saves after a group started
      are listed in the finding's "fix_check" by id (texts once per bot in "fix_candidates"; unverified) for the host bot to confirm or drop. Items marked needs_review=true
      carry placeholder English text. The host bot writes all wording in the user's language (text fields,
      "ui" labels, "date_label", quote translations), drops noise, and removes needs_review.
  python3 build_findings.py finalize --work W [--draft FILE] [--strict]
      Validates (statuses, quotes must appear word for word in the saved chats, memory or descriptions),
      scores every proposal, keeps at most 3 per bot (rest -> "more"), picks the top 3 -> W/findings.json
      and W/scores.md. --strict fails when needs_review items remain.
"""
import argparse, math, os, re, sys, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import dump_json, has_app_text, load_json, norm

CONF = {'high': 1.0, 'medium': 0.7, 'low': 0.4}
TOPIC = {  # title, fix
 'tone_style': ('Tone and wording fixes keep coming up', 'Save the tone rule so you stop repeating it.'),
 'format_length': ('Format and length fixes keep coming up', 'Save the format you want as a default.'),
 'scope_selection': ('It picks the wrong topics or items', 'Write down what to include and what to skip.'),
 'accuracy_sources': ('Facts or sources needed fixing more than once', 'Make checking the source a default step.'),
 'misread_intent': ('It misreads what you asked for', 'Have it confirm in one line when a request is ambiguous.'),
 'repeated_content': ('It repeats things you already have', 'Have it check what you already have first.'),
 'method_choice': ('It keeps choosing a different way to do it', 'Write down the way you want it done.'),
 'depth_completeness': ('It stops short of what you asked', 'Have it say up front if it cannot do everything.'),
 'missing_context': ('It lacks a fact about your situation', 'Add the missing fact to its memory.'),
 'other': ('The same correction keeps coming up', 'Save a rule so it stops repeating.'),
}
QUOTE_SPLIT = re.compile(r'\s*(?:…|\.\.\.)\s*')

def impact_from(n_inc, days=0, bots=1, recurred=False):
    i = 3 if (n_inc >= 4 or days >= 5 or bots >= 3) else 2 if (n_inc >= 2 or days >= 3 or bots >= 2) else 1
    return min(3, i + (1 if recurred else 0))

def corpus(work, diag=None):
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

def copy_texts(f):
    """A finding's paste text(s): "copy" is a string, or a list of {"bot": name, "text": ...} for several bots."""
    c = f.get('copy')
    if isinstance(c, list):
        return [str((x or {}).get('text') or '') if isinstance(x, dict) else str(x or '') for x in c]
    return [str(c)] if c else []

SENT_RE = re.compile(r'(?<=[.!?\u3002\uff01\uff1f])\s+|\n+')

def md(ts):
    """'YYYY-MM-DD…' -> 'MM/DD' (the skeleton's one date format; the host bot may localize it)."""
    return ts[5:10].replace('-', '/') if ts and len(ts) >= 10 else ''

def pick_quote(text, evidence='', n=200):
    """Evidence quote for a message: the sentence holding the judge's evidence words if found, else the whole message
    if short, else its first sentences up to n characters (never cut mid-sentence when a boundary exists)."""
    t = norm(text)
    if len(t) <= n:
        return t
    parts = [norm(x) for x in SENT_RE.split(text or '') if norm(x)]
    ev = norm(re.sub(r'^["\'\u201c\u300c]+|["\'\u201d\u300d]+$', '', evidence or ''))
    if ev:
        hit = next((x for x in parts if ev in x), None)
        if hit: return hit if len(hit) <= n * 2 else hit[:n]
    out = ''
    for x in parts:
        if len(out) + len(x) + 1 > n: break
        out = (out + ' ' + x).strip()
    return out or t[:n]

def skeleton(a):
    diag = load_json(os.path.join(a.work, 'diag.json')); jin = {x['key']: x for x in load_json(os.path.join(a.work, 'judge_inputs.json'), [])}
    tls = {os.path.basename(p)[:-5]: load_json(p) for p in glob.glob(os.path.join(a.work, 'timelines', '*.json'))}
    lang = a.lang
    def txt(key):
        bid, i = key.split(':'); return tls[bid]['events'][int(i)]['text']
    order = sorted(diag['bots'].items(), key=lambda kv: -kv[1]['share'])
    bots, fleet, empty = [], [], []
    for bid, b in order:
        findings, improving = [], []
        for topic, g in sorted(b['groups'].items(), key=lambda kv: -kv[1]['incidents']):
            if not g['repeated']:
                continue
            title, fix = TOPIC.get(topic, TOPIC['other'])
            labels = load_json(os.path.join(a.work, 'labels.json'), {})
            ev = [dict(date=md(jin.get(k, {}).get('ts')), quote={'orig': pick_quote(txt(k), labels.get(k, {}).get('evidence', ''))})
                  for k in g['keys'][:4]]
            conf = 'high' if g['confidences'].count('high') >= max(1, len(g['confidences']) // 2) else 'medium'
            item = dict(title=title, now=ev, fix=fix, copy=None, copy_kind='memory', needs_review=True, topic=topic,
                        score=dict(impact=impact_from(g['incidents']), confidence=conf, effort=1, reversibility=1.0,
                                   basis=f"{g['incidents']} incidents on {g['sessions']} separate occasions"))
            if g.get('fix_candidates'):
                # unverified: the host bot decides whether any of these is about this problem (references/writing.md)
                item['fix_check'] = g['fix_candidates']
            if g.get('fix_candidates_omitted'):
                # more saves than are listed, all with no incident after them: the timeline has the rest (kind memory_write)
                item['fix_check_omitted'] = g['fix_candidates_omitted']
            findings.append(item)
        for r in b['repeated_requests'][:1]:
            if len(r['days']) >= 3:
                findings.append(dict(title='You ask for the same thing by hand on many days',
                                     now=[dict(date=f"{md(r['days'][0])}~{md(r['days'][-1])}", quote={'orig': pick_quote(t)}) for t in r['examples'][:3]],
                                     fix='A routine could do this on a schedule. Check the routines page in the app first.',
                                     copy=None, copy_kind='routine', needs_review=True,
                                     score=dict(impact=impact_from(0, days=len(r['days'])), confidence='medium', effort=2, reversibility=1.0,
                                                basis=f"similar request on {len(r['days'])} days")))
        if b['description_empty'] and b['status_suggested'] != 'red':
            empty.append(bid)
            findings.append(dict(title='The description is empty', now=[], fix='See the shared description item.',
                                 see='fleet-1'))
        why = {'red': 'Barely used for most of its life, and a very small part of your overall use.',
               'yellow': 'The same correction keeps coming back.' if any(g['strong'] for g in b['groups'].values())
                         else 'Some requests went unanswered.',
               'green': 'No repeated problem.'}[b['status_suggested']]
        if b['status_suggested'] == 'red':
            findings = [dict(title='Barely used', cleanup=True, now=[dict(date='', text=f"Last request {md(b['last_request'])}")],
                             fix='Consider cleaning it up, or moving its job to a bot you use. How: see the keep / clean-up item.',
                             needs_review=True, score=dict(impact=1, confidence='medium', effort=1, reversibility=0.6, basis='idle; small share'))] + findings
        own = [w for w in b['waits'] if not w['fleet_outage'] and w['texts']]
        if own:   # unanswered requests: information, not a scored proposal
            findings.append(dict(title='Some requests went unanswered', info=True, needs_review=True,
                                 now=[dict(date=md(w['first']), quote={'orig': pick_quote(w['texts'][0])}) for w in own[:3]],
                                 fix='It went quiet for hours after these messages. Check whether it was busy or stuck.'))
        bots.append(dict(id=bid, name=b['name'], status=b['status_suggested'], issue='TODO short issue', why=why,
                         improving=improving, findings=findings, needs_review=True,
                         **({'fix_candidates': b['fix_candidates']} if b.get('fix_candidates') and any('fix_check' in f for f in findings) else {})))
    if empty:
        fleet.append(dict(title=f'Bots with no description: {len(empty)}',
                          now=[dict(date='', text=', '.join(diag['bots'][x]['name'] for x in empty))],
                          fix='Paste a short description into each bot, written from how you actually use it.',
                          copy=[dict(bot=diag['bots'][x]['name'], text='TODO description') for x in empty],
                          copy_kind='description', needs_review=True,
                          score=dict(impact=impact_from(0, bots=len(empty)), confidence='medium', effort=1, reversibility=1.0, basis=f'{len(empty)} bots')))
    for o in diag['fleet']['outages']:
        fleet.append(dict(title='Several bots stopped answering at the same time',
                          now=[dict(date=md(w['first']), who=diag['bots'][w['bot']]['name'], quote={'orig': pick_quote(w['texts'][0])})
                               for w in o['waits'][:4] if w['texts']],
                          fix='It happened once, so nothing to change. The next audit will flag it if it happens again.',
                          info=True))
    keep = [b['name'] for b in bots if b['status'] != 'red']; drop = [b['name'] for b in bots if b['status'] == 'red']
    fleet.append(dict(title='Keep / clean-up candidates',
                      now=[dict(date='', text='Keep: ' + ', '.join(keep))] +
                          ([dict(date='', text='Clean-up candidates: ' + ', '.join(drop))] if drop else []),
                      fix='Nothing is deleted automatically. Check in the app that a bot has no routines; then you can delete it yourself '
                          '(right-click the bot in the sidebar and choose Delete).', info=True))
    leads = dict(preferences=[], memory={}, promises={}, skipped_questions={}, similar_requests=diag['fleet']['similar_requests_candidates'][:10],
                 other_bots_job=diag['fleet']['other_bots_job_candidates'][:10])
    for bid, b in diag['bots'].items():
        if b['memory'] and (b['memory']['time_sensitive'] or b['memory']['near_duplicates']):
            leads['memory'][bid] = dict(time_sensitive=b['memory']['time_sensitive'], near_duplicates=b['memory']['near_duplicates'])
        if b['promise_candidates']: leads['promises'][bid] = b['promise_candidates']
        if b['skipped_questions']['count']:
            leads['skipped_questions'][bid] = dict(count=b['skipped_questions']['count'], questions=b['skipped_questions']['questions'])
        leads['preferences'] += [norm(txt(k))[:120] for k in b['preferences'] if k in jin]
    from make_report import UI_DEFAULT
    draft = dict(schema=3, lang=lang, title='Bot audit report', date=diag['now'][:10], date_label='TODO ' + diag['now'][:10],
                 ui=dict(UI_DEFAULT), bots=bots, fleet=fleet, leads=leads)
    draft['_skeleton'] = dict(lang='en', texts=sorted(set(placeholder_texts(draft))))
    dump_json(draft, os.path.join(a.work, 'findings_draft.json'))
    n = sum(len(b['findings']) for b in bots)
    print(f'draft: {len(bots)} bots, {n} bot findings, {len(fleet)} fleet items -> {os.path.join(a.work, "findings_draft.json")}')

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
    text = corpus(a.work, diag)
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
    for b in draft['bots']:
        if b.get('status') not in ('green', 'yellow', 'red'):
            errors.append(f"{b.get('name')}: status must be green|yellow|red")
        if b.get('needs_review'): warns.append(f"{b['name']}: bot entry still needs review")
        for k in ('issue',):
            v = b.get(k)
            if 'TODO' in (' '.join(map(str, v.values())) if isinstance(v, dict) else str(v or '')):
                warns.append(f"{b['name']}: {k} still has TODO")
    for b, f in iter_findings(draft):
        ti = f.get('title'); ti = next(iter(ti.values()), '') if isinstance(ti, dict) else ti
        where = (b['name'] if b else 'fleet') + ' / ' + str(ti)
        if f.get('needs_review'): warns.append(where + ': needs review')
        if 'fix_check' in f: warns.append(where + ': fix_check not resolved (confirm or drop the fix, then delete fix_check)')
        c = f.get('copy')
        if isinstance(c, list) and not all(isinstance(x, dict) and x.get('bot') and x.get('text') for x in c):
            errors.append(where + ': "copy" as a list needs {"bot", "text"} in every item')
        if any('TODO' in t for t in copy_texts(f)): warns.append(where + ': copy still has TODO')
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
    for b in draft.get('bots', []):
        b.pop('fix_candidates', None)
        for f in b.get('findings', []) + b.get('more', []): f.pop('fix_check_omitted', None)
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
