import { useCallback, useEffect, useState } from "react";

import * as api from "./api";
import { relativeTime, shiftDay, todayKey } from "./format";
import {
  AppBreakdown,
  CategoryChart,
  EmptyDay,
  ErrorState,
  Header,
  Kpis,
  Skeleton,
  Timeline,
  Trend,
  TrackerWarning,
  Triage,
} from "./components";

// The tracker writes at least every 30s, so polling status faster than that
// only adds requests without adding information.
const STATUS_POLL_MS = 15000;
const TREND_DAYS = 14;

export default function App() {
  const [date, setDate] = useState(todayKey());
  const [status, setStatus] = useState(null);
  const [data, setData] = useState(null);
  const [trend, setTrend] = useState([]);
  const [categories, setCategories] = useState({ uncategorized: [], categories: [] });
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);

  const isToday = date === todayKey();

  /** Day-scoped data. Reloaded whenever the selected date changes. */
  const loadDay = useCallback(async (day) => {
    try {
      const [summary, timeline] = await Promise.all([
        api.getSummary(day),
        api.getTimeline(day),
      ]);

      setData({ summary, sessions: timeline.sessions });
      setError(null);
    } catch (err) {
      setError(err.message);
    }
  }, []);

  /** Data that spans days, plus the category list behind the triage panel. */
  const loadShared = useCallback(async () => {
    try {
      const [trendResult, categoryResult] = await Promise.all([
        api.getTrend(TREND_DAYS),
        api.getCategories(),
      ]);

      setTrend(trendResult.days);
      setCategories(categoryResult);
      setError(null);
    } catch (err) {
      setError(err.message);
    }
  }, []);

  useEffect(() => {
    setData(null);
    loadDay(date);
  }, [date, loadDay]);

  useEffect(() => {
    loadShared();
  }, [loadShared]);

  useEffect(() => {
    let cancelled = false;

    const poll = async () => {
      try {
        const result = await api.getStatus();
        if (!cancelled) setStatus(result);
      } catch {
        // The error banner is driven by the data requests; a failed status
        // poll on its own should not replace the whole view.
        if (!cancelled) setStatus({ tracking: false, current: null, last_seen: null });
      }
    };

    poll();
    const timer = setInterval(poll, STATUS_POLL_MS);

    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  // While viewing today, keep the numbers current as the tracker writes.
  useEffect(() => {
    if (!isToday) return undefined;

    const timer = setInterval(() => loadDay(date), STATUS_POLL_MS * 2);

    return () => clearInterval(timer);
  }, [isToday, date, loadDay]);

  const assignCategory = async (app, category) => {
    setSaving(true);

    try {
      await api.setAppCategory(app, category);
      // Categories change how every view is grouped, so refresh both scopes.
      await Promise.all([loadDay(date), loadShared()]);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const trackerStopped =
    status && !status.tracking && status.last_seen && isToday;

  const hasActivity = data && data.summary.tracked_seconds > 0;

  return (
    <div className="app">
      <Header
        date={date}
        isToday={isToday}
        status={status}
        onShift={(delta) => setDate((current) => shiftDay(current, delta))}
        onToday={() => setDate(todayKey())}
      />

      <main className="main">
        <div className="content">
          {error && <ErrorState message={error} />}

          {trackerStopped && <TrackerWarning lastSeen={relativeTime(status.last_seen)} />}

          {categories.uncategorized.length > 0 && (
            <Triage
              apps={categories.uncategorized}
              knownCategories={categories.categories}
              onAssign={assignCategory}
              busy={saving}
            />
          )}

          {!data && !error && <Skeleton />}

          {data && !hasActivity && <EmptyDay isToday={isToday} />}

          {data && hasActivity && (
            <>
              <Kpis summary={data.summary} timeline={data.sessions} />

              {data.summary.apps.length > 0 && (
                <div className="grid-2">
                  <AppBreakdown summary={data.summary} />
                  <CategoryChart summary={data.summary} />
                </div>
              )}

              {data.sessions.length > 0 && (
                <Timeline sessions={data.sessions} date={date} />
              )}
            </>
          )}

          {trend.length > 0 && (
            <Trend days={trend} selected={date} onSelect={setDate} />
          )}
        </div>
      </main>
    </div>
  );
}
