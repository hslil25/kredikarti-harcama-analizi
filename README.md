# Türkiye Kredi Kartı Harcama Analizi

Analyze Turkish credit-card spending against inflation (TÜİK CPI and İTO index),
using data from the CBRT **EVDS** API.

The headline metric is the **real average ticket**:

```
avg_ticket(t)      = cc_amount(t) / cc_count(t)
real_avg_ticket(t) = avg_ticket(t) × CPI(base) / CPI(t)
```

CPI is monthly and credit-card data is weekly, so the chosen CPI series is
linearly interpolated onto the weekly axis before deflating. The user picks the
spending category, the deflator source (TÜİK / İTO), and the base week.

## Layout

```
backend/   FastAPI + official `evds` package; caches EVDS data in SQLite
frontend/  React (Vite) + Recharts; stacked spending + CPI charts
```

## Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then put your EVDS_API_KEY in .env
```

1. Edit `app/catalog.py` — replace every `PLACEHOLDER_*` with real EVDS series
   codes and fill in the credit-card ↔ CPI `MAPPING`.
2. Fetch + cache the data:
   ```bash
   python -m app.ingest
   ```
3. Run the API:
   ```bash
   uvicorn app.main:app --reload
   ```
   - `GET /health` — cache status / whether the catalog is configured
   - `GET /categories` — categories for the UI
   - `GET /real?category=food&source=tuik&base=YYYY-MM-DD`

## Frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173 (proxies /api -> :8000)
```

## What still needs your input

- **EVDS API key** → `backend/.env`
- **Series codes** for the 4 families (CC amount, CC count, TÜİK CPI, İTO)
- **CC ↔ CPI category mapping** → `backend/app/catalog.py`

Finding codes: the `evds` package lists them via
`evds.main_categories`, `evds.get_sub_categories(<id>)`, `evds.get_series(<sub>)`.
