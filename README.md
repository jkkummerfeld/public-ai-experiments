# public-ai-experiments
Space to play with AI making websites etc

## Sydney flight deal feed

`scripts/update_sydney_feed.py` checks the RSS feed of
https://www.theflightdeal.com/ for posts that mention a flight to/from
Sydney, and adds any new ones to `feed/sydney-deals.xml` — a small RSS feed
you can subscribe to directly in a reader like Feedly.

A GitHub Actions workflow (`.github/workflows/sydney-deal-feed.yml`) runs
this every 6 hours and commits the updated feed file back to the repo, so
no credentials or secrets are needed. **The workflow only fires on the
default branch (`main`)**, so it needs to be merged there to actually run
on schedule.

Subscribe in Feedly using this repo's raw file URL (requires the repo to
be public — see below):

```
https://raw.githubusercontent.com/jkkummerfeld/public-ai-experiments/main/feed/sydney-deals.xml
```

Run manually for testing:

```
python3 scripts/update_sydney_feed.py --output feed/sydney-deals.xml --dry-run
```

`--dry-run` prints new matches without writing the file. Entries already in
the feed are kept (deduped by link) up to `--max-items` (default 100) and
`--max-age-days` (default 180).
