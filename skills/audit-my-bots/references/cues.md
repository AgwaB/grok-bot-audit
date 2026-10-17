# Cue phrases (`cues.json`) and `--all`

A few checks look for short phrases. The built-in lists (`CUES_EN` in `scripts/common.py`) are a minimal English fallback,
so the pipeline runs without input. There are no lists for other languages, on purpose: you read the chats yourself.

## Which mode for step 3
- **Most user messages are in English:** run `judge_inputs.py` as is.
- **Otherwise (the default for any other language or a mix):** run `judge_inputs.py --all`. It exports every reply that
  follows a bot message, and you judge each one with the rubric. Nothing is missed because of word endings or phrasing.
- **`--all` gives more items than you can judge carefully** (several hundred): write `$W/cues.json` from words you see in
  the actual chats, run without `--all`, and check that it still catches the corrections you noticed while skimming.
  If it misses some, add their words and run it again.

## `cues.json`
Same five keys as the fallback. Entries are case-insensitive regular expressions or plain words, added to the English
list. Write stems or short fragments rather than whole sentences, so different endings still match.

| key | what it finds | English examples |
|---|---|---|
| `directive` | a user message that may correct the bot (wide net; the rubric decides) | no, not that, instead, don't, wrong, I meant, too long, already, again, from now on, are you sure |
| `fix` | the bot saying it saved a rule | from now on, I'll remember, I've saved, going forward |
| `promise` | the bot promising to come back later | I'll let you know, working on it, give me a minute |
| `nudge` | a short user check-in after silence (matched at the start of the message) | hi, hello, any update, status? |
| `timely` | a memory fact that goes stale | currently, now, at the moment, as of |

```json
{
  "directive": ["<word for no>", "<word for instead>", "<stem for too long>"],
  "fix": ["<phrase for from now on>"],
  "promise": ["<phrase for I'll let you know>"],
  "nudge": ["^<greeting>"],
  "timely": ["<word for currently>"]
}
```

`--all` covers only the correction candidates. The other four keys feed smaller checks (a fix the bot announced, promises
followed by a nudge, stale memory facts). Memory saves are detected in any language. For chats in other languages, either
add a few words for those keys, or check the memory block and the bots' promises yourself while reading.
