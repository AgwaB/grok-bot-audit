# Cue phrases (`cues.json`)

A few checks look for short phrases. The built-in lists (`CUES_EN` in `scripts/common.py`) are a minimal English fallback.
For chats in other languages, write `$W/cues.json` with the same five keys before step 3, using words from the actual
chats. Entries are case-insensitive regular expressions or plain words, added to the fallback.

| key | what it finds | English examples |
|---|---|---|
| `directive` | a user message that may correct the bot (wide net; the rubric decides) | no, not that, instead, don't, wrong, I meant, too long, already, again, from now on, are you sure |
| `fix` | the bot saying it saved a rule | from now on, I'll remember, I've saved, going forward |
| `promise` | the bot promising to come back later | I'll let you know, working on it, give me a minute |
| `nudge` | a short user check-in after silence (matched at the start of the message) | hi, hello, any update, status? |
| `timely` | a memory fact that goes stale | currently, now, at the moment, as of |

```json
{
  "directive": ["<word for no>", "<word for instead>", "<phrase for too long>"],
  "fix": ["<phrase for from now on>"],
  "promise": ["<phrase for I'll let you know>"],
  "nudge": ["^<greeting>"],
  "timely": ["<word for currently>"]
}
```

Or skip the cue filter: `judge_inputs.py --all` exports every reply that follows a bot message, and you judge them all.
