# public-ai-experiments
Space to play with AI making websites etc

## Flight deal feeds

`scripts/update_city_feed.py` checks the RSS feed of
https://www.theflightdeal.com/ for posts that mention a flight to/from a
given city, and adds any new ones to a per-city RSS feed file — a small
feed you can subscribe to directly in a reader like Feedly. Currently
tracked:

| City | Feed file | Workflow |
| --- | --- | --- |
| Sydney | `feed/sydney-deals.xml` | `.github/workflows/sydney-deal-feed.yml` |

Each city has its own GitHub Actions workflow that runs every 6 hours and
commits its feed file to the `feeds` branch, so no credentials or secrets
are needed. (`main` is protected and only accepts changes via pull
requests, so the bot never pushes there; the copies under `feed/` on
`main` are just the seed used when the `feeds` branch is first created.) **These workflows only fire on the default branch (`main`)**, so
they need to be merged there to actually run on schedule.

Subscribe in Feedly using this repo's raw file URL (requires the repo to
be public — see below), e.g. for Sydney:

```
https://raw.githubusercontent.com/jkkummerfeld/public-ai-experiments/feeds/feed/sydney-deals.xml
```

Run manually for testing:

```
python3 scripts/update_city_feed.py --city Sydney --output feed/sydney-deals.xml --dry-run
```

`--dry-run` prints new matches without writing the file. Entries already in
the feed are kept (deduped by link) up to `--max-items` (default 100) and
`--max-age-days` (default 180).

To track a new city, add a `feed/<city>-deals.xml` and copy
`.github/workflows/sydney-deal-feed.yml`, swapping in the new city name
(in the workflow name, concurrency group, `FEED_FILE`, `--city` and commit
message).
