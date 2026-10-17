#!/usr/bin/env python3
"""Bot Audit, step 4: draft and finalize the findings JSON (schema: references/findings-schema.md).

  python3 build_findings.py skeleton --work W [--lang <BCP 47 code, default en>]
      W/diag.json (+ timelines, labels) -> W/findings_draft.json
      A starting point: statuses from the criteria, one draft finding per repeated correction group or
      repeated request, verbatim evidence quotes, and "leads" to check. Items marked needs_review=true
      carry generic English text; the host bot rewrites title/fix/copy in plain words in the report language,
      adds quote translations where the chat language differs, drops noise, and removes needs_review.
      With a non-English --lang the draft also has "translate": true and a "ui" object of English labels;
      the host bot translates every text field and label, then deletes "translate".
  python3 build_findings.py finalize --work W [--draft FILE] [--strict]
      Validates (statuses, quotes must appear word for word in the saved chats, memory or descriptions),
      scores every proposal, keeps at most 3 per bot (rest -> "more"), picks the top 3 -> W/findings.json
      and W/scores.md. --strict fails when needs_review items remain.
"""
import argparse, math, os, re, sys, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import dump_json, load_json, norm

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

def corpus(work, diag):
    parts = []
    for p in glob.glob(os.path.join(work, 'timelines', '*.json')):
        tl = load_json(p)
        parts += [e.get('text') or '' for e in tl['events']]
        if tl.get('memory'): parts.append(tl['memory']['text'])
    for b in load_json(os.path.join(work, 'bots.json'), []):
        parts += [b.get('name', ''), b.get('description', '')]
    return norm('\n'.join(parts))

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
            if g['possibly_fixed']:
                improving.append(f'{title}: the bot recorded a fix on {g["fixes_after_last"][0]["ts"][5:10]} and it has not come back')
                continue
            ev = [dict(date=jin[k]['ts'][5:10].replace('-', '/') if jin.get(k, {}).get('ts') else '', quote={'orig': norm(txt(k))[:200]})
                  for k in g['keys'][:4]]
            conf = 'high' if g['confidences'].count('high') >= max(1, len(g['confidences']) // 2) else 'medium'
            findings.append(dict(title=title, now=ev, fix=fix, copy=None, copy_kind='memory', needs_review=True, topic=topic,
                                 score=dict(impact=impact_from(g['incidents'], recurred=g['recurred_after_fix']), confidence=conf,
                                            effort=1, reversibility=1.0,
                                            basis=f"{g['incidents']} incidents on {len(g['days'])} days" + (' (came back after a fix)' if g['recurred_after_fix'] else ''))))
        for r in b['repeated_requests'][:1]:
            if len(r['days']) >= 3:
                findings.append(dict(title='You ask for the same thing by hand on many days',
                                     now=[dict(date=f"{r['days'][0][5:]}~{r['days'][-1][5:]}".replace('-', '/'), quote={'orig': t}) for t in r['examples'][:3]],
                                     fix='A routine could do this on a schedule. Check the routines page in the app first.',
                                     copy=None, copy_kind='routine', needs_review=True,
                                     score=dict(impact=impact_from(0, days=len(r['days'])), confidence='medium', effort=2, reversibility=1.0,
                                                basis=f"similar request on {len(r['days'])} days")))
        if b['description_empty'] and b['status_suggested'] != 'red':
            empty.append(bid)
            findings.append(dict(title='The description is empty', now=[], fix='See the shared description item.',
                                 see='fleet-1'))
        why = {'red': 'Barely used for most of its life, and a very small part of your overall use.',
               'yellow': 'The same correction keeps coming back.',
               'green': 'No repeated problem.'}[b['status_suggested']]
        if b['status_suggested'] == 'red':
            findings = [dict(title='Barely used', now=[dict(date='', text=f"Last request {(b['last_request'] or '')[5:10]}")],
                             fix='Consider merging it into another bot or removing it. Check its routines in the app first; nothing is deleted automatically.',
                             needs_review=True, score=dict(impact=1, confidence='medium', effort=1, reversibility=0.6, basis='idle; small share'))] + findings
        bots.append(dict(id=bid, name=b['name'], status=b['status_suggested'], issue='TODO short issue', why=why,
                         improving=improving, findings=findings, needs_review=True))
    if empty:
        fleet.append(dict(title=f'{len(empty)} bots have no description',
                          now=[dict(date='', text=', '.join(diag['bots'][x]['name'] for x in empty))],
                          fix='Paste a short description into each bot, written from how you actually use it.',
                          copy=None, copy_kind='description', needs_review=True,
                          score=dict(impact=impact_from(0, bots=len(empty)), confidence='medium', effort=1, reversibility=1.0, basis=f'{len(empty)} bots')))
    for o in diag['fleet']['outages']:
        fleet.append(dict(title='Several bots stopped answering at the same time',
                          now=[dict(date=w['first'][5:10].replace('-', '/'), who=diag['bots'][w['bot']]['name'], quote={'orig': w['texts'][0]})
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
        if b['skipped_questions']['count']: leads['skipped_questions'][bid] = b['skipped_questions']['count']
        leads['preferences'] += [norm(txt(k))[:120] for k in b['preferences'] if k in jin]
    draft = dict(schema=3, title='Bot audit report', date=diag['now'][:10], lang=lang, bots=bots, fleet=fleet, leads=leads)
    if not lang.lower().startswith('en'):
        from make_report import UI_DEFAULT
        draft['translate'] = True
        draft['ui'] = {k: v for k, v in UI_DEFAULT.items()}
    dump_json(draft, os.path.join(a.work, 'findings_draft.json'))
    n = sum(len(b['findings']) for b in bots)
    print(f'draft: {len(bots)} bots, {n} bot findings, {len(fleet)} fleet items -> {os.path.join(a.work, "findings_draft.json")}')

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
    if draft.get('translate'):
        warns.append(f"report language is {draft.get('lang')}: translate every text field and the ui labels, then delete \"translate\"")
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
        for e in f.get('now', []):
            q = e.get('quote')
            if not q: continue
            orig = q.get('orig') if isinstance(q, dict) else q
            if not orig:
                errors.append(where + ': quote without "orig" (the exact original words)'); continue
            for seg in [s for s in QUOTE_SPLIT.split(norm(orig)) if len(s) >= 2]:
                if seg not in text:
                    errors.append(f'{where}: quote not found word for word in the saved chats: "{seg[:60]}"'); break
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
    draft.pop('leads', None)
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
