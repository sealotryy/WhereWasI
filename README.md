# WhereWasI

A local-first focus tracker for macOS. It records which application and window
had your attention, ignores time when you were away from the keyboard, and
reports where the day actually went.

Everything stays on your machine. The database is a SQLite file next to the
code, and the API binds to localhost only.

## Layout

| File | Role |
| --- | --- |
| `tracker.py` | Long-running daemon. Polls the foreground app and writes sessions. |
| `db.py` | Schema and migrations. Shared by everything else. |
| `macos.py` | System probes: frontmost app, window title, idle time. |
| `queries.py` | All reading and aggregation. Returns plain JSON-serializable data. |
| `view_data.py` | Command-line reports. Formatting only. |
| `api.py` | Local HTTP API over `queries.py`. |
| `dashboard/` | React dashboard served separately. Reads the API, writes categories. |
| `test.py` | Diagnostic that checks the system probes work. |

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt   # only needed for the API
```

Reading window titles requires Accessibility permission for whatever runs
Python — Terminal, iTerm, or VS Code — under System Settings > Privacy &
Security > Accessibility. Check it first:

```bash
python test.py
```

App names work without that permission. Window titles come back empty.

## Tracking

```bash
python tracker.py
```

Leave it running. It records a session per app-and-window-title, updates the
open session every 30 seconds so nothing is lost to a crash, and after two
minutes without input stops crediting time to the foreground app, logging the
gap as idle instead.

## Reports

```bash
python view_data.py                      # today
python view_data.py 2026-09-19           # a specific day
python view_data.py --week               # 7-day trend
python view_data.py --days               # which days have data
python view_data.py --categorize         # name any uncategorized apps
python view_data.py --set Opera=Leisure  # change one app's category
```

The tracker never interrupts you to ask about a new app; it records it as
`Uncategorized`. Name them later with `--categorize`, or over the API.

## API

```bash
uvicorn api:app --reload --port 8000
```

Interactive docs at <http://127.0.0.1:8000/docs>.

| Endpoint | Returns |
| --- | --- |
| `GET /api/summary?date=` | One day by app, window title, and category |
| `GET /api/timeline?date=&min_seconds=` | Ordered sessions for a day |
| `GET /api/trend?days=` | Active and idle seconds per day |
| `GET /api/category-totals?days=` | Seconds per category over a range |
| `GET /api/categories` | Known apps, categories, and what needs naming |
| `PUT /api/categories/{app}` | Classify an app |
| `GET /api/days` | Dates that have data |
| `GET /api/status` | What is being tracked right now |
| `GET /api/health` | Liveness |

There is no authentication because the server is not reachable from the
network. If you ever change the bind address, add auth first.

## Dashboard

A React dashboard that reads the API and renders the day: active versus idle
time, where the time went by app and category, an expandable list of window
titles per app, a session timeline, and a fourteen-day trend. Apps that have not
been classified appear in a panel at the top with a text field and one-click
buttons for categories already in use, so nothing stays `Uncategorized` unless
you leave it that way.

It needs two processes. Start the API first, from the project root:

```
uvicorn api:app --port 8000
```

Then the dashboard, from `dashboard/`:

```
npm install
npm run dev
```

Open the address Vite prints, usually `http://localhost:5173`. The dashboard
polls `/api/status` every fifteen seconds and, while showing today, refreshes
the day's figures every thirty, so leaving the tab open keeps it current.

For a production build:

```
npm run build
```

`dist/` can then be served by any static file server. The API's allowed origins
are listed in `DEV_ORIGINS` in `api.py`; if you serve the build from a different
port, add it there or the browser will block the requests.

## Notes on the data

- Idle time is excluded from active totals and reported separately, so
  percentages describe how focused time was split rather than the wall clock.
- Sessions shorter than two seconds are stored and counted but hidden from
  timeline listings, since tabbing through apps is noise.
- Rows recorded before window titles were added show `(no title)`.
