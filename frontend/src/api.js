// Static data client. Reads precomputed JSON (works on GitHub Pages with no
// backend). BASE_URL handles the repo subpath in production.
const BASE = `${import.meta.env.BASE_URL}data`;

export async function getCategories() {
  const r = await fetch(`${BASE}/categories.json`);
  if (!r.ok) throw new Error("kategoriler yüklenemedi");
  return r.json();
}

// `base`/`start`/`end` are applied client-side, so only category+source pick
// the file here.
export async function getReal({ category, source }) {
  const r = await fetch(`${BASE}/real/${category}__${source}.json`);
  if (!r.ok) throw new Error("veri alınamadı");
  return r.json();
}

export async function getHealth() {
  try {
    const r = await fetch(`${BASE}/health.json`);
    return r.json();
  } catch {
    return { catalog_configured: true };
  }
}
