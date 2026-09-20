/** Compact duration for dense UI: 2h 14m, 47m, 38s. */
export function duration(seconds) {
  const total = Math.round(seconds || 0);

  if (total < 60) return `${total}s`;

  const hours = Math.floor(total / 3600);
  const minutes = Math.round((total % 3600) / 60);

  if (!hours) return `${minutes}m`;

  return minutes ? `${hours}h ${minutes}m` : `${hours}h`;
}

export function clockTime(isoString) {
  if (!isoString) return "";

  return new Date(isoString).toLocaleTimeString([], {
    hour: "numeric",
    minute: "2-digit",
  });
}

export function dayLabel(date, { weekday = false } = {}) {
  if (!date) return "";

  // Parse as local noon so a timezone offset cannot shift the day.
  const parsed = new Date(`${date}T12:00:00`);
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);

  const asKey = (value) => value.toISOString().slice(0, 10);
  const todayKey = asKey(new Date(`${today.toISOString().slice(0, 10)}T12:00:00`));
  const yesterdayKey = asKey(
    new Date(`${yesterday.toISOString().slice(0, 10)}T12:00:00`),
  );

  if (date === todayKey) return "Today";
  if (date === yesterdayKey) return "Yesterday";

  return parsed.toLocaleDateString([], {
    weekday: weekday ? "short" : undefined,
    month: "short",
    day: "numeric",
  });
}

export function shortDay(date) {
  return new Date(`${date}T12:00:00`).toLocaleDateString([], {
    weekday: "narrow",
  });
}

export function relativeTime(isoString) {
  if (!isoString) return "";

  const seconds = (Date.now() - new Date(isoString).getTime()) / 1000;

  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;

  return `${Math.floor(seconds / 86400)}d ago`;
}

export function todayKey() {
  const now = new Date();
  const offset = now.getTimezoneOffset() * 60000;

  return new Date(now.getTime() - offset).toISOString().slice(0, 10);
}

export function shiftDay(date, days) {
  const parsed = new Date(`${date}T12:00:00`);
  parsed.setDate(parsed.getDate() + days);

  const offset = parsed.getTimezoneOffset() * 60000;

  return new Date(parsed.getTime() - offset).toISOString().slice(0, 10);
}

// Stable category colors: the same category keeps its hue across every chart
// and every session, so the eye can learn it.
const PALETTE = [
  "#5eead4",
  "#7dd3fc",
  "#c4b5fd",
  "#fcd34d",
  "#fda4af",
  "#86efac",
  "#f0abfc",
  "#fdba74",
];

const IDLE_COLOR = "#3f4a5a";

export function categoryColor(category) {
  if (!category) return IDLE_COLOR;
  if (category === "Idle") return IDLE_COLOR;
  if (category === "Uncategorized") return "#64748b";

  let hash = 0;

  for (let i = 0; i < category.length; i += 1) {
    hash = (hash * 31 + category.charCodeAt(i)) % 9973;
  }

  return PALETTE[hash % PALETTE.length];
}
