# X → Discord: @itsyourfatb0i

A small polling service that forwards new public X posts from one account to a Discord channel via Discord Webhook.

## What it does

`@itsyourfatb0i` → X API recent search → every 60 seconds → Discord Webhook

The first run creates a baseline from the latest post, so it does NOT spam your Discord with old posts.

By default it forwards original posts/quote posts and ignores replies and retweets.

## 1. X Developer setup

Create/approve an X Developer App and copy its Bearer Token.

The current X API uses consumption-based billing. Reading Posts is currently listed at $0.005 per resource fetched, so keep the polling interval reasonable and monitor API usage.

## 2. Discord webhook

In your Discord server:

Server Settings → Integrations → Webhooks → New Webhook

Choose the target channel and copy the webhook URL.

Never publish the webhook URL or Bearer Token.

## 3. Deploy on Render

1. Put this project in a GitHub repository.
2. Go to Render and create a new Web Service from the repository.
3. Render will detect `render.yaml`, or use:
   - Build: `pip install -r requirements.txt`
   - Start: `gunicorn --workers 1 --threads 4 --timeout 120 app:app`
4. Add environment variables:
   - `X_BEARER_TOKEN`
   - `DISCORD_WEBHOOK_URL`
   - `X_USERNAME=itsyourfatb0i`
   - `POLL_SECONDS=60`
   - `INCLUDE_REPLIES=false`
5. Deploy.

## Important: free hosting sleep

If your hosting provider sleeps the service, it cannot monitor X while asleep. For dependable 24/7 monitoring, use an always-on service/VPS or a hosting plan that does not sleep.

## Faster than 60 seconds

Set `POLL_SECONDS=30` for a typical 30-second polling target, if your API budget/rate limits allow it.

For genuinely event-driven delivery, use an X streaming/event mechanism rather than polling.

## Local test

Python 3.10+:

```bash
pip install -r requirements.txt
```

Set the environment variables, then:

```bash
python app.py
```

Open `/` in a browser to see the health status.

## Troubleshooting

- 401/403 from X: check the Bearer Token and that the App has the required API access.
- 404 for the username: check `X_USERNAME`.
- Discord 401/404: recreate/copy the webhook URL.
- No Discord posts: check logs and make sure the X account is public and actually posts something after the baseline was established.
