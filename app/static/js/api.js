// Small JSON API client.

export async function api(path, { method = "GET", body, formData } = {}) {
  const opts = { method };
  if (formData) {
    opts.body = formData;
  } else if (body !== undefined) {
    opts.headers = { "Content-Type": "application/json" };
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(path, opts);
  if (res.status === 401) {
    location.hash = "#/login";
    throw new Error("not signed in");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg =
      typeof data.detail === "string"
        ? data.detail
        : Array.isArray(data.detail)
          ? data.detail.map((d) => d.msg).join("; ")
          : "request failed";
    throw new Error(msg);
  }
  return data;
}

export function scopeParams(scope) {
  return new URLSearchParams({ scope });
}
