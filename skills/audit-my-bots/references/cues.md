# Cue phrases (`cues.json`) and `--all`

A few checks look for short phrases. The built-in lists (`CUES_EN` in `scripts/common.py`) are a minimal English fallback,
so the pipeline runs without input. There are no lists for other languages, on purpose: you read the chats yourself.

## Which mode for step 3
Decided per bot from that bot's **user messages** (not the language the user writes to you in). `judge_inputs.py` prints,
for each bot, the share of its user messages written mostly in Latin letters (the only ones the English cues can match)
and a recommended mode; `--auto` applies it:
- **At least 8 in 10, and at most 1 in 10 with accented letters:** the cue filter is fine for that bot. Code spans,
  identifiers, commands and links are removed before counting, and a message with 3 or more letters of another script
  counts as mixed, so a user who writes in another language between code still gets every reply judged.
- **Otherwise:** all its replies are judged. By hand: `--all` (every bot) or `--all-for <bot> …` (only those bots).
  Nothing is missed because of word endings or phrasing. Latin-script chats in another language (accented letters in
  more than 1 in 10 messages) get every reply too. A language with few accents can still pass as English: if you
  see that a bot's chats are not in English, use `--all-for <bot>` or write `cues.json`.
- A bot whose replies match no cue at all gets all its replies exported anyway (small histories).
- **Over 400 items with `--all`:** you may write `$W/cues.json` from words you see in the actual chats and run without
  `--all`; check that it still catches the corrections you noticed while skimming, and add words if it misses some.

## `cues.json`
Same six keys as the fallback. Entries are case-insensitive regular expressions or plain words, added to the English
list. Write stems or short fragments rather than whole sentences, so different endings still match.

| key | what it finds | English examples |
|---|---|---|
| `directive` | a user message that may correct the bot (wide net; the rubric decides) | no, not that, instead, don't, wrong, I meant, too long, already, again, from now on, are you sure |
| `fix` | the bot saying it saved a rule | from now on, I'll remember, I've saved, going forward |
| `promise` | the bot promising to come back later | I'll let you know, working on it, give me a minute |
| `nudge` | a short user check-in after silence (matched at the start of the message) | hi, hello, any update, status? |
| `timely` | a memory fact that goes stale | currently, now, at the moment, as of |
| `safety` | a safety boundary kept in memory (`setup.md`) | never send … without, ask me first, confirm before |

```json
{
  "directive": ["<word for no>", "<word for instead>", "<stem for too long>"],
  "fix": ["<phrase for from now on>"],
  "promise": ["<phrase for I'll let you know>"],
  "nudge": ["^<greeting>"],
  "timely": ["<word for currently>"],
  "safety": ["<phrase for ask me first>"]
}
```

`--all` covers only the correction candidates. The other four keys feed smaller checks (a fix the bot announced, promises
followed by a nudge, stale memory facts, safety rules in memory). They are an extra signal only: promises and stale
memory are also found from the judge's labels (`later`, `newer_judged`) in any language. Some checks need no words and work in any language:
memory saves, memory facts holding a date that has passed, and a very short "…?" from the user after an hour or more
of silence following a short bot message. For the rest, in chats in other languages, either add a few words for those
keys, or check the memory block and the bots' promises yourself while reading.
