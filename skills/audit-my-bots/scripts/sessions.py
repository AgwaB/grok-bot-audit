#!/usr/bin/env python3
"""Bot Audit, step 1: list bots, save transcript pages, and turn pages into per-bot timelines.

  python3 sessions.py list-bots --work W [--self AGENT_ID]
      Reads only "name" and "description" from <agents>/*/profile.json -> W/bots.json.
      The auditing bot itself (--self) is skipped.
  python3 sessions.py save-page FILE [FILE ...] --work W --bot AGENT_ID
  python3 sessions.py save-page AGENT_ID=FILE [AGENT_ID=FILE ...] --work W
      Copies saved ReadTranscript results to W/transcripts/<id>/page_<start>.txt and prints, per file,
      "start=<A> end=<B> total=<N>" so you know the next `before` value (A) and when you reached 0.
      Several files (one bot or several) can be saved in one call.
  python3 sessions.py parse --work W
      W/transcripts/<id>/page_*.txt -> W/timelines/<id>.json (events, memory block, coverage).
  python3 sessions.py replay --work W [--from DIR] [--self AGENT_ID]
      Testing only (tests/EVAL.md): instead of steps 1-2, copy DIR/bots.json and DIR/transcripts/<id>/page_*.txt
      (pre-saved pages) into W, plus DIR/replay.json ({"now": "YYYY-MM-DD HH:MM", "self": "<id>"}) if present. DIR
      defaults to $AUDIT_REPLAY_DIR. The bot skipped as "self" is --self, else replay.json's "self", else none: every
      other listed bot is audited.

Read-only on bot data. Never opens anything except profile.json and the saved pages.
"""
import argparse, collections, datetime as dt, glob, json, os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (AGENTS_DIR, call_args, clean_user, dump_json, load_json, load_pages, norm, page_start,
                    parse_ts, tool_input, user_kind)
import re

def list_bots(a):
    bots = []
    for p in sorted(glob.glob(os.path.join(a.agents_dir, '*', 'profile.json'))):
        aid = os.path.basename(os.path.dirname(p))
        if a.self and aid == a.self:
            continue
        try:
            prof = json.load(open(p, encoding='utf-8'))
        except Exception:
            continue
        bots.append(dict(id=aid, name=prof.get('name') or aid[:8], description=(prof.get('description') or '').strip()))
    dump_json(bots, os.path.join(a.work, 'bots.json'))
    for b in bots:
        print(f"{b['id']}\t{b['name']}")
    print(f'{len(bots)} bots -> {os.path.join(a.work, "bots.json")}', file=sys.stderr)

def save_page(a):
    bad = 0
    for item in a.files:
        bot, f = (item.split('=', 1) if '=' in item and not os.path.exists(item) else (a.bot, item))
        if not bot:
            print(f'{item}: no bot id (use --bot ID or ID=FILE)'); bad += 1; continue
        info = page_start(f)
        if not info:
            print(f'{bot}: no "positions A–B of N" header found in {f}'); bad += 1; continue
        d = os.path.join(a.work, 'transcripts', bot)
        os.makedirs(d, exist_ok=True)
        dst = os.path.join(d, f'page_{info[0]:05d}.txt')
        shutil.copyfile(f, dst)
        print(f'{bot[:8]} start={info[0]} end={info[1]} total={info[2]} saved={dst}' + (' (reached the start)' if info[0] == 0 else ''))
    if bad:
        sys.exit(1)

def replay(a):
    src = a.src or os.environ.get('AUDIT_REPLAY_DIR')
    if not src or not os.path.isfile(os.path.join(src, 'bots.json')):
        sys.exit('replay: give --from DIR or set AUDIT_REPLAY_DIR (a folder with bots.json and transcripts/<id>/page_*.txt)')
    os.makedirs(a.work, exist_ok=True)
    me = a.self or load_json(os.path.join(src, 'replay.json'), {}).get('self')
    bots = [b for b in load_json(os.path.join(src, 'bots.json'), []) if b['id'] != me]
    dump_json(bots, os.path.join(a.work, 'bots.json'))
    if os.path.isfile(os.path.join(src, 'replay.json')):
        shutil.copyfile(os.path.join(src, 'replay.json'), os.path.join(a.work, 'replay.json'))
    n = 0
    ids = {b['id'] for b in bots}
    for p in glob.glob(os.path.join(src, 'transcripts', '*', 'page_*.txt')):
        if os.path.basename(os.path.dirname(p)) not in ids: continue
        d = os.path.join(a.work, 'transcripts', os.path.basename(os.path.dirname(p)))
        os.makedirs(d, exist_ok=True); shutil.copyfile(p, os.path.join(d, os.path.basename(p))); n += 1
    print(f'replay: {len(bots)} bots, {n} saved pages from {src} -> {a.work}. Every listed bot is audited. '
          f'Next: sessions.py parse.')
    for b in bots:
        print(f"{b['id']}\t{b['name']}")

def bot_text(name, inp):
    if name == 'CallDynamicTool' and inp.get('toolName') == 'SendToUser':
        inp = call_args(inp)
    elif name != 'SendToUser':
        return None
    for k in ('content', 'text', 'message', 'body'):
        v = inp.get(k)
        if isinstance(v, str) and v.strip():
            return v
    return None

def parse_one(d):
    entries, cover = load_pages(d)
    events, memory, last_ts = [], None, None
    fallback_text = []
    offsets = collections.Counter()
    for e in entries:
        role = e.get('role'); content = (e.get('message') or {}).get('content') or []
        if isinstance(content, str):
            content = [dict(type='text', text=content)]
        for x in content:
            ty = x.get('type')
            if role == 'user' and ty == 'text':
                t = x.get('text') or ''
                ts = parse_ts(t)
                if ts: last_ts = ts
                k = user_kind(t)
                m = re.search(r'<memory_context>(.*?)</memory_context>', t, re.S)
                if m: memory = dict(text=m.group(1).strip(), ts=ts or last_ts)
                if k == 'real':
                    if ts: offsets[ts.utcoffset()] += 1
                    ct, att = clean_user(t, with_meta=True)
                    ev = dict(role='user', ts=ts or last_ts, text=ct)
                    if att: ev['attachments'] = att
                    events.append(ev)
                elif k == 'skipped_question':
                    q = re.search(r'without responding \((.*?)\)\. Treat', t, re.S)
                    events.append(dict(role='app', kind='skipped_question', ts=ts or last_ts, text=norm(q.group(1)).strip('"') if q else ''))
                elif k in ('routine', 'agent', 'background_result', 'form_submit'):
                    events.append(dict(role='app', kind=k, ts=ts or last_ts, text=''))
            elif role == 'assistant' and ty == 'tool_use':
                inp = tool_input(x)
                bt = bot_text(x.get('name'), inp)
                if bt:
                    events.append(dict(role='bot', ts=last_ts, text=bt))
                elif x.get('name') == 'UpdateMemory' and inp.get('action', 'write') == 'write' and inp.get('fact'):
                    events.append(dict(role='app', kind='memory_write', ts=last_ts, text=str(inp.get('fact'))[:400]))
            elif role == 'assistant' and ty == 'text' and (x.get('text') or '').strip():
                fallback_text.append(dict(role='bot', ts=last_ts, text=x['text'], _pos=len(events)))
    if not any(ev['role'] == 'bot' for ev in events):   # bots that answer in plain text
        for f in reversed(fallback_text):
            events.insert(f.pop('_pos'), f)
    tz = offsets.most_common(1)[0][0] if offsets else dt.timedelta(0)
    zone = dt.timezone(tz)
    for i, ev in enumerate(events):
        ev['i'] = i
        ev['ts'] = ev['ts'].astimezone(zone).strftime('%Y-%m-%d %H:%M') if ev.get('ts') else None
    if memory:
        memory['ts'] = memory['ts'].astimezone(zone).strftime('%Y-%m-%d %H:%M') if memory.get('ts') else None
    return dict(events=events, memory=memory, coverage=cover, utc_offset_hours=tz.total_seconds() / 3600)

def parse(a):
    bots = load_json(os.path.join(a.work, 'bots.json'), [])
    for b in bots:
        d = os.path.join(a.work, 'transcripts', b['id'])
        if not glob.glob(os.path.join(d, 'page_*.txt')):
            print(f"{b['name']}: no pages saved, skipped", file=sys.stderr)
            continue
        tl = parse_one(d); tl.update(id=b['id'], name=b['name'])
        dump_json(tl, os.path.join(a.work, 'timelines', b['id'] + '.json'))
        n_user = sum(1 for e in tl['events'] if e['role'] == 'user')
        flag = '' if tl['coverage']['complete'] else '  WARNING: pages do not reach position 0 / the end; fetch the missing pages'
        print(f"{b['name']}: {n_user} user messages, {sum(1 for e in tl['events'] if e['role'] == 'bot')} bot messages{flag}")

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    p = sp.add_parser('list-bots'); p.add_argument('--work', required=True); p.add_argument('--self')
    p.add_argument('--agents-dir', default=AGENTS_DIR); p.set_defaults(fn=list_bots)
    p = sp.add_parser('save-page'); p.add_argument('files', nargs='+'); p.add_argument('--work', required=True)
    p.add_argument('--bot'); p.set_defaults(fn=save_page)
    p = sp.add_parser('parse'); p.add_argument('--work', required=True); p.set_defaults(fn=parse)
    p = sp.add_parser('replay'); p.add_argument('--work', required=True); p.add_argument('--from', dest='src'); p.add_argument('--self')
    p.set_defaults(fn=replay)
    a = ap.parse_args(); a.fn(a)

if __name__ == '__main__':
    main()
