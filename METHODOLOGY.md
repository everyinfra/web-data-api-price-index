# Methodology — Web Data API Price Index, Q4 2026 (edition 2026.Q4)

This file gives every rule that turns a public pricing page into a number in `index.csv`.
The rules were written before the pages were read on 22 November 2026. Where the reading
showed a case that the rules did not decide, the decision and the reason are in
[Decisions made during the reading](#decisions-made-during-the-reading).

## 1. What the index measures

The index records the **published, self-serve list price** of 39 web data APIs in three lines:

| Line | Providers | What one call is |
|---|---|---|
| `search` | 16 | one search query that returns one page of results (normally 10) |
| `data` | 10 | one request, record, result, page, credit or unit, as the provider bills it |
| `captcha` | 13 | one solved CAPTCHA, for five types: reCAPTCHA v2, reCAPTCHA v3, Cloudflare Turnstile, hCaptcha and normal image CAPTCHA |

All prices are US dollars per 1,000 calls. The index does not measure speed, success rate,
data quality, discounts that need a sales call, or what customers pay after negotiation.

## 2. Coverage

- The 39 providers are the ones on the public price comparison of everyinfra.com, which has
  tracked them since 26 September 2026 (period 0). This edition adds no provider and removes none.
- Providers that we did not cover in this edition include ZenRows, ScrapFly, Decodo, Crawlbase,
  ValueSERP and Scrapeless. To propose a provider for the next edition, open an issue.
- **The publisher is also a provider.** EveryInfra sells APIs in all three lines. Its rows are in
  `index.csv` with `publisher = true`, follow the same rules, and are excluded from every headline
  statistic.

## 3. How each page was read

1. **Render.** Each pricing page was opened in headless Chromium (chrome-headless-shell 1234) from
   Singapore, logged out, with the page in its default state (no toggle clicked, no cookie banner
   accepted). The rendered text, a 1440×7000 screenshot and the SHA-256 of the text were kept.
   `pages.csv` gives the read time of each page in Singapore time (SGT, UTC+8), to the minute.
2. **Archive.** On the same day, each page was saved with the Wayback Machine (Save Page Now).
   `archive_url` in `pages.csv` and `index.csv` opens that copy. We then downloaded each copy and
   confirmed that the Wayback Machine serves it at the saved timestamp. All copies are dated
   22 November 2026, between 19:19 and 21:19 SGT. Two cases are marked in `pages.csv` →
   `archive_note`: for Jina and Anti-Captcha the Wayback Machine did not store a new copy of the
   listed address that day (the page was identical to an earlier copy), so the same page was saved
   at an equivalent address (`/reader/?pricing`, `/mainpage`).
3. **Extract.** Every published way to pay for the product was copied into `tiers.csv`, one row per
   option, with the exact text from the page (`quote`, and `quote2` when a second sentence gives
   the unit). Nothing was taken from sales e-mails, documentation outside the pricing page (except
   where the pricing page links to it for prices, listed in section 9), memory or other sites.
4. **Check.** A script looked for each quote, or for the numbers in it that feed the price, in the
   archived copy of the page. The result is in `tiers.csv` → `archive_check` (section 8).

## 4. Definitions

**Option.** One way to pay: a subscription plan, a one-time credit pack, a pay-as-you-go rate, or a
pay-as-you-go volume bracket. "Contact sales", "Enterprise" and "Custom" offers are not options.

**Billing** (`billing` in `tiers.csv`):

| Value | Meaning |
|---|---|
| `subscription` | a recurring monthly plan |
| `prepaid` | a one-time pack of credits or requests, paid up front, with no recurring charge |
| `payg` | charged per use at a published rate, with no plan (a minimum top-up can apply) |
| `free` | a free allowance; never used as an entry or lowest price |

**Billing of a product** (`billing` in `index.csv`): `payg` if any pay-as-you-go option exists,
otherwise `prepaid` if any pack exists, otherwise `subscription`.
**Subscription-only** means the page offers no pay-as-you-go rate and no one-time pack.

**Base call.** The cheapest ordinary call of the product:

- If a provider sells several modes of one product at different prices (for example Lite, Auto and
  Deep search), the base call is the cheapest mode that returns ordinary results. The other modes
  stay in `tiers.csv` as recorded variants, with the product name `search:<mode>`.
  *Example:* Exa lists "Lite Search $4, Auto Search $7, Deep Search $12" per 1,000 requests; the
  base call is Lite Search, $4.00.
- Only synchronous calls count (the result comes back in the same HTTP call). Queued or
  asynchronous modes are recorded with `async = true` and are not used.
  *Example:* DataForSEO's "Standard queue … $0.60 per 1K" is asynchronous; its "Live mode …
  $2.00 per 1K" is the base call.
- For credit-billed products, the base call is a standard request with no JavaScript rendering, no
  premium proxy and no special target. `units_per_call` is the number of credits it costs.
- When a page gives one price range across endpoints or modes without saying which costs what,
  the base call uses the low end of the range.

**Entry price** (`entry_usd_per_1k`). The price per 1,000 base calls on the paid option with the
smallest minimum spend: the pay-as-you-go rate if one exists (its highest volume bracket, or the
high end of a range that the page gives for one product), otherwise the cheapest one-time pack, otherwise
the cheapest monthly plan. A range across modes or endpoints is not a volume range: the base-call
rule above applies, so the entry price and the lowest price both use its low end.
**Lowest price** (`lowest_usd_per_1k`). The lowest price per 1,000 base calls among all paid
self-serve options of the same product (the low end of any range).

*Example (Serper):* "$50* 50k credits ($1.00/1k) Submit 50,000 queries" is the smallest pack, so
the entry price is $1.00. "$3750* 12.5M credits ($0.30/1k)" is the largest, so the lowest price is
$0.30.

**Minimum payment** (`min_payment_usd`). The smallest amount a new customer must pay: the stated
minimum top-up for pay-as-you-go (blank when the page does not state one), otherwise the cheapest
pack or monthly plan.

**Failed calls** (`failed_calls_charged`). `true`, `false` or `partial` only when the pricing page
says whether failed or unsuccessful calls are billed; the sentence is in `providers.csv`. `false`
includes pages that price "successful" requests or responses only. `partial` means the page frees
only some kinds of failure (for example Firecrawl bills pages that answer 403 or 404, and
EnsembleData frees only "failed requests caused by internal errors"). Blank means the page does
not say.

**Unit** (`unit` in `index.csv`). What one of the 1,000 calls is: `request` for search APIs and for
most scraping APIs, `result` or `record` where the provider bills each returned item, `solve` for
CAPTCHA solvers.

**Volume prices** (`usd_per_1k_at_10k`, `_100k`, `_1m`). The cheapest published way to buy 10,000,
100,000 or 1,000,000 base calls in one month, per 1,000: a single flat pay-as-you-go rate, repeated
one-time packs, or one plan plus its published overage rate. Graduated pay-as-you-go brackets are
not modelled, so those cells are blank. These columns are indicative and are not used in headlines.

## 5. Conversions

Every conversion uses numbers printed on the page. `derived = true` in `index.csv` marks a price
that needs more than dividing a published price by a published number of units; `conversion`
says what was done.

| Case | Rule | Example |
|---|---|---|
| Credits | price per 1,000 base requests = price per 1,000 credits × credits per base request | ScraperAPI Hobby: "$49 /month … 100,000 API Credits"; "A standard page costs 1 credit" → $0.49 |
| Per 10 results | one call = one page of 10 results | Firecrawl Search: "Search costs 2 credits per 10 results"; Hobby "$19/month … 5,000 credits" → 2,500 searches → $7.60 |
| Credits per search call | as stated | Scrapingdog: "Google SERP Light API 5 credits / req"; Lite "$40/month 200,000 … Credits" → 40,000 searches → $1.00 |
| Tokens | price per token × tokens per call | Jina: "$50 … 1 Billion tokens"; "Every request costs a fixed number of tokens, starting from 10,000 tokens" → $0.50 per 1,000 searches, a lower bound |
| Daily allowance | units per day × 30 | EnsembleData Wood: "1,500 units / day $100 / month" → 45,000 units a month → $2.22 per 1,000 units |
| Monthly vs annual | the monthly price | Firecrawl Hobby "$19/month billed monthly ($16/month billed annually)" → $19 |
| Currency | the page's US dollar price | Firecrawl showed Singapore dollar cards to a Singapore reader; the page's own "Pricing at a glance" gives the US dollar prices used |

In the text of the report, credit-billed prices are given per 1,000 base requests; the credit
multipliers for harder targets are in the notes (for example, ScraperAPI: "Amazon costs 5, Google
and Bing … cost 25, and LinkedIn costs 30").

## 6. CAPTCHA rows

- Five rows per provider, one per type (`recaptcha_v2`, `recaptcha_v3`, `turnstile`, `hcaptcha`,
  `image`). Enterprise variants are not the base type.
- A type with no price on the rendered pricing page has `listed = false`. The headline counts
  providers whose pricing page shows no hCaptcha price; it does not say whether they can solve
  hCaptcha. The count includes NopeCHA and TrueCaptcha, which publish one plan or one price that is
  not split by type. Values that are in the page source but not displayed are not prices on the page
  (see 2Captcha in the decisions table).
- A range (for example 2Captcha "reCAPTCHA v2 … $1 — $2.99 Price per 1000"; the page does
  not say what sets the price inside the range) gives the high end as the entry price and the low end as the lowest price.
- Plans that are not tied to one type (NopeCHA's daily-solve plans) are in a sixth row, `any`.

## 7. Headline statistics

- Median and quartiles use Python's `statistics.median` and `statistics.quantiles(n=4,
  method="inclusive")`. With an even number of providers, the median is the mean of the two middle
  values, which may be a price that no provider charges.
- Every headline gives its number of providers (n). `headlines.json` also gives the leave-one-out
  range: the lowest and highest median when any one provider is removed.
- Search providers are also split into two segments, from each provider's own product description:
  `google_serp` (APIs that return Google or Bing result pages) and `web_search` (the provider's own
  index or a search API for AI use).
- Rounding in sentences: two decimals for prices of $0.10 and more, three below. The CSV keeps four
  decimals.

## 8. Verification

`archive_check` in `tiers.csv` gives the result of the script check of each option against the
archived copy (the Wayback `id_` copy, which is the page as the server sent it):

| Value | Meaning |
|---|---|
| `VERBATIM` | the quote, with spaces normalised, is in the text of the archived page |
| `VERBATIM(source)` | the quote is in the HTML source of the archived page (for example an attribute) |
| `NUMBERS(text)` | the numbers of the quote that feed the price are in the archived text, in order, within 400 characters |
| `NUMBERS(source)` | the same, in the HTML source of the archived page (prices inside scripts or attributes) |
| `VERBATIM(data)` | the page fills the price by script from a public data address; the exact text in `evidence_quote` is in the archived copy of that address (`evidence_page`), saved the same day |
| `MISSING` | not found in any archived copy |
| `n/a` | the row has no number (a type with no listed price) |

Result for this edition: for 37 of the 39 providers, every option used for an entry or lowest price
passes on the archived page itself. For the other two (Jina and Capzy) the archived page has no
digits, because the page loads its prices from a data address after it opens; the check passes on
the archived copy of that address. Their numbers are therefore checked by script, but a reader who
opens `archive_url` in a browser does not see the price on the page. `headlines.json` →
`strict` gives the headline numbers without these two providers.

One more page needs the source view. The Bright Data SERP page keeps its prices in `data-usd` and
`data-tiers` attributes; in the Wayback Machine replay the price slots stay empty ("$ /1K
requests"). The numbers are in the archived HTML: open `archive_url`, view the page source and
search for `data-usd` or `data-tiers`. We opened the replays of the other pages checked at source
level (SerpApi, Anti-Captcha, Bright Data Web Scraper) in a browser on 22 November 2026, and they
show their prices.

45 rows of `tiers.csv` are `MISSING`. None of them sets an entry or lowest price. 44 are larger
plans that the page draws by script (AZcaptcha plan cards AZ2 to AZ12), kept for completeness, and
one is the free tier of Bright Data Web Scraper.

A lone short number ("1", "5") is not accepted as a match. `unsupported_values` in `tiers.csv` must
be empty for every row used in the index: it lists a number of the row that no quote supports.

To check a number yourself: open `archive_url` for the row's page and find the `quote`.

## 9. Pages read in addition to the main pricing page

Some pricing pages give per-item prices on linked pages. These were read and archived the same way:
Tavily's API credits page (credits per search), the pricing tabs of five Apify Store actors, and
EveryInfra's CAPTCHA list (its pricing page says "Each type page shows its published base price").

**Apify Store.** Prices are set per actor. The sample is the first five actors on Apify's "Social
media scrapers" category page on the read date. Each actor has a price per Apify plan; the entry
price is the Starter plan price (the cheapest paid plan, $19 a month) and the lowest price is the
Business plan price. The billing of Apify Store is the billing of the Apify platform plans.

## 10. Comparison with period 0 (26 September 2026)

Period 0 is the reading published on everyinfra.com on 26 September 2026 (`data/2026-09-26/`). It
has no archived copies of its own. A price counts as different when it moved by more than half a
cent. Each different price has one row in `changes.csv`, with the Wayback copy of the page that
is the latest on or before 26 September 2026 (`prior_archive_url`), a quote from it, and a cause:

| Cause | Meaning |
|---|---|
| `price_change` | the earlier copy shows the period-0 price, and the page now shows another price |
| `rule` | the earlier copy shows the same figures as today; the numbers differ because this edition applies a rule that period 0 did not (monthly billing, no queued modes, no sales-only offers, pay-as-you-go as entry) or because period 0 read another figure on the page |
| `unverified` | no earlier copy shows the period-0 price |

Only `price_change` rows are counted as price changes in the report.

The earlier copy is older than the previous reading, so a `price_change` row also has a `timing`:

| Timing | Meaning |
|---|---|
| `after` | a copy dated after 26 September 2026 still shows the higher price, so the price fell after the previous reading |
| `around` | the price fell between two copies, one before and one after 26 September 2026; the archives cannot place it on either side |
| `before` | the provider's own records date the change before 26 September 2026; the previous reading recorded a price that was already out of date |

The headline sentence counts all three. It starts at the date of the oldest earlier copy that it
uses, not at the previous reading. In this edition that date is 13 September 2026: two changes are
`after` (Oxylabs Web Scraper, ScrapingBee), one is `around` (Exa, between 19 and 29 September) and
one is `before` (Perplexity, 24 September; the `note` column of `changes.csv` gives the announcement and the two changelog copies that date it).

A price that the nearest earlier copy shows lower than today, and that period 0 recorded at another
figure, stays `unverified`: AZcaptcha Turnstile was $0.90 in the copy of 9 June 2026 and is $1.00
now, and no copy dates that rise.

## 11. Known limits

- Prices shown to a Singapore reader can differ from those shown to readers elsewhere. The archived
  copies were made by the Wayback Machine from the United States and are the reference.
- Pricing pages change without notice. The index is a reading on one day, not a price guarantee.
- Pay-as-you-go minimum top-ups are often not on the pricing page; those cells are blank. DeathByCaptcha
  and BestCaptchaSolver show their top-up amounts only after login.
- Pages were read in their default state. Tabs that were not opened are not in the index: the
  "/Search" tab of the Oxylabs page (the Oxylabs Google row is the Google price of the default tab)
  and the "Subscription" tab of the Anti-Captcha page.

## 12. Corrections and versions

Report an error by opening an issue in this repository or by e-mail to partners@everyinfra.com. We
reply within two business days. Each correction is listed in `CHANGELOG.md` and released as a new
version (2026.Q4.1, 2026.Q4.2, …); each version gets its own DOI under the same concept DOI.

## 13. Licence

The compilation and the derived values (the CSV tables, `headlines.json`, this text) are licensed
under CC BY 4.0. Quoted text and screenshots of provider pages remain the property of their owners
and are reproduced only so that readers can verify each number. `recompute.py` is MIT-licensed.

## Decisions made during the reading

| Provider | Case | Decision |
|---|---|---|
| Bright Data (SERP, Web Scraper) | The pages store prices in `data-usd` attributes and write the visible number by script. The SERP page's Scale plan has a slider ("Slide to adjust plan") whose three steps are in a `data-tiers` attribute | Prices taken from the attributes (`data-usd="1.5"`, `"499"`; slider steps $499 for 380K, $999 for 900K and $1,999 for 2M requests), which are also in the archived HTML source. The lowest SERP price is the third step, $1,999 / 2,000,000 requests |
| ScraperAPI | The Professional and Advanced plan cards print "10,500,000 API Credits" and "21,500,000 API Credits" under "LIMITED OFFER · +250K BONUS CREDITS" and "+500K BONUS CREDITS"; the page does not say whether the figures include the bonus | The printed figure is used ($1,975 / 21,500,000 credits = $0.0919 per 1,000). The same cards are in the Wayback copy of 14 September 2026. If the bonus were on top of 21,000,000 credits, the lowest price would be $0.0940 |
| 2Captcha | The pricing table on the rendered page has no hCaptcha row; the page source holds a price map with `"hCaptcha":2.99` that the page does not display | hCaptcha is `listed = false`: the index reads what a buyer sees on the page |
| Zyte | "From $0.06 per 1,000 successful responses" | `failed_calls_charged = false`, the same reading as Serper ("Every time you receive successful responses to queries, we will deduct credits") and Bright Data ("Pay only for success") |
| EveryInfra (publisher) | One range for search, "$0.69–$2.78 per 1,000 requests", by search tool | Base call uses $0.69, the same low-end rule as Linkup and TikHub; the row is not in any headline |
| Jina, Capzy | The pages load prices from a data address after they open; the archived pages show no price | The archived copy of the data address is the reference for the check (section 8) |
| Perplexity | Two search modes: standard $5.00 and Fast Search $1.00, "Lower-latency results in the same response format" | Base call is Fast Search ($1.00); standard is a recorded variant |
| Oxylabs (Google) | Separate prices with and without JavaScript rendering | Base call is the non-JavaScript request |
| Linkup | The pricing page gives one range, "$0.005 - $0.006", for Fast, Standard and Deep search. Linkup's documentation prices deep search at $0.05 a request | Base call uses $0.005, the low end of the range on the pricing page; the documentation price for deep search is not on the pricing page and is not used |
| TikHub | Per-request range "$0.001 – $0.01" across endpoints | Base call uses $0.001; the range is a multiplier note |
| AZcaptcha | The page says "No subscriptions" and also sells AZ1–AZ12 monthly plans; the rate table has a second price column under "Plan from $24.9/month" | The plans are self-serve monthly options and are included at the rate of that column; the contradiction is noted |
| CapSolver | Prices "USD / 1000 tokens" without a definition of token | Read as 1,000 solved tasks |
| TrueCaptcha | One price "$0.33 USD for 1000 captchas" with no type, and a banner "The service is currently down" | Recorded as image CAPTCHA; the banner is in `providers.csv` → `service_notice` |
| NopeCHA | Only daily-solve plans | Recorded in the `any` row; per-type rows are `listed = false` |
