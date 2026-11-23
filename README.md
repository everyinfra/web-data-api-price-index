# Web Data API Price Index

Published list prices of 39 search, scraping and CAPTCHA APIs, read from their public pricing pages
and converted to US dollars per 1,000 calls. Edition **Q4 2026** (version 2026.Q4), read on
22 November 2026.

<!-- HEADLINE:START -->
We re-read the public pricing pages of 39 search, scraping and CAPTCHA APIs on 22 November 2026 and converted every price to US dollars per 1,000 calls.
The median entry price for a search API is $3.00 per 1,000 searches (16 providers; middle half $1.00–$5.00).
Entry prices run from $0.50 (Jina, converted from token pricing) to $25.00 (SerpApi); the median of the lowest published prices is $1.25.
APIs that return Google results have a median entry price of $1.75 (n = 8); web search APIs built for AI have $5.00 (n = 8).
6 of 16 search APIs and 6 of 10 scraping and platform-data APIs can only be bought as a monthly subscription.
10 of 13 CAPTCHA solvers show no hCaptcha price on their pricing page.
Between 13 September and 22 November 2026, 4 of 39 providers changed an entry or lowest price (Exa, Oxylabs Web Scraper, Perplexity, ScrapingBee); archived copies of the earlier pages confirm each change, and every change was a decrease.
<!-- HEADLINE:END -->

The text between the two markers above is written by `recompute.py`. A check on every commit
fails if it does not match the tables.

The same tables are on Hugging Face as a dataset:
<https://huggingface.co/datasets/everyinfra/web-data-api-price-index>.
Zenodo keeps a copy of this edition with a DOI: <https://doi.org/10.5281/zenodo.24453414>.
The report that explains the numbers is at
<https://everyinfra.com/en/research/web-data-api-price-index>.

## What you can do with it

- Quote a number. Each number has the exact text from the provider's page, the time we read the
  page (Singapore time), and a link to a Wayback Machine copy saved the same day.
- Check a number. Open `archive_url` for the row and find the `price_quote`.
- Recompute everything with one command. Python 3.10 or later; no packages to install.

```bash
python3 recompute.py
```

```bash
python3 recompute.py --check
```

The first command rebuilds `index.csv`, `headlines.json` and the headline above from the raw tables.
The second command changes nothing and fails if the committed outputs differ.

## Files

| File | Content |
|---|---|
| `data/2026-q4/index.csv` | One row per provider and product: entry price, lowest price, billing, minimum payment, source and archive. Start here. |
| `data/2026-q4/headlines.json` | The headline numbers, the sentences above, one sentence per provider, and a strict variant. |
| `data/2026-q4/tiers.csv` | Every published way to pay (plan, pack, pay-as-you-go rate), with the exact page text and the result of the archive check. |
| `data/2026-q4/providers.csv` | Billing facts for each provider: minimum top-up, failed calls, free allowance, each with its page text. |
| `data/2026-q4/pages.csv` | Each page read: address, read time, SHA-256 of the rendered text, Wayback Machine copy. |
| `data/2026-q4/changes.csv` | Each price that differs from the reading of 26 September 2026, with its cause. |
| `data/2026-09-26/readings.csv` | The earlier reading (period 0). |
| `recompute.py` | Rebuilds the index and the headline from the raw tables. Standard library only. |
| `METHODOLOGY.md` | Every rule, with an example for each. Read this before you compare two providers. |
| `datapackage.json` | Frictionless Data Package description of the tables. |

The first eleven columns of `index.csv` are fixed:

```text
line,provider,source_url,read_at,unit,entry_usd_per_1k,lowest_usd_per_1k,billing,min_payment_usd,failed_calls_charged,archive_url
```

## Read this before you compare

- The index gives **list prices**, not what a customer pays after a sales call.
- **Entry price** is the price on the paid option with the smallest minimum payment. **Lowest price**
  is the lowest self-serve price, usually on the largest plan.
- One call is not the same thing at every provider. A search call returns one page of results. A
  scraping call is a standard request without JavaScript rendering. Harder targets cost more;
  `providers.csv` gives the multipliers that each page states.
- Medians hide a wide range. `headlines.json` gives the number of providers, the quartiles and the
  median when any one provider is removed.

## The publisher is also a provider

EveryInfra publishes this index and also sells APIs of these three kinds. Its rows are in the tables
with `publisher = true`, follow the same rules, and are not part of any headline number.

## Corrections

If a number is wrong, open an issue with the row and the page text that shows the error, or write
to partners@everyinfra.com. We reply within two business days. Each correction is listed in
`CHANGELOG.md` and released as a new version.

## Cite

```text
EveryInfra (2026). Web Data API Price Index, Q4 2026 (version 2026.Q4) [Data set]. Zenodo. https://doi.org/10.5281/zenodo.24453414
```

This DOI is for the Q4 2026 edition. To cite the index without naming an edition, use
<https://doi.org/10.5281/zenodo.24453413>, which always opens the latest edition.
`CITATION.cff` has the same data in machine-readable form.

## Licence

The tables and the text are licensed under [CC BY 4.0](LICENSE): you can copy and adapt them if you
name the source. Quoted text from provider pages remains the property of its owners and is here so
that you can check each number. `recompute.py` is licensed under the [MIT licence](LICENSE-CODE).
