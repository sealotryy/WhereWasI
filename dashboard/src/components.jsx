import { useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
} from "recharts";

import { categoryColor, clockTime, dayLabel, duration, shortDay } from "./format";

/* ---------------------------------------------------------------- icons */

export function Logo() {
  // Stacked time blocks: the product's own timeline strip, reduced to a mark.
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-label="WhereWasI">
      <rect x="1.5" y="1.5" width="21" height="21" rx="6" stroke="currentColor" strokeWidth="1.6" />
      <rect x="6" y="7" width="12" height="2.4" rx="1.2" fill="currentColor" />
      <rect x="6" y="11.8" width="7.5" height="2.4" rx="1.2" fill="currentColor" opacity="0.6" />
      <rect x="6" y="16.6" width="4" height="2.4" rx="1.2" fill="currentColor" opacity="0.3" />
    </svg>
  );
}

function Chevron({ open }) {
  return (
    <svg className={`chev${open ? " open" : ""}`} width="12" height="12" viewBox="0 0 12 12" fill="none">
      <path d="M4.5 2.5 8 6l-3.5 3.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function Arrow({ dir }) {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
      <path
        d={dir === "left" ? "M8.5 3.5 5 7l3.5 3.5" : "M5.5 3.5 9 7l-3.5 3.5"}
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function WarnIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <circle cx="8" cy="8" r="6.6" stroke="currentColor" strokeWidth="1.5" />
      <path d="M8 4.8v3.6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      <circle cx="8" cy="11" r="0.85" fill="currentColor" />
    </svg>
  );
}

/* ---------------------------------------------------------------- header */

export function Header({ date, isToday, onShift, onToday, status }) {
  const tracking = status?.tracking;
  const current = status?.current;

  let dotClass = "stopped";
  let label = "Tracker not running";

  if (tracking && current) {
    dotClass = current.is_idle ? "idle" : "live";
    label = current.is_idle ? "Idle" : current.label;
  } else if (status === null) {
    dotClass = "";
    label = "Connecting...";
  }

  return (
    <header className="header">
      <div className="brand">
        <Logo />
        WhereWasI
      </div>

      <div className="header-spacer" />

      <div className="datenav">
        <button onClick={() => onShift(-1)} aria-label="Previous day">
          <Arrow dir="left" />
        </button>
        <span className="datenav-current">{dayLabel(date)}</span>
        <button onClick={() => onShift(1)} disabled={isToday} aria-label="Next day">
          <Arrow dir="right" />
        </button>
      </div>

      {!isToday && (
        <button className="today-btn" onClick={onToday}>
          Today
        </button>
      )}

      <div className="status" title={current ? `Since ${clockTime(current.start)}` : undefined}>
        <span className={`dot ${dotClass}`} />
        <span className="status-label">{label}</span>
      </div>
    </header>
  );
}

/* ---------------------------------------------------------------- states */

export function TrackerWarning({ lastSeen }) {
  return (
    <div className="banner">
      <WarnIcon />
      <div>
        <div className="banner-title">Tracker is not running</div>
        <div className="banner-body">
          Nothing has been recorded since {lastSeen}. Start it with{" "}
          <code>python tracker.py</code> — an empty chart otherwise looks the same
          as a day away from the machine.
        </div>
      </div>
    </div>
  );
}

export function EmptyDay({ isToday }) {
  return (
    <div className="card">
      <div className="empty">
        <div className="empty-title">Nothing recorded {isToday ? "yet today" : "on this day"}</div>
        <p>
          {isToday ? (
            <>
              Run <code>python tracker.py</code> and leave it going. Sessions appear
              here within a minute.
            </>
          ) : (
            <>
              Pick another day, or list the days that do have data with{" "}
              <code>python view_data.py --days</code>
            </>
          )}
        </p>
      </div>
    </div>
  );
}

export function ErrorState({ message }) {
  return (
    <div className="banner">
      <WarnIcon />
      <div>
        <div className="banner-title">Cannot reach the API</div>
        <div className="banner-body">
          {message} — start it from the project folder with{" "}
          <code>uvicorn api:app --port 8000</code>
        </div>
      </div>
    </div>
  );
}

export function Skeleton() {
  return (
    <>
      <div className="kpis">
        {[0, 1, 2, 3].map((i) => (
          <div className="kpi" key={i}>
            <div className="skeleton sk-line" style={{ width: "45%" }} />
            <div className="skeleton sk-line" style={{ width: "70%", height: 20 }} />
          </div>
        ))}
      </div>
      <div className="grid-2">
        <div className="card">
          <div className="skeleton sk-line" style={{ width: "30%" }} />
          {[0, 1, 2, 3, 4].map((i) => (
            <div className="skeleton sk-line" key={i} style={{ marginTop: 18 }} />
          ))}
        </div>
        <div className="card">
          <div className="skeleton sk-line" style={{ width: "40%" }} />
          <div className="skeleton" style={{ height: 180, marginTop: 18 }} />
        </div>
      </div>
    </>
  );
}

/* ---------------------------------------------------------------- KPIs */

export function Kpis({ summary, timeline }) {
  const { active_seconds: active, idle_seconds: idle, tracked_seconds: tracked } = summary;

  const topCategory = summary.categories[0];
  const longest = useMemo(
    () =>
      timeline
        .filter((session) => !session.is_idle)
        .reduce((best, session) => (session.seconds > (best?.seconds ?? 0) ? session : best), null),
    [timeline],
  );

  const focusShare = tracked ? Math.round((active / tracked) * 100) : 0;

  return (
    <div className="kpis">
      <div className="kpi accent">
        <div className="kpi-label">Active</div>
        <div className="kpi-value num">{duration(active)}</div>
        <div className="kpi-sub">{focusShare}% of {duration(tracked)} tracked</div>
      </div>

      <div className="kpi">
        <div className="kpi-label">Idle</div>
        <div className="kpi-value num">{duration(idle)}</div>
        <div className="kpi-sub">away from the keyboard</div>
      </div>

      <div className="kpi">
        <div className="kpi-label">Top category</div>
        <div className="kpi-value">{topCategory?.category ?? "None"}</div>
        <div className="kpi-sub">
          {topCategory ? `${duration(topCategory.seconds)} · ${topCategory.share}%` : "nothing categorized"}
        </div>
      </div>

      <div className="kpi">
        <div className="kpi-label">Longest stretch</div>
        <div className="kpi-value num">{longest ? duration(longest.seconds) : "—"}</div>
        <div className="kpi-sub">{longest ? longest.app : "no sessions"}</div>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------- app list */

export function AppBreakdown({ summary }) {
  const [openApp, setOpenApp] = useState(null);
  const max = summary.apps[0]?.seconds ?? 1;

  return (
    <section className="card">
      <div className="card-head">
        <h2 className="card-title">Where the time went</h2>
        <span className="card-note">{summary.apps.length} apps</span>
      </div>

      <div className="applist">
        {summary.apps.map((app) => {
          const open = openApp === app.app;
          const color = categoryColor(app.category);

          return (
            <div className="approw" key={app.app}>
              <button
                className="approw-main"
                onClick={() => setOpenApp(open ? null : app.app)}
                aria-expanded={open}
              >
                <span className="swatch" style={{ background: color }} />
                <span className="approw-name">
                  <div className="approw-app">{app.app}</div>
                  <div className="approw-cat">{app.category}</div>
                </span>
                <span className="approw-time num">{duration(app.seconds)}</span>
                <span className="approw-share num">{app.share}%</span>
                <Chevron open={open} />
              </button>

              <div className="bar-track">
                <div
                  className="bar-fill"
                  style={{ width: `${(app.seconds / max) * 100}%`, background: color }}
                />
              </div>

              {open && (
                <div className="titles">
                  {app.titles.length === 0 && (
                    <div className="titlerow">No window titles recorded.</div>
                  )}
                  {app.titles.map((title) => (
                    <div className="titlerow" key={title.title}>
                      <span className="titlerow-name">{title.title}</span>
                      <span className="titlerow-time num">
                        {duration(title.seconds)} · {Math.round(title.share_of_app)}%
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}

/* ---------------------------------------------------------------- categories */

function PieTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;

  const item = payload[0].payload;

  return (
    <div className="tooltip">
      <div className="tooltip-label">{item.category}</div>
      <span className="num">{duration(item.seconds)}</span> · {item.share}%
    </div>
  );
}

export function CategoryChart({ summary }) {
  const data = summary.categories;

  return (
    <section className="card">
      <div className="card-head">
        <h2 className="card-title">By category</h2>
        <span className="card-note">active time only</span>
      </div>

      <div className="chart-wrap">
        <ResponsiveContainer>
          <PieChart>
            <Pie
              data={data}
              dataKey="seconds"
              nameKey="category"
              innerRadius="58%"
              outerRadius="88%"
              paddingAngle={2}
              stroke="none"
              isAnimationActive={false}
            >
              {data.map((item) => (
                <Cell key={item.category} fill={categoryColor(item.category)} />
              ))}
            </Pie>
            <Tooltip content={<PieTooltip />} />
          </PieChart>
        </ResponsiveContainer>
      </div>

      <div className="legend">
        {data.map((item) => (
          <span className="legend-item" key={item.category}>
            <span className="legend-swatch" style={{ background: categoryColor(item.category) }} />
            {item.category}
            <span className="legend-time num">{duration(item.seconds)}</span>
          </span>
        ))}
      </div>
    </section>
  );
}

/* ---------------------------------------------------------------- timeline */

export function Timeline({ sessions, date }) {
  // The strip is proportional to the tracked span, so a long session reads as
  // a wide block rather than one row among many.
  const total = sessions.reduce((sum, session) => sum + session.seconds, 0) || 1;
  const first = sessions[0];
  const last = sessions[sessions.length - 1];

  return (
    <section className="card">
      <div className="card-head">
        <h2 className="card-title">Timeline · {dayLabel(date)}</h2>
        <span className="card-note">{sessions.length} sessions</span>
      </div>

      <div className="strip">
        {sessions.map((session, index) => (
          <div
            key={`${session.start_time}-${index}`}
            className="strip-seg"
            style={{
              width: `${(session.seconds / total) * 100}%`,
              background: session.is_idle ? "var(--idle)" : categoryColor(session.category),
            }}
            title={`${session.label} · ${duration(session.seconds)}`}
          />
        ))}
      </div>

      <div className="strip-axis">
        <span>{clockTime(first?.start)}</span>
        <span>{clockTime(last?.end)}</span>
      </div>

      <div className="sessions">
        {sessions.map((session, index) => (
          <div
            className={`session${session.is_idle ? " is-idle" : ""}`}
            key={`${session.start_time}-row-${index}`}
          >
            <span className="session-time num">{clockTime(session.start)}</span>
            <span className="swatch" style={{
              background: session.is_idle ? "var(--idle)" : categoryColor(session.category),
              height: 16,
            }} />
            <span className="session-label">{session.label}</span>
            <span className="session-dur num">{duration(session.seconds)}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

/* ---------------------------------------------------------------- trend */

function TrendTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;

  const item = payload[0].payload;

  return (
    <div className="tooltip">
      <div className="tooltip-label">{dayLabel(item.date, { weekday: true })}</div>
      <div>
        Active <span className="num">{duration(item.active_seconds)}</span>
      </div>
      {item.idle_seconds > 0 && (
        <div style={{ color: "var(--text-dim)" }}>
          Idle <span className="num">{duration(item.idle_seconds)}</span>
        </div>
      )}
    </div>
  );
}

export function Trend({ days, selected, onSelect }) {
  const hasData = days.some((day) => day.active_seconds > 0);

  return (
    <section className="card">
      <div className="card-head">
        <h2 className="card-title">Last {days.length} days</h2>
        <span className="card-note">active time per day</span>
      </div>

      {hasData ? (
        <div className="chart-wrap" style={{ height: 180 }}>
          <ResponsiveContainer>
            <BarChart data={days} margin={{ top: 4, right: 0, bottom: 0, left: 0 }}>
              <XAxis
                dataKey="date"
                tickFormatter={shortDay}
                tick={{ fill: "#64748b", fontSize: 11 }}
                axisLine={false}
                tickLine={false}
                interval={0}
              />
              <Tooltip content={<TrendTooltip />} cursor={{ fill: "rgba(255,255,255,0.04)" }} />
              <Bar
                dataKey="active_seconds"
                radius={[3, 3, 0, 0]}
                onClick={(bar) => onSelect(bar.date)}
                cursor="pointer"
                isAnimationActive={false}
              >
                {days.map((day) => (
                  <Cell
                    key={day.date}
                    fill={day.date === selected ? "#2dd4bf" : "#26344a"}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div className="empty">
          <p>No activity in this range yet.</p>
        </div>
      )}
    </section>
  );
}

/* ---------------------------------------------------------------- triage */

export function Triage({ apps, knownCategories, onAssign, busy }) {
  const [drafts, setDrafts] = useState({});

  const update = (app, value) => setDrafts((prev) => ({ ...prev, [app]: value }));

  return (
    <section className="card triage">
      <div className="card-head">
        <h2 className="card-title">Needs a category</h2>
        <span className="card-note">{apps.length} waiting</span>
      </div>

      {apps.map((app) => (
        <div className="triage-row" key={app}>
          <span className="triage-app">{app}</span>

          {/* Reusing an existing name is one click, which keeps categories from
              fragmenting into Coding / coding / Code over time. */}
          {knownCategories.length > 0 && (
            <div className="chips" style={{ margin: 0 }}>
              {knownCategories.slice(0, 4).map((category) => (
                <button
                  key={category}
                  className="chip"
                  type="button"
                  onClick={() => onAssign(app, category)}
                  disabled={busy}
                >
                  {category}
                </button>
              ))}
            </div>
          )}

          <form
            className="triage-form"
            onSubmit={(event) => {
              event.preventDefault();
              const value = (drafts[app] ?? "").trim();
              if (value) onAssign(app, value);
            }}
          >
            <input
              className="triage-input"
              list="known-categories"
              placeholder="Category"
              value={drafts[app] ?? ""}
              onChange={(event) => update(app, event.target.value)}
              disabled={busy}
            />
            <button className="btn" type="submit" disabled={busy || !(drafts[app] ?? "").trim()}>
              Save
            </button>
          </form>
        </div>
      ))}

      <datalist id="known-categories">
        {knownCategories.map((category) => (
          <option key={category} value={category} />
        ))}
      </datalist>
    </section>
  );
}
