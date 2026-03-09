# TCG Presale Tracker

> Automatically scrapes TCGPlayer daily for **presale sealed products** (booster boxes etc.) with a **market price above $150**. Cases are excluded. Results are published to a GitHub Pages site.

**Live site →** https://gauravagarwal003.github.io/TCG_Presale_Tracker/

---

## How it works

| Component | Description |
|---|---|
| `tcgplayer_presale.py` | Scraper — hits TCGPlayer's internal API, filters presale items, writes `docs/data/results.json` |
| `.github/workflows/scrape.yml` | GitHub Actions — runs the scraper daily at 9 AM UTC, commits results |
| `docs/` | GitHub Pages site — reads the JSON and renders a card grid with images, prices, links |

## Filters applied

- **Sealed products only** (booster boxes, displays, etc.)
- **Market price ≥ $150**
- **Future release date** (true presales — not already shipped)
- **Excludes "case"** in the product name

## Local usage

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python tcgplayer_presale.py
```

Results are printed to stdout and saved to `docs/data/results.json`.

## Customize

Edit the config block at the top of `tcgplayer_presale.py`:

```python
SEARCH_QUERY     = "booster box"   # TCGPlayer search query
MIN_PRICE        = 150.0           # market price threshold
EXCLUDE_KEYWORDS = ["case"]        # skip names containing these words
```

## GitHub Pages setup (one-time)

1. Push this repo to GitHub as `TCG_Presale_Tracker`
2. Go to **Settings → Pages**
3. Set source to **Deploy from a branch → `main` → `/docs`**
4. Visit `https://gauravagarwal003.github.io/TCG_Presale_Tracker/`

The Actions workflow will automatically scrape and update the site every day.
To trigger a manual run: **Actions tab → Daily TCGPlayer Presale Scrape → Run workflow**.
