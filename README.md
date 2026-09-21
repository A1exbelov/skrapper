# Skrapper

Telegram bot that checks apartment listing pages and sends new matching ads to a chat.

## What it does

- Polls configured search URLs on a schedule.
- Normalizes listings from source-specific parsers.
- Filters by price, rooms, include keywords, and exclude keywords.
- Stores seen listing IDs locally to avoid duplicate Telegram messages.
- Sends compact Telegram notifications with title, price, location, and link.

## Quick start

1. Copy env and config examples:

```powershell
Copy-Item .env.example .env
Copy-Item config.example.yaml config.yaml
```

2. Fill in `.env`:

```text
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
CONFIG_PATH=config.yaml
```

3. Run locally:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
python -m skrapper
```

Or with Docker:

```powershell
docker compose up --build -d
```

## Config

Each search has a `source`, a public search `url`, and filters:

```yaml
searches:
  - name: avito_saratov_sale
    source: avito
    url: "https://www.avito.ru/saratov/kvartiry/prodam-ASgBAgICAUSSA8YQ"
    enabled: true
    filters:
      min_price: 4000000
      max_price: 7000000
      rooms: []
      include_keywords: []
      exclude_keywords: []
```

Supported sources:

- `avito`
- `cian`
- `domclick`
- `rss`

Keep extra sources as `enabled: false` until their URLs are tuned and tested. Direct HTML
parsers can break when a platform changes markup or rate-limits traffic; RSS/API-like sources
are usually more stable.

## Notes

Use official APIs where available and keep polling intervals conservative. Some classified
platforms actively limit automated collection, so source parsers should be treated as adapters
that may need maintenance.
