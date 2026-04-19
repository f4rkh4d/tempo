# tempo

pretty pomodoro timer for the terminal. sessions, tags, github-style heatmap, streaks. optional macos menubar companion.

**→ [frkhd.com/tempo](https://frkhd.com/tempo)** for screenshots and the pitch.

```
$ tempo start --tag uni --duration 25
╭── tempo ─────────────────────────────────────────────────────╮
│                                                              │
│   UNI  • today · 4th session • target 25:00                  │
│                                                              │
│          ╭──╮ ╭──╮   ╭──╮ ╷                                  │
│          ├──┤ ╰─╮│ ██ │  │ │                                 │
│          ╰──╯ ╶──╯    ──╯ ╵                                  │
│                                                              │
│       ████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░        │
│                                                              │
│                 52%  •  running                              │
│              q quit  p pause  + add 5 min                    │
│                                                              │
╰──────────────────────────────────────────────────────────────╯
```

```
$ tempo stats
╭─── last 7d ──────────────────────────────────────────────────╮
│                                                              │
│    11h 40min     18         5 days      7 days               │
│    FOCUS         SESSIONS   STREAK      BEST                 │
│                                                              │
╰──────────────────────────────────────────────────────────────╯

╭─── by tag ───────────────────────────────────────────────────╮
│   uni       5h 10min  ▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇               │
│   code      4h 25min  ▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇                  │
│   reading   2h 05min  ▇▇▇▇▇▇▇▇▇▇                             │
╰──────────────────────────────────────────────────────────────╯

╭─── last 90 days ─────────────────────────────────────────────╮
│  mon ▇▇ ▇▇ ▇▇ ▇▇ ▇▇ ▇▇ ▇▇ ▇▇ ▇▇ ▇▇ ▇▇ ▇▇ ▇▇                  │
│      ▇▇ ▇▇ ▇▇ ▇▇ ▇▇ ▇▇ ▇▇ ▇▇ ▇▇ ▇▇ ▇▇ ▇▇ ▇▇                  │
│  wed ▇▇ ▇▇ ▇▇ ▇▇ ▇▇ ▇▇ ▇▇ ▇▇ ▇▇ ▇▇ ▇▇ ▇▇ ▇▇                  │
│      ▇▇ ▇▇ ▇▇ ▇▇ ▇▇ ▇▇ ▇▇ ▇▇ ▇▇ ▇▇ ▇▇ ▇▇ ▇▇                  │
│  fri ▇▇ ▇▇ ▇▇ ▇▇ ▇▇ ▇▇ ▇▇ ▇▇ ▇▇ ▇▇ ▇▇ ▇▇ ▇▇                  │
│      ▇▇ ▇▇ ▇▇ ▇▇ ▇▇ ▇▇ ▇▇ ▇▇ ▇▇ ▇▇ ▇▇ ▇▇ ▇▇                  │
│  sun ▇▇ ▇▇ ▇▇ ▇▇ ▇▇ ▇▇ ▇▇ ▇▇ ▇▇ ▇▇ ▇▇ ▇▇ ▇▇                  │
│                                                              │
│      less  ▇▇ ▇▇ ▇▇ ▇▇ ▇▇  more                              │
╰──────────────────────────────────────────────────────────────╯
```

built because i kept writing the same three lines of python every time i wanted a pomodoro timer. this one saves the sessions, shows you a heatmap, and sits in your menu bar if you want.

## install

```
pip install git+https://github.com/f4rkh4d/tempo
```

python 3.9+. macos and linux. keyboard shortcuts work in a real terminal (not in piped/redirected stdin).

**with the macos menubar companion:**

```
pip install "tempo[menubar] @ git+https://github.com/f4rkh4d/tempo"
tempo-bar
```

## usage

```bash
# start a focus block
tempo start                          # default: 25 min, no tag
tempo start -t code -d 50            # 50 min tagged 'code'
tempo start -t uni -n "6.006 pset"

# during a session
#   p  →  pause / resume
#   +  →  add 5 minutes
#   q  →  quit (still logs the partial session)

# stats — dashboard in the terminal
tempo stats                          # last 7 days, with heatmap
tempo stats --window day
tempo stats --window month
tempo stats --window all
tempo stats --no-heatmap             # just the numbers

# quick glance
tempo today
tempo ls                             # recent sessions
tempo ls -n 20

# wipe
tempo clear
```

## desktop notifications

when a session ends (completed or aborted), tempo fires a native desktop notification so you don't have to be staring at the terminal.

- **macos** — uses `osascript`. ships with the OS, no setup.
- **linux** — uses `notify-send` if installed. skipped silently otherwise.
- **windows** — not wired up yet.

disable per-session with `--no-notify`.

## macos menubar companion

install with the extra: `pip install "tempo[menubar]"`, then run `tempo-bar`.

you get `● tempo` in the menu bar. click it to:

- see today's total + current session status
- start a session (pick duration + tag from the menu or type your own)
- watch a live countdown right in the menubar title: `● uni 12:34`
- pause / add 5 min / abort from the menu
- get a native notification when the session ends

sessions from cli + menubar share the same `~/.tempo/sessions.jsonl` store, so history is continuous regardless of which you use.

## streaks

`tempo stats` shows a **current streak** (consecutive days with at least one session, counted from today or yesterday) and a **best streak** (longest streak you've ever had).

same psychology as the github contribution graph — missing a day hurts.

## where sessions are stored

plain jsonl at `~/.tempo/sessions.jsonl`. one session per line. portable, diff-friendly, easy to query with `jq`:

```bash
# total minutes today, tagged 'code'
jq -s 'map(select(.tag == "code")) | map(.actual_sec) | add / 60' \
   ~/.tempo/sessions.jsonl
```

override the path with `TEMPO_STORE=/some/other/path.jsonl`.

## why not just use a physical timer?

because you can't `grep` a physical timer.

## license

mit.
