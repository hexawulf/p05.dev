/* Fetch client with AbortController cancellation and CSP-safe PNG/SVG/JSON downloads */

const _controllers = new Map();

export async function apiRequest(url, { method = "GET", body = null, channel = null } = {}) {
  if (channel) {
    const prev = _controllers.get(channel);
    if (prev) prev.abort();
    const ctrl = new AbortController();
    _controllers.set(channel, ctrl);
    return _doFetch(url, method, body, ctrl.signal);
  }
  return _doFetch(url, method, body, undefined);
}

async function _doFetch(url, method, body, signal) {
  const opts = { method, signal, headers: {} };
  if (body !== null) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(url, opts);
  const text = await res.text();
  let parsed = null;
  try {
    parsed = JSON.parse(text);
  } catch {
    // plain text fallback
  }
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    if (parsed && parsed.detail) {
      if (typeof parsed.detail === "string") {
        msg = parsed.detail;
      } else if (Array.isArray(parsed.detail)) {
        msg = parsed.detail.map((e) => `${(e.loc || []).slice(1).join(".")}: ${e.msg}`).join("; ");
      } else {
        msg = JSON.stringify(parsed.detail);
      }
    } else if (text) {
      msg = text;
    }
    throw new Error(msg);
  }
  return parsed;
}

export function triggerDownloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1500);
}

export async function downloadBackendPng(spec, filename = "p05-plot.png") {
  if (!spec) return;
  const res = await fetch("/api/v2/export/png", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(spec),
  });
  if (!res.ok) {
    const msg = await res.text();
    throw new Error(msg || `PNG export failed (HTTP ${res.status})`);
  }
  const blob = await res.blob();
  triggerDownloadBlob(blob, filename);
}

export function downloadJson(data, filename = "p05-result.json") {
  if (!data) return;
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  triggerDownloadBlob(blob, filename);
}
