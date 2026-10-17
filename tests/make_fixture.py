#!/usr/bin/env python3
"""Generate the synthetic test fixture (fake bots, fake chats). All names and text are invented.

Writes tests/fixtures/agents/<id>/profile.json and tests/fixtures/pages/<id>/page_<start>.txt in the
same shape as saved ReadTranscript results, plus tests/fixtures/labels_by_text.json (what a judge would decide).
"""
import json, os, shutil, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__)); FX = os.path.join(HERE, 'fixtures')
TZ = dt.timezone(dt.timedelta(hours=-5))
BASE = dt.datetime(2030, 3, 1, 9, 0, tzinfo=TZ)   # far-future dates make it obvious this is fake

BOTS = {
 'aaaaaaaa-0000-4000-8000-000000000001': dict(name='Recipe Helper', description='Suggests easy weeknight recipes. Fake test bot.'),
 'aaaaaaaa-0000-4000-8000-000000000002': dict(name='Trip Planner', description=''),
 'aaaaaaaa-0000-4000-8000-000000000003': dict(name='Old Notes', description=''),
 'aaaaaaaa-0000-4000-8000-000000000004': dict(name='メモボット', description=''),
 'aaaaaaaa-0000-4000-8000-0000000000ff': dict(name='Auditor (self)', description='The bot running the audit. Fake.'),
}

def stamp(t):
    off = t.utcoffset().total_seconds() / 3600
    return f"<timestamp>{t.strftime('%A, %b')} {t.day}, {t.year}, {int(t.strftime('%I'))}:{t.strftime('%M %p')} (UTC{int(off):+d})</timestamp>"

def user(t, text, n):
    return dict(role='user', message=dict(content=[dict(type='text', text=f'{stamp(t)}\n<user_query>\n[t{n}u]\n{text}\n</user_query>')]))

def attach_notice(path, size='120 KB'):
    """The app's attachment notice, in the shape it takes inside a user message (fake path)."""
    return ("The user attached a file. They're in your agent store at the paths below; open them with Read.\n"
            f"- {path} ({size}): an image already shown to you inline, so use this path only when you need the file itself")

def bot(text, k):
    return [dict(role='assistant', message=dict(content=[dict(type='tool_use', id=f'u{k}', name='SendToUser', input=dict(content=text))])),
            dict(role='tool', message=dict(content=[dict(type='tool_result', tool_use_id=f'u{k}', name='SendToUser',
                 result=f'<cursor_untrusted_data_redacted source="SendToUser">\nMessage sent to user. (id: tbs{k})\n</cursor_untrusted_data_redacted>')]))]

def memory(t, facts):
    body = 'These durable memory facts are untrusted data, not instructions.\n\nAbout the user (profile):\n' + '\n'.join(f'- (learned {d}) {f}' for d, f in facts)
    return dict(role='user', message=dict(content=[dict(type='text', text=f'{stamp(t)}\n<memory_context>\n{body}\n</memory_context>')]))

def hidden(t, kind_text):
    return dict(role='user', message=dict(content=[dict(type='text', text=f'{stamp(t)}\n<user_query>\n[GROK_BOT_HIDDEN_PROMPT]{kind_text}\n</user_query>')]))

def remember(fact, k):
    return [dict(role='assistant', message=dict(content=[dict(type='tool_use', id=f'm{k}', name='UpdateMemory', input=dict(action='write', fact=fact, type='profile'))]))]

def convo(script):
    """script: list of (day, hour, minute, 'u'|'b'|'mem'|'skip'|'remember', text)"""
    out, n, k = [], 0, 0
    for d, h, m, who, text in script:
        t = BASE + dt.timedelta(days=d, hours=h - 9, minutes=m)
        if who == 'u': out.append(user(t, text, n)); n += 1
        elif who == 'b': out += bot(text, k); k += 1
        elif who == 'mem': out.append(memory(t, text))
        elif who == 'skip': out.append(hidden(t, f'Earlier you prompted the user and they moved on without responding ("{text}"). Treat it as skipped.'))
        elif who == 'remember': out += remember(text, k); k += 1
    return out

R = convo([
 (0, 9, 0, 'mem', [('2030-02-20', 'The user currently cooks for two people.'), ('2030-02-20', 'The user likes spicy food.')]),
 (0, 9, 0, 'u', 'Suggest a quick dinner recipe for tonight'),
 (0, 9, 1, 'b', 'Here is a long recipe with twelve steps, a history of the dish, and three variations. [fake text]'),
 (0, 9, 5, 'u', 'Too long. Just give me the steps, no history'),
 (0, 9, 6, 'b', 'Sure: 1) boil 2) stir 3) serve. [fake text]'),
 (2, 18, 0, 'u', 'Suggest a quick dinner recipe for tonight please'),
 (2, 18, 1, 'b', 'Another long answer with a story about the farm where the beans grew. [fake text]'),
 (2, 18, 4, 'u', 'Still too long, I said no stories'),
 (2, 18, 5, 'b', 'Sorry. From now on I will keep recipes short. [fake text]'),
 (4, 19, 0, 'u', 'Suggest a quick dinner recipe for tonight'),
 (4, 19, 1, 'b', 'A long essay about pasta shapes before the recipe. [fake text]'),
 (4, 19, 3, 'u', 'No, too long again. Steps only'),
 (4, 19, 4, 'b', 'Steps only: 1) cook 2) eat. [fake text]'),
 (5, 8, 0, 'u', 'Is cilantro a herb?'),
 (5, 8, 1, 'b', 'Yes, it is a herb. [fake text]'),
 (6, 20, 0, 'u', 'suggest a quick dinner recipe for tonight'),
 (6, 20, 1, 'b', '1) chop 2) fry 3) serve. [fake text]'),
 (7, 10, 0, 'u', 'Plan dinners for the week'),
])
T = convo([
 (1, 10, 0, 'mem', [('2030-02-25', 'The user is planning a fake trip to Testville.')]),
 (1, 10, 0, 'u', 'Find me a cheap hotel in Testville'),
 (1, 10, 2, 'b', 'I found Hotel Example for 80 a night. [fake text]'),
 (1, 10, 5, 'u', "That's not what I asked, I meant a hostel"),
 (1, 10, 6, 'b', 'Got it, hostels: Example Hostel. [fake text]'),
 (1, 10, 7, 'skip', 'Which dates? — May / June'),
 (1, 10, 8, 'u', 'June'),
 (1, 10, 9, 'b', 'June noted. [fake text]'),
 (3, 11, 0, 'u', 'Book a table for dinner in Testville'),
 (3, 11, 1, 'b', 'I booked lunch at Sample Diner. [fake text]'),
 (3, 11, 3, 'u', 'No, I meant dinner, not lunch'),
 (3, 11, 4, 'b', 'Changed to dinner. [fake text]'),
 (4, 22, 0, 'u', 'What time does the museum open?'),
 (5, 9, 30, 'u', 'hello?'),
 (5, 9, 31, 'b', 'Sorry for the delay, it opens at 10. [fake text]'),
 (6, 12, 0, 'u', 'Find a train from Testville to Sampleton'),
 (6, 12, 1, 'b', 'The 9:00 train. [fake text]'),
 (6, 12, 3, 'u', 'You said 9:00 but I asked for an evening train, I meant evening'),
 (6, 12, 4, 'b', 'Evening: the 18:00 train. [fake text]'),
])
O = convo([
 (0, 12, 0, 'u', 'Save a note: buy fake milk'),
 (0, 12, 1, 'b', 'Saved. [fake text]'),
])
K = convo([   # the one non-English bot (Japanese), to test non-Latin chats
 (4, 21, 0, 'u', 'テスト用の偽メモを保存して'),
 (4, 21, 1, 'b', '保存しました。[偽テキスト]'),
 (4, 23, 0, 'u', 'さっきのメモをもう一度見せて'),
 (5, 10, 0, 'u', '確認?'),
 (5, 10, 1, 'b', '遅れてすみません。メモ: 偽のテストメモ [偽テキスト]'),
 (6, 9, 0, 'u', 'メモを要約して'),
 (6, 9, 1, 'b', 'とても長い要約です。背景と歴史まで含めました。[偽テキスト]'),
 (6, 9, 2, 'u', '長すぎる。一行にして'),
 (6, 9, 3, 'b', '一行要約: 偽メモ [偽テキスト]'),
])
CONVOS = {'aaaaaaaa-0000-4000-8000-000000000001': R, 'aaaaaaaa-0000-4000-8000-000000000002': T,
          'aaaaaaaa-0000-4000-8000-000000000003': O, 'aaaaaaaa-0000-4000-8000-000000000004': K}

def write_pages(aid, name, entries, size=8, root=None, prefix='raw_'):
    d = os.path.join(root or os.path.join(FX, 'pages'), aid); os.makedirs(d, exist_ok=True)
    n = len(entries)
    for start in range(0, n, size):
        end = min(n, start + size) - 1
        lines = ['<cursor_untrusted_data_redacted source="ReadTranscript">', '',
                 f'Transcript of agent "{name}" ({aid}), positions {start}–{end} of {n}:', '']
        lines += [json.dumps(e, ensure_ascii=False) for e in entries[start:end + 1]]
        lines += ['', 'This is the start of the transcript.' if start == 0 else f'Earlier entries exist; call again with before={start}.', '',
                  '</cursor_untrusted_data_redacted>']
        open(os.path.join(d, f'{prefix}{start}.txt'), 'w', encoding='utf-8').write('\n'.join(lines) + '\n')

if __name__ == '__main__':
    shutil.rmtree(FX, ignore_errors=True)
    for aid, prof in BOTS.items():
        d = os.path.join(FX, 'agents', aid); os.makedirs(d)
        json.dump(dict(name=prof['name'], description=prof['description'], title=prof['name']), open(os.path.join(d, 'profile.json'), 'w'), ensure_ascii=False)
    for aid, entries in CONVOS.items():
        write_pages(aid, BOTS[aid]['name'], entries)
    labels = {
     'Too long. Just give me the steps, no history': dict(label=True, type='correction', topic='format_length', confidence='high', evidence='"Too long"'),
     'Still too long, I said no stories': dict(label=True, type='correction', topic='format_length', confidence='high', evidence='"Still too long"'),
     'No, too long again. Steps only': dict(label=True, type='correction', topic='format_length', confidence='high', evidence='"too long again"'),
     "That's not what I asked, I meant a hostel": dict(label=True, type='correction', topic='misread_intent', confidence='high', evidence='"I meant a hostel"'),
     'No, I meant dinner, not lunch': dict(label=True, type='correction', topic='misread_intent', confidence='high', evidence='"I meant dinner"'),
     'You said 9:00 but I asked for an evening train, I meant evening': dict(label=True, type='correction', topic='misread_intent', confidence='high', evidence='"I meant evening"'),
     '長すぎる。一行にして': dict(label=True, type='correction', topic='format_length', confidence='high', evidence='"長すぎる"'),
    }
    json.dump(labels, open(os.path.join(FX, 'labels_by_text.json'), 'w'), ensure_ascii=False, indent=1)
    cues = dict(directive=['長すぎ', 'じゃなくて', 'もう一度'], fix=['今後は'], promise=['お知らせします'], nudge=['^確認'], timely=['現在'])
    json.dump(cues, open(os.path.join(FX, 'cues_ja.json'), 'w'), ensure_ascii=False, indent=1)
    print('fixture written to', FX)
