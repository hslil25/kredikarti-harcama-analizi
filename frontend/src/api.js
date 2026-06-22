// Thin client for the FastAPI backend (proxied at /api in dev).
const BASE = "/api";

export async function getCategories() {
  const r = await fetch(`${BASE}/categories`);
  if (!r.ok) throw new Error("kategoriler yüklenemedi");
  return r.json();
}

export async function getReal({ category, source, base, start, end }) {
  const params = new URLSearchParams({ category, source });
  if (base) params.set("base", base);
  if (start) params.set("start", start);
  if (end) params.set("end", end);
  const r = await fetch(`${BASE}/real?${params}`);
  if (!r.ok) throw new Error("veri alınamadı");
  return r.json();
}

export async function getHealth() {
  const r = await fetch(`${BASE}/health`);
  return r.json();
}
