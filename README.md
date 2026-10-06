# Skrapper

Telegram bot that checks apartment listing pages and sends new matching ads to a chat.

## What it does

- Polls configured search URLs on a schedule.
- Normalizes listings from source-specific parsers.
- Filters by price, rooms, include keywords, and exclude keywords.
- Stores seen listings locally to avoid duplicate Telegram messages.
- Performs a first-run baseline sync per search, so existing listings are not spammed.
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
- `yandex`
- `youla`
- `n1`
- `gdeetotdom`
- `akula`
- `saratov_nedvizhimost`
- `rss`

## Email Alerts

Some platforms block direct scraping with CAPTCHA or authorization. For those sources, use their
own saved-search notifications and let Skrapper read those emails over IMAP.

1. Create a separate mailbox for listing alerts.
2. Save searches on Cian, Domclick, Yandex Realty, Avito, and other platforms.
3. Enable email notifications for those saved searches.
4. Fill IMAP settings in `.env`:

```text
EMAIL_IMAP_HOST=imap.example.com
EMAIL_IMAP_PORT=993
EMAIL_IMAP_USERNAME=flat.alerts@example.com
EMAIL_IMAP_PASSWORD=app-password
EMAIL_IMAP_USE_SSL=true
```

5. Enable the source in `config.yaml`:

```yaml
email_alerts:
  enabled: true
```

The first successful email scan is also a baseline sync: existing emails are saved without
Telegram spam, and later matching emails become notifications.

Keep extra sources as `enabled: false` until their URLs are tuned and tested. Direct HTML
parsers can break when a platform changes markup or rate-limits traffic; RSS/API-like sources
are usually more stable.

## Fresh listings only

Each enabled search has its own bootstrap state in SQLite. On the first successful fetch for a
search, Skrapper saves the current listings without sending them. After that baseline is done,
only listings that were not observed before are eligible for Telegram notifications.

Useful bot commands:

- `/check` runs all enabled searches now and reports fetched/new/sent counts.
- `/status` shows stored listing counts and per-search health.
- `/chatid` prints the chat id that should be used in `.env`.

## Notes

Use official APIs where available and keep polling intervals conservative. Some classified
platforms actively limit automated collection, so source parsers should be treated as adapters
that may need maintenance.
