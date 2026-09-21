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
  - name: avito_moscow_rent
    source: avito
    url: "https://www.avito.ru/..."
    enabled: true
    filters:
      min_price: 50000
      max_price: 120000
      rooms: [1, 2]
      include_keywords: ["метро"]
      exclude_keywords: ["апартаменты"]
```

## Notes

Use official APIs where available and keep polling intervals conservative. Some classified
platforms actively limit automated collection, so source parsers should be treated as adapters
that may need maintenance.

