import { useEffect, useMemo, useState } from "react";
import { getCategories, getReal, getHealth } from "./api";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ReferenceLine,
} from "recharts";

const nf0 = new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 0 });
const nf1 = new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 1 });
const nf2 = new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 2 });

const tl = (n) => (n == null ? "—" : `₺${nf0.format(n)}`);
const pct = (n) => (n == null ? "—" : `%${nf1.format(n)}`);
const signPct = (n) =>
  n == null ? "—" : `${n >= 0 ? "+" : ""}${nf1.format(n)}%`;

// Reference month for the "= 100" indexing option.
const REF_PREFIX = "2021-09"; // Eylül 2021
const REF_LABEL = "Eylül 2021";

// Colors for the per-component CPI lines.
const COMP_COLORS = [
  "#2a9d8f", "#e76f51", "#457b9d", "#e9c46a",
  "#9b5de5", "#f15bb5", "#00bbf9", "#8ac926",
];

// Centered moving average over `window` points; preserves nulls.
function smoothArr(vals, window) {
  if (!window) return vals;
  const half = Math.floor(window / 2);
  return vals.map((_, i) => {
    let sum = 0;
    let n = 0;
    for (let j = i - half; j <= i + half; j++) {
      if (j >= 0 && j < vals.length && vals[j] != null) {
        sum += vals[j];
        n += 1;
      }
    }
    return n ? sum / n : null;
  });
}

// Index of the point at/closest to the reference month.
function refIndex(points) {
  const exact = points.findIndex((p) => p.date.startsWith(REF_PREFIX));
  if (exact !== -1) return exact;
  const target = new Date(`${REF_PREFIX}-15`).getTime();
  let best = -1;
  let bestD = Infinity;
  points.forEach((p, i) => {
    const d = Math.abs(new Date(p.date).getTime() - target);
    if (d < bestD) {
      bestD = d;
      best = i;
    }
  });
  return best;
}

export default function App() {
  const [categories, setCategories] = useState([]);
  const [category, setCategory] = useState("");
  const [source, setSource] = useState("tuik");
  const [base, setBase] = useState("");
  const [smooth, setSmooth] = useState(8); // moving-average window (weeks)
  const [indexBase, setIndexBase] = useState(false); // Kasım 2021 = 100
  const [data, setData] = useState(null);
  const [health, setHealth] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getHealth().then(setHealth).catch(() => {});
    getCategories()
      .then((cats) => {
        setCategories(cats);
        if (cats.length) setCategory(cats[0].key);
      })
      .catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    if (!category) return;
    setLoading(true);
    setError("");
    getReal({ category, source, base: base || undefined })
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [category, source, base]);

  const points = data?.points ?? [];
  const summary = data?.summary;
  const current = categories.find((c) => c.key === category);

  // If the selected category has no İTO mapping, fall back to TÜİK.
  useEffect(() => {
    if (source === "ito" && current && !current.has_ito) setSource("tuik");
  }, [current, source]);
  const baseWeeks = useMemo(
    () => points.filter((_, i) => i % 4 === 0).map((p) => p.date),
    [points]
  );
  const hasReal = points.some((p) => p.real_avg_ticket != null);

  // Build the average-ticket chart data: optional Kasım-2021 indexing + smoothing.
  const ticket = useMemo(() => {
    let real = points.map((p) => p.real_avg_ticket);
    const nom = points.map((p) => p.nominal_avg_ticket); // always raw ₺, not indexed
    let indexed = false;
    let refDate = null;

    if (indexBase && points.length) {
      const ri = refIndex(points);
      const rRef = points[ri]?.real_avg_ticket;
      refDate = points[ri]?.date ?? null;
      indexed = true;
      // index only the real series to 100 at the reference month
      real = real.map((v) => (v != null && rRef ? (v / rRef) * 100 : null));
    }

    const w = Number(smooth);
    const realS = smoothArr(real, w);
    const nomS = smoothArr(nom, w);
    const rows = points.map((p, i) => ({
      date: p.date,
      real: real[i],
      nom: nom[i],
      realS: realS[i],
      nomS: nomS[i],
    }));
    return { rows, indexed, refDate, smoothed: w > 0 };
  }, [points, smooth, indexBase]);

  // Polarization vs market: count ratio + avg-ticket ratio (smoothed).
  const pol = useMemo(() => {
    const w = Number(smooth);
    const pic = smoothArr(points.map((p) => p.pi_count), w);
    const pit = smoothArr(points.map((p) => p.pi_ticket), w);
    const rows = points.map((p, i) => ({
      date: p.date,
      pi_count: p.pi_count,
      pi_ticket: p.pi_ticket,
      picS: pic[i],
      pitS: pit[i],
    }));
    return { rows, smoothed: w > 0 };
  }, [points, smooth]);

  const unitLabel = ticket.indexed ? `${REF_LABEL} = 100` : "₺";
  const tUnit = ticket.indexed ? "endeks" : "₺"; // unit shown in legend
  const fmtTicket = ticket.indexed ? (v) => nf1.format(v) : tl;
  const srcLabel = data?.source === "ito" ? "İTO" : "TÜİK";

  return (
    <div className="app">
      <header>
        <h1>Türkiye Kredi Kartı Harcama Analizi</h1>
        <p className="sub">
          Kategori bazında işlem başına harcamanın enflasyona karşı reel değeri
          (TÜİK / İTO ile düzeltilmiş)
        </p>
      </header>

      {health && !health.catalog_configured && (
        <div className="banner warn">
          Katalog yapılandırılmadı — <code>backend/app/catalog.py</code> kodlarını
          doldurup <code>python -m app.ingest</code> çalıştırın.
        </div>
      )}

      <section className="controls">
        <label>
          Kategori
          <select value={category} onChange={(e) => setCategory(e.target.value)}>
            {categories.map((c) => (
              <option key={c.key} value={c.key}>
                {c.label}
              </option>
            ))}
          </select>
        </label>

        <label>
          Endeks Kaynağı
          <div className="toggle">
            <button
              className={source === "tuik" ? "on" : ""}
              disabled={current && !current.has_tuik}
              onClick={() => setSource("tuik")}
            >
              TÜİK
            </button>
            <button
              className={source === "ito" ? "on" : ""}
              disabled={!current || !current.has_ito}
              title={current && !current.has_ito ? "Henüz uygulanmadı" : ""}
              onClick={() => setSource("ito")}
            >
              İTO
            </button>
          </div>
        </label>

        <label>
          Baz Dönem (referans hafta)
          <select
            value={base}
            disabled={indexBase}
            title={indexBase ? "Endeksleme açıkken etkisizdir" : ""}
            onChange={(e) => setBase(e.target.value)}
          >
            <option value="">En son hafta (varsayılan)</option>
            {baseWeeks.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        </label>

        <label>
          Düzleştirme
          <select value={smooth} onChange={(e) => setSmooth(Number(e.target.value))}>
            <option value={0}>Ham veri</option>
            <option value={4}>4 haftalık ortalama</option>
            <option value={8}>8 haftalık ortalama</option>
            <option value={13}>13 haftalık (≈çeyrek)</option>
            <option value={26}>26 haftalık (≈yarım yıl)</option>
          </select>
        </label>

        <label className="check">
          <input
            type="checkbox"
            checked={indexBase}
            onChange={(e) => setIndexBase(e.target.checked)}
          />
          <span>{REF_LABEL} = 100 endeksle</span>
        </label>
      </section>

      {error && <div className="banner err">{error}</div>}
      {loading && <div className="banner">Yükleniyor…</div>}

      {summary && (
        <section className="stats">
          <Stat
            label="Reel değişim"
            hint={`${summary.period_start} → ${summary.period_end}`}
            value={signPct(summary.real_change_pct)}
            tone={summary.real_change_pct >= 0 ? "pos" : "neg"}
          />
          <Stat
            label="Nominal değişim"
            hint="işlem başına, ham"
            value={signPct(summary.nominal_change_pct)}
          />
          <Stat
            label="Kümülatif enflasyon"
            hint={`${srcLabel}, dönem içi`}
            value={signPct(summary.cumulative_inflation_pct)}
          />
          <Stat
            label="Son yıllık enflasyon"
            hint="YoY"
            value={pct(summary.latest_cpi_yoy)}
          />
        </section>
      )}

      {data && (
        <div className="meta">
          <span className="chip">{data.cc_label}</span>
          <span>Kaynak: {srcLabel}</span>
          <span>Baz dönem: {data.base_date ?? "—"}</span>
          <span>{points.length} hafta</span>
        </div>
      )}

      {data?.components?.length > 0 && (
        <div className="components">
          <span className="components-title">CPI bileşenleri (normalize ağırlık):</span>
          {data.components.map((c, i) => (
            <span key={c.key} className="comp-chip">
              <span className="dot" style={{ background: COMP_COLORS[i % COMP_COLORS.length] }} />
              {c.label}
              <b>%{nf1.format(c.weight * 100)}</b>
            </span>
          ))}
        </div>
      )}

      {points.length > 0 ? (
        <>
          <ChartCard
            title={
              ticket.indexed
                ? `İşlem Başına Harcama — Reel Endeks (${unitLabel})`
                : `İşlem Başına Harcama — Reel vs Nominal (${unitLabel})`
            }
          >
            <LineChart data={ticket.rows} margin={{ top: 8, right: 16, bottom: 0, left: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
              <XAxis dataKey="date" minTickGap={48} fontSize={11} tickFormatter={yr} />
              <YAxis fontSize={11} width={70} tickFormatter={(v) => nf0.format(v)} />
              <Tooltip formatter={(v, n) => [fmtTicket(v), n]} labelFormatter={lbl} />
              <Legend />
              {ticket.indexed ? (
                <ReferenceLine y={100} stroke="#bbb" strokeDasharray="3 3" />
              ) : (
                data.base_date && (
                  <ReferenceLine x={data.base_date} stroke="#bbb" strokeDasharray="3 3" />
                )
              )}
              {ticket.smoothed && (
                <>
                  {/* raw real, faint, behind the trend */}
                  <Line type="monotone" dataKey="real" name="Reel (ham)"
                    stroke="#c1121f" strokeOpacity={0.18} dot={false} isAnimationActive={false}
                    strokeWidth={1} connectNulls legendType="none" />
                  <Line type="monotone" dataKey="realS" name={`Reel trend (${tUnit})`}
                    stroke="#c1121f" dot={false} isAnimationActive={false} strokeWidth={2.4} connectNulls />
                  {!ticket.indexed && (
                    <Line type="monotone" dataKey="nomS" name="Nominal trend (₺)"
                      stroke="#999" dot={false} isAnimationActive={false} strokeWidth={1.8}
                      strokeDasharray="4 3" connectNulls />
                  )}
                </>
              )}
              {!ticket.smoothed && (
                <>
                  <Line type="monotone" dataKey="real" name={`Reel (${tUnit})`}
                    stroke="#c1121f" dot={false} isAnimationActive={false} strokeWidth={2} connectNulls />
                  {!ticket.indexed && (
                    <Line type="monotone" dataKey="nom" name="Nominal (₺)"
                      stroke="#999" dot={false} isAnimationActive={false} strokeDasharray="4 3" connectNulls />
                  )}
                </>
              )}
            </LineChart>
          </ChartCard>

          <ChartCard title={`${srcLabel} Fiyat Endeksi (haftalığa interpolasyon)`}>
            <LineChart data={points} margin={{ top: 8, right: 16, bottom: 0, left: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
              <XAxis dataKey="date" minTickGap={48} fontSize={11} tickFormatter={yr} />
              <YAxis fontSize={11} width={70} tickFormatter={(v) => nf0.format(v)} />
              <Tooltip formatter={(v, n) => [nf2.format(v), n]} labelFormatter={lbl} />
              <Line type="monotone" dataKey="cpi" name="Endeks"
                stroke="#1d3557" dot={false} isAnimationActive={false} strokeWidth={2} />
            </LineChart>
          </ChartCard>

          <ChartCard title="Yıllık Enflasyon (YoY %) — bileşenler">
            <LineChart data={points} margin={{ top: 8, right: 16, bottom: 0, left: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
              <XAxis dataKey="date" minTickGap={48} fontSize={11} tickFormatter={yr} />
              <YAxis fontSize={11} width={70} tickFormatter={(v) => `%${nf0.format(v)}`} />
              <Tooltip formatter={(v, n) => [pct(v), n]} labelFormatter={lbl} />
              <Legend />
              {/* per-component YoY lines */}
              {(data.components ?? []).map((c, i) => (
                <Line
                  key={c.key}
                  type="monotone"
                  dataKey={`${c.key}_yoy`}
                  name={c.label}
                  stroke={COMP_COLORS[i % COMP_COLORS.length]}
                  dot={false}
                  isAnimationActive={false}
                  strokeWidth={1.3}
                  strokeOpacity={0.85}
                  connectNulls
                />
              ))}
              {/* composite on top, bold */}
              <Line type="monotone" dataKey="cpi_yoy" name="Bileşik (ağırlıklı)"
                stroke="#1a1a1a" dot={false} isAnimationActive={false}
                strokeWidth={2.4} connectNulls />
            </LineChart>
          </ChartCard>

          {!data.is_basic && (
            <>
              <ChartCard title={`Polarizasyon — İşlem Adedi Oranı (${data.basic_label}'ne göre)`}>
                <LineChart data={pol.rows} margin={{ top: 8, right: 16, bottom: 0, left: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
                  <XAxis dataKey="date" minTickGap={48} fontSize={11} tickFormatter={yr} />
                  <YAxis fontSize={11} width={70} tickFormatter={(v) => nf2.format(v)} />
                  <Tooltip formatter={(v, n) => [nf2.format(v), n]} labelFormatter={lbl} />
                  <ReferenceLine y={1} stroke="#bbb" strokeDasharray="3 3" />
                  {pol.smoothed && (
                    <Line type="monotone" dataKey="pi_count" name="ham"
                      stroke="#6a4c93" strokeOpacity={0.18} dot={false}
                      isAnimationActive={false} strokeWidth={1} connectNulls legendType="none" />
                  )}
                  <Line type="monotone" dataKey={pol.smoothed ? "picS" : "pi_count"}
                    name="Adet oranı" stroke="#6a4c93" dot={false}
                    isAnimationActive={false} strokeWidth={2.2} connectNulls />
                </LineChart>
              </ChartCard>

              <ChartCard title={`Polarizasyon — İşlem Başına Tutar Oranı (${data.basic_label}'ne göre)`}>
                <LineChart data={pol.rows} margin={{ top: 8, right: 16, bottom: 0, left: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
                  <XAxis dataKey="date" minTickGap={48} fontSize={11} tickFormatter={yr} />
                  <YAxis fontSize={11} width={70} tickFormatter={(v) => nf2.format(v)} />
                  <Tooltip formatter={(v, n) => [nf2.format(v), n]} labelFormatter={lbl} />
                  <ReferenceLine y={1} stroke="#bbb" strokeDasharray="3 3" />
                  {pol.smoothed && (
                    <Line type="monotone" dataKey="pi_ticket" name="ham"
                      stroke="#bc6c25" strokeOpacity={0.18} dot={false}
                      isAnimationActive={false} strokeWidth={1} connectNulls legendType="none" />
                  )}
                  <Line type="monotone" dataKey={pol.smoothed ? "pitS" : "pi_ticket"}
                    name="Tutar oranı" stroke="#bc6c25" dot={false}
                    isAnimationActive={false} strokeWidth={2.2} connectNulls />
                </LineChart>
              </ChartCard>
            </>
          )}

          {!hasReal && (
            <p className="note">
              Bu kategori için TÜİK karşılığı tanımlı değil — yalnızca nominal
              gösterilir.
            </p>
          )}
        </>
      ) : (
        !loading && <div className="empty">Gösterilecek veri yok.</div>
      )}
    </div>
  );
}

const yr = (d) => (d ? d.slice(0, 4) : d);
const lbl = (d) => `Hafta: ${d}`;

function Stat({ label, value, hint, tone }) {
  return (
    <div className="stat">
      <span className="stat-label">{label}</span>
      <span className={`stat-value ${tone ?? ""}`}>{value}</span>
      {hint && <span className="stat-hint">{hint}</span>}
    </div>
  );
}

function ChartCard({ title, children }) {
  return (
    <div className="card">
      <h2>{title}</h2>
      <ResponsiveContainer width="100%" height={240}>
        {children}
      </ResponsiveContainer>
    </div>
  );
}
