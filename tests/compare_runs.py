#!/usr/bin/env python3
"""Compare finished audit runs of the same fleet: per-bot status table, agreement rate, and the top 3 of each run.

  python3 tests/compare_runs.py [LABEL=]WORK_DIR [LABEL=]WORK_DIR ... [--json OUT]

Reads only each WORK_DIR/findings.json (and diag.json for the suggested status, if present). Bots are matched by id.
- status agreement: share of bots whose final status is the same in every run; pairwise: mean share over run pairs.
- top-3 agreement: mean pairwise overlap (Jaccard) of the top-3 targets, where a target is the bot an item belongs to
  ("fleet" for fleet items). Wording differs between runs (and languages), so items are compared by target, not text.
"""
import itertools, json, os, sys

SHORT = {'green': 'Fine', 'yellow': 'Needs work', 'red': 'Clean up'}

def load(arg):
    label, _, path = arg.rpartition('=') if '=' in arg else ('', '', arg)
    path = path or arg
    d = json.load(open(os.path.join(path, 'findings.json'), encoding='utf-8'))
    diag = {}
    if os.path.exists(os.path.join(path, 'diag.json')):
        diag = json.load(open(os.path.join(path, 'diag.json'), encoding='utf-8')).get('bots', {})
    names = {b['id']: b['name'] for b in d['bots']}
    def target(ref):
        if str(ref).startswith('fleet'): return 'fleet'
        return next((bid for bid in names if str(ref).startswith(bid)), str(ref))
    top = [(target(x.get('ref')), x.get('text', '')) for x in d.get('top3', [])]
    return dict(label=label or os.path.basename(os.path.dirname(os.path.dirname(path.rstrip('/')))) or path,
                status={b['id']: b['status'] for b in d['bots']}, names=names, top=top,
                suggested={bid: v.get('status_suggested') for bid, v in diag.items()})

def compare(runs):
    ids = list(dict.fromkeys(i for r in runs for i in r['status']))
    names = {}
    for r in runs: names.update(r['names'])
    same = [i for i in ids if len({r['status'].get(i) for r in runs}) == 1]
    pairs = list(itertools.combinations(runs, 2))
    pw = sum(sum(a['status'].get(i) == b['status'].get(i) for i in ids) / len(ids) for a, b in pairs) / len(pairs) if pairs else 1.0
    def jac(a, b):
        x, y = {t for t, _ in a['top']}, {t for t, _ in b['top']}
        return len(x & y) / len(x | y) if x | y else 1.0
    tj = sum(jac(a, b) for a, b in pairs) / len(pairs) if pairs else 1.0
    return dict(ids=ids, names=names, same=same, status_all=len(same) / len(ids) if ids else 1.0, status_pairwise=pw, top3_pairwise=tj)

def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    out = sys.argv[sys.argv.index('--json') + 1] if '--json' in sys.argv else None
    if out in args: args.remove(out)
    if len(args) < 2: sys.exit(__doc__)
    runs = [load(a) for a in args]; c = compare(runs)
    head = ['bot'] + [r['label'] for r in runs] + ['suggested', 'agree']
    print('| ' + ' | '.join(head) + ' |\n|' + '---|' * len(head))
    for i in c['ids']:
        sug = {r['suggested'].get(i) for r in runs if r['suggested'].get(i)}
        print('| ' + ' | '.join([c['names'].get(i, i[:8])] + [SHORT.get(r['status'].get(i), '-') for r in runs]
                                + ['/'.join(SHORT.get(s, s) for s in sorted(sug)) or '-', 'yes' if i in c['same'] else '**no**']) + ' |')
    print(f"\nstatus agreement: {len(c['same'])}/{len(c['ids'])} bots identical in all runs ({c['status_all']:.0%}); "
          f"pairwise {c['status_pairwise']:.0%}")
    print(f"top-3 agreement (by target bot, pairwise Jaccard): {c['top3_pairwise']:.0%}")
    for r in runs:
        print(f"top 3 {r['label']}: " + '; '.join(f"[{'fleet' if t == 'fleet' else c['names'].get(t, t)[:20]}] {x}" for t, x in r['top']))
    if out:
        json.dump(dict(runs=[{k: r[k] for k in ('label', 'status', 'top')} for r in runs], **{k: c[k] for k in ('status_all', 'status_pairwise', 'top3_pairwise')}),
                  open(out, 'w'), ensure_ascii=False, indent=1)

if __name__ == '__main__':
    main()
