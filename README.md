# tempo

pretty pomodoro timer for the terminal. sessions, tags, weekly stats. optional macos menubar app.

```
$ tempo start --tag uni --duration 25
╭─ focus session ─────────────────────────────╮
│              uni  ·  25:00                  │
│                                             │
│   ████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░      │
│                                             │
│                17:58 left                   │
│                                             │
│       q quit · p pause · + add 5 min        │
│                                             │
│                 [running]                   │
╰─────────────────────────────────────────────╯
```

```
$ tempo stats --window week
last 7d: 11h 40min across 18 sessions.
  uni       5h 10min  ▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇
  code      4h 25min  ▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇
  reading   2h 05min  ▇▇▇▇▇▇▇▇▇▇
```

built because i kept writing the same three lines of python every time i wanted a pomodoro timer. this one saves the sessions so you can look back.

## install

```
pip install tempo
```

or from source:

```
pip install git+https://github.com/f4rkh4d/tempo
```

python 3.9+. runs on macos and linux. keyboard shortcuts work in a real terminal (not in piped/redirected stdin).

**with the menubar companion** (macos):

```
pip install "tempo[menubar]"
```

## usage

```bash
# start a focus block
tempo start                    # default: 25 min, no tag
tempo start -t code -d 50      # 50 min tagged 'code'
tempo start -t uni -n "reading mit 6.006"

# during a session
#   p  →  pause / resume
#   +  →  add 5 minutes
#   q  →  quit (still logs the partial session)

# see stats
tempo stats                    # last 7 days
tempo stats --window day
tempo stats --window month
tempo stats --window all

# recent sessions
tempo ls
tempo ls -n 20

# wipe everything
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

you get a 🍅 in the menu bar. click it to:

- start a session (pick duration + tag from the menu or type your own)
- see a live countdown right in the menubar title: `🍅 uni 12:34`
- pause / add 5 min / abort from the menu
- get a native notification when the session ends
- peek at last-7d stats

sessions go into the same `~/.tempo/sessions.jsonl` store, so cli + menubar share history.

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
