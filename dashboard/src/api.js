// Resolves to localhost during development and to the proxy path when the
// built bundle is served from a preview host.
const PLACEHOLDER = "__PORT_8000__";

export const API_BASE = PLACEHOLDER.startsWith("__")
  ? "http://localhost:8000"
  : PLACEHOLDER;

async function request(path, options) {
  let response;

  try {
    response = await fetch(`${API_BASE}${path}`, options);
  } catch {
    // fetch() rejects with the unhelpful "Failed to fetch" for every network
    // level problem, so say the thing the reader can actually act on.
    throw new Error(`Nothing is listening on ${API_BASE}`);
  }

  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;

    try {
      const body = await response.json();
      if (body?.detail) detail = body.detail;
    } catch {
      // Non-JSON error body; the status line is all we have.
    }

    throw new Error(detail);
  }

  return response.json();
}

export const getStatus = () => request("/api/status");
export const getDays = () => request("/api/days");
export const getCategories = () => request("/api/categories");

export const getSummary = (date) =>
  request(`/api/summary?titles_per_app=6${date ? `&date=${date}` : ""}`);

export const getTimeline = (date) =>
  request(`/api/timeline?min_seconds=2${date ? `&date=${date}` : ""}`);

export const getTrend = (days = 14) => request(`/api/trend?days=${days}`);

export const getCategoryTotals = (days = 14) =>
  request(`/api/category-totals?days=${days}`);

export const setAppCategory = (app, category) =>
  request(`/api/categories/${encodeURIComponent(app)}`, {
    method: "PUT",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ category }),
  });
