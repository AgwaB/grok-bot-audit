#!/usr/bin/env python3
"""Build replay folders from the synthetic fixtures (fake bots, fake text) for replay evals (tests/EVAL.md).

  python3 tests/make_replay.py OUTDIR
      OUTDIR/replay-synth-ja   the test fleet (4 bots: English bots with real problems, one Japanese bot)
      OUTDIR/replay-tiny       2 healthy English bots, nothing to fix

Each folder holds bots.json, transcripts/<id>/page_<start>.txt and replay.json ({"now": ...}), the same layout
`sessions.py replay` reads. Real-run replay folders are made by hand from a work folder and never go in the repo.
"""
import glob, json, os, shutil, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
S = os.path.join(ROOT, 'skills', 'audit-my-bots', 'scripts')
sys.path.insert(0, HERE)
import make_fixture as mf

SELF = 'aaaaaaaa-0000-4000-8000-0000000000ff'
TINY = {'cccccccc-0000-4000-8000-000000000001': ('Weather Buddy', 'Gives the morning weather for Testville. Fake test bot.'),
        'cccccccc-0000-4000-8000-000000000002': ('Word Coach', 'Explains one English word a day. Fake test bot.')}

def save(out, pages_root):
    for raw in sorted(glob.glob(os.path.join(pages_root, '*', '*.txt'))):
        subprocess.run([sys.executable, f'{S}/sessions.py', 'save-page', '--work', out,
                        f'{os.path.basename(os.path.dirname(raw))}={raw}'], check=True, capture_output=True)

def synth_ja(out):
    fx = os.path.join(HERE, 'fixtures')
    bots = []
    for p in sorted(glob.glob(os.path.join(fx, 'agents', '*', 'profile.json'))):
        aid = os.path.basename(os.path.dirname(p))
        if aid == SELF: continue
        pr = json.load(open(p, encoding='utf-8'))
        bots.append(dict(id=aid, name=pr['name'], description=pr.get('description', '')))
    json.dump(bots, open(os.path.join(out, 'bots.json'), 'w'), ensure_ascii=False, indent=1)
    save(out, os.path.join(fx, 'pages'))
    json.dump({'now': '2030-03-11 09:00'}, open(os.path.join(out, 'replay.json'), 'w'))

def tiny(out):
    w = mf.convo([(0, 7, 0, 'u', 'Weather today?'), (0, 7, 1, 'b', 'Sunny, 20 degrees. [fake]'),
                  (1, 7, 0, 'u', 'Will it rain this afternoon?'), (1, 7, 1, 'b', 'No rain expected. [fake]'),
                  (1, 7, 2, 'u', 'Thanks, perfect'), (1, 7, 3, 'b', 'Glad to help. [fake]')])
    c = mf.convo([(0, 20, 0, 'u', 'Word of the day please'), (0, 20, 1, 'b', 'Serendipity: a happy accident. [fake]'),
                  (2, 20, 0, 'u', 'Use it in a sentence'), (2, 20, 1, 'b', 'Finding that cafe was serendipity. [fake]')])
    tmp = os.path.join(out, '_pages'); bots = []
    for (aid, (name, desc)), conv in zip(TINY.items(), (w, c)):
        mf.write_pages(aid, name, conv, size=8, root=tmp); bots.append(dict(id=aid, name=name, description=desc))
    json.dump(bots, open(os.path.join(out, 'bots.json'), 'w'), indent=1)
    save(out, tmp); shutil.rmtree(tmp)
    json.dump({'now': '2030-03-04 09:00'}, open(os.path.join(out, 'replay.json'), 'w'))

if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    for name, fn in (('replay-synth-ja', synth_ja), ('replay-tiny', tiny)):
        out = os.path.join(sys.argv[1], name); shutil.rmtree(out, ignore_errors=True); os.makedirs(out); fn(out)
        print(out, len(glob.glob(os.path.join(out, 'transcripts', '*', 'page_*.txt'))), 'pages')
