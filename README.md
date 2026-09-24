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
commits its feed file back to the repo, so no credentials or secrets are
needed. **These workflows only fire on the default branch (`main`)**, so
they need to be merged there to actually run on schedule.

Subscribe in Feedly using this repo's raw file URL (requires the repo to
be public — see below), e.g. for Sydney:

```
https://raw.githubusercontent.com/jkkummerfeld/public-ai-experiments/main/feed/sydney-deals.xml
```

Run manually for testing:

```
python3 scripts/update_city_feed.py --city Sydney --output feed/sydney-deals.xml --dry-run
```

`--dry-run` prints new matches without writing the file. Entries already in
the feed are kept (deduped by link) up to `--max-items` (default 100) and
`--max-age-days` (default 180).

To track a new city, add a `feed/<city>-deals.xml` and copy
`.github/workflows/berlin-deal-feed.yml`, swapping in the new city name.

## COLM 2026 Paper Scout

`colm2026/index.html` is a single-page tool for finding papers to see at
COLM 2026. It covers all 856 accepted papers, with abstracts from
OpenReview and poster/oral times from the conference schedule. Write your
interests one per line and papers are ranked by embedding similarity, using
the static [model2vec](https://github.com/MinishLab/model2vec) model
`potion-base-8M` running in the browser, with a small bonus for exact
keyword matches. Star papers to get "more like your stars" suggestions and
a "My schedule" view grouped by poster session, room and board number.

Serve the folder over HTTP so the page can load the model files
(`python -m http.server -d colm2026`). Opened from `file://`, the model
can't load and the page falls back to keyword matching.

Rebuild the data (scrape, OpenReview lookup, embeddings) with:

```
pip install model2vec numpy
python colm2026/build.py
node colm2026/test_tokenizer.js   # checks the JS tokenizer against the Python one
```
