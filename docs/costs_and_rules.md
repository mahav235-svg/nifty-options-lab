# NIFTY options: data sources, rules and costs (research notes)

Compiled 18 Oct 2026. Every fact carries a source URL and a date. "Accessed 18 Oct 2026" means the page itself shows no publication date. Anything not confirmed on an official page (exchange, regulator, Budget, broker's own docs) is marked **unconfirmed**. Broker community posts by broker staff are treated as semi-official and labelled as such.

NSE circular PDFs were read directly from `https://nsearchives.nseindia.com/content/circulars/<REF>.pdf`. SEBI circular PDFs were read from `sebi.gov.in/sebi_data/attachdocs/...`.

---

## Part A. Historical data sources

### A1. Upstox API

**Plain historical candles (v3)**

- Endpoint: `GET https://api.upstox.com/v3/historical-candle/{instrument_key}/{unit}/{interval}/{to_date}/{from_date}`. Note `to_date` comes before `from_date`. Pipe in keys is URL-encoded (`NSE_INDEX%7CNifty%2050`). Source: https://upstox.com/developer/api-documentation/v3/get-historical-candle-data/ (accessed 18 Oct 2026).
- Units and depth (same page):

  | unit | interval | history | max range per call |
  |---|---|---|---|
  | minutes | 1 to 300 | from Jan 2022 | 1 month for 1 to 15 min; 1 quarter above 15 min |
  | hours | 1 to 5 | from Jan 2022 | 1 quarter |
  | days | 1 | from Jan 2000 | 1 decade |
  | weeks, months | 1 | from Jan 2000 | not stated |

- Candle array: timestamp (ISO, +05:30), O, H, L, C, volume, OI. India VIX is available as `NSE_INDEX|India VIX`. Same page.
- Auth: doc samples send a Bearer token, but Upstox staff (Anand_Sajankar) stated on 12 Feb 2026 that the v3 historical and intraday candle endpoints "do not require an access token, as these are data endpoints and are open to all users." Source: https://community.upstox.com/t/critical-security-bug-v3-historical-intraday-data-not-protected/14072 (12 Feb 2026). Staff post, not docs, so treat as **semi-official**; the v2 endpoint still appeared to need a token in that thread.
- Historical Candle Data V3 and Instrument Search are available on all plans. Source: https://upstox.com/developer/api-documentation/backtesting/ (accessed 18 Oct 2026).
- Coverage of F&O: this endpoint serves live contracts only. Expired contracts need the Expired Instruments APIs below (backtesting page).
- v2 endpoint `GET https://api.upstox.com/v2/historical-candle/{instrument_key}/{interval}/{to_date}/{from_date}` is marked Deprecated. Its page contradicts itself on 1-minute depth (one place says 1 month, the notes say 6 months). Source: https://upstox.com/developer/api-documentation/get-historical-candle-data/ (accessed 18 Oct 2026).
- Rate limits: non-order APIs (incl. historical candles) 50/s, 500/min, 2,000 per 30 min, per user. Source: https://upstox.com/developer/api-documentation/rate-limiting/ (accessed 18 Oct 2026).
- Gotchas: exceeding the range limit returns error UDAPI1148 instead of truncating; current-day data needs the Intraday Candle endpoint; 1-minute index history therefore starts Jan 2022, not earlier.

**Expired Instruments APIs (all v2, all need Upstox Plus)**

| Purpose | Path |
|---|---|
| Expiries | `GET https://api.upstox.com/v2/expired-instruments/expiries?instrument_key=NSE_INDEX%7CNifty%2050` |
| Expired option contracts | `GET https://api.upstox.com/v2/expired-instruments/option/contract?instrument_key=...&expiry_date=YYYY-MM-DD` |
| Expired future contracts | `GET https://api.upstox.com/v2/expired-instruments/future/contract?...` (path per docs index; page not opened, **unconfirmed** exact params) |
| Expired candles | `GET https://api.upstox.com/v2/expired-instruments/historical-candle/{expired_instrument_key}/{interval}/{to_date}/{from_date}` |

- Sources: https://upstox.com/developer/api-documentation/get-expiries/ , https://upstox.com/developer/api-documentation/get-expired-option-contracts/ , https://upstox.com/developer/api-documentation/get-expired-historical-candle-data/ (all accessed 18 Oct 2026).
- Plan: error UDAPI1149 "available exclusively with an Upstox Plus plan subscription" on each page. Plus pricing: the Plus T&C PDF says the plan "can be activated for free initially" with advance notice if it becomes chargeable. https://upstox.com/files/terms-and-condition/plus-pack.pdf (accessed 18 Oct 2026). No fee figure found on https://upstox.com/plus/ . Trading brokerage under Plus is shown as Rs 30 per F&O order vs Rs 20 on Basic: https://upstox.com/help-center/what-are-the-benefits-of-upstox-plus-264070/ (accessed 18 Oct 2026). That looks odd but it is what the page says.
- Depth: Get Expiries returns "up to six months of historical expiries" (expiries page). So expired intraday data from Upstox is only a rolling ~6-month window, not years.
- Expired key format: `NSE_FO|<exchange_token>|<DD-MM-YYYY>`, e.g. `NSE_FO|47983|17-04-2025`. Request dates are YYYY-MM-DD but the key embeds DD-MM-YYYY.
- Intervals for expired candles: 1minute, 3minute, 5minute, 15minute, 30minute, day. Max range per call not stated.
- Workflow (backtesting page): Instrument Search, then Expiries, then Expired Option Contracts, then Expired Candles. Upstox recommends chunking and backoff.
- Gotcha: one user reported the Expired Instruments toggle missing even with Plus active: https://community.upstox.com/t/expired-instruments-api-toggle-missing-in-developer-console-plus-plan-active/11428 (community, **unconfirmed**).

### A2. Groww Trade API

- Price: Rs 499/month plus taxes ("early bird"; Rs 2,000 shown struck through). Pricing box lists "Historical data, up to 3 months". Source: https://groww.in/trade-api (accessed 18 Oct 2026). This conflicts with the backtesting docs below, which say data from 2020. Groww's blog says the free trial does not include historical candles used for backtesting (search snippet of https://groww.in/blog/api-trading-on-groww , **unconfirmed** on page).
- Backtesting endpoints (added 3 Oct 2025 per changelog https://groww.in/trade-api/docs/curl/changelog):
  - `GET https://api.groww.in/v1/historical/expiries` (exchange, underlying_symbol, year, month)
  - `GET https://api.groww.in/v1/historical/contracts` (exchange, underlying_symbol, expiry_date)
  - `GET https://api.groww.in/v1/historical/candles` (exchange, segment CASH/FNO, groww_symbol, start_time, end_time, candle_interval)
  - Source: https://groww.in/trade-api/docs/curl/backtesting (accessed 18 Oct 2026).
- Symbol format: `NSE-NIFTY-04Jan24-19200-CE`.
- History: equities, indices and FNO from 2020; expiries lookup also from 2020 (same page).
- Granularity and max range per call: 1/2/3/5 min = 30 days; 10/15/30 min = 90 days; 1h/4h/1d/1w/1M = 180 days.
- Expired contracts: the docs' worked example pulls Jan 2024 expiries and contracts, which implies expired contracts are covered, but the page never says so outright. **Unconfirmed** until tested.
- Rate limits (docs intro): Orders 10/s, 250/min; Live Data 10/s, 300/min; Non-trading 20/s, 500/min; token generation 5/s, 30/min, 150/day. Historical endpoints are not listed separately. Source: https://groww.in/trade-api/docs/curl (accessed 18 Oct 2026).
- Auth: access token expires daily at 6:00 AM; API key + secret or TOTP flows need daily approval (same page).

### A3. ICICI Direct Breeze API

- Cost: "No charges at all to connect your systems, creating apps or for access to the historical data." Source: https://api.icicidirect.com/apiuser/home (accessed 18 Oct 2026). ICICI FAQ agrees Breeze is free: https://www.icicidirect.com/faqs/fno/what-is-the-cost-or-fees-for-using-breeze-api (accessed via search 18 Oct 2026).
- Historical v2 endpoint: `GET https://breezeapi.icicidirect.com/api/v2/historicalcharts`, headers `X-SessionToken` and `apikey`. Options need `expiry_date`, `right`, `strike_price`; `product_type` futures/options/cash. Source: https://api.icicidirect.com/breezeapi/documents/index.html (accessed 18 Oct 2026). The REST doc lists 1minute, 5minute, 30minute, 1day only.
- 1-second data: the official Python SDK readme lists "1second" for options under `get_historical_data_v2` and caps a call at 1,000 candles. Source: https://pypi.org/project/breeze-connect/ (v1.0.69, 14 Apr 2026). The REST doc does not list 1second, so treat 1-second availability for futures and via raw REST as **unconfirmed**.
- Depth: conflicting official claims. Home page says "3 years of second level LTP data" and "3 years of Futures and Options historical data"; the SDK readme says "10 years of historical market data including 1 sec OHLCV." Plan for 3 years until tested.
- Expired options: not addressed in official docs (**unconfirmed**). A third-party package (https://pypi.org/project/breeze-historical-options/) pulls second-level options history by expiry and strike, which suggests it works.
- Rate limits: 100 calls/minute and 5,000 calls/day; separate cap of 10 orders/second. Orders must come from the registered static IP, changeable once a week; market orders not permitted via API. Source: Breeze docs page above (accessed 18 Oct 2026).

### A4. DhanHQ expired options ("rolling option") API

- Endpoint: `POST https://api.dhan.co/v2/charts/rollingoption`. Body: exchangeSegment, interval (1, 5, 15, 25, 60 minutes), securityId (underlying), instrument (e.g. OPTIDX), expiryFlag (WEEK/MONTH), expiryCode, strike (ATM, ATM+n / ATM-n), drvOptionType (CALL/PUT), requiredData (open, high, low, close, iv, volume, strike, oi, spot), fromDate, toDate (non-inclusive). Source: https://dhanhq.co/docs/v2/expired-options-data/ (accessed 18 Oct 2026).
- Strikes: up to ATM±10 for index options near expiry, ATM±3 otherwise (same page). Strikes are relative to ATM at each minute, so you get a continuous ATM-relative series, not a fixed contract.
- Depth: "up to the last 5 years" (so roughly Oct 2021 onward from today). Max 30 days per call.
- Cost: DhanHQ Data API is Rs 499 + taxes per month, 30-day renewal; free-with-trades promo discontinued. Sources: https://dhan.co/support/platforms/dhanhq-api/is-the-dhanhq-data-api-subscription-free-if-i-execute-a-minimum-number-of-trades-every-month/ and https://dhan.co/support/platforms/dhanhq-api/how-does-the-dhanhq-data-api-subscription-work/ (accessed via search 18 Oct 2026). Trading APIs are free: https://dhan.co/pricing/ (accessed 18 Oct 2026).
- Rate limits: Data APIs 5/s and 100,000/day; Order APIs 10/s, 250/min, 1,000/hour, 7,000/day. Source: https://dhanhq.co/docs/v2/ (accessed 18 Oct 2026).
- Gotchas: daily historical is T-1 (support FAQ above); ATM-relative series means strike identity changes through the day, so reconstructing a fixed-strike position needs care (use the returned `strike` field).

### A5. Zerodha Kite Connect

- Price: Personal plan free (no historical or live data); Connect plan Rs 500 per app per month includes historical candles and WebSocket data. From Oct 2026, users with Rs 2,000+ monthly brokerage get 500 Developer Credits covering the next month. Source: https://support.zerodha.com/category/trading-and-markets/general-kite/kite-api/articles/what-are-the-charges-for-kite-apis (accessed 18 Oct 2026). Historical add-on fee dropped from 8 Feb 2025 (Zerodha support, via search, **unconfirmed** on page).
- Endpoint: `GET https://api.kite.trade/instruments/historical/{instrument_token}/{interval}?from=...&to=...&continuous=0|1&oi=0|1`. Intervals: minute, 3minute, 5minute, 10minute, 15minute, 30minute, 60minute, day. Source: https://kite.trade/docs/connect/v3/historical/ (accessed 18 Oct 2026).
- Expired options: not supported in practice. Instrument dump lists only live contracts; `continuous=1` gives day candles for futures only. Zerodha staff have said intraday candles are not provided for expired instruments (forum, via search, **unconfirmed** on docs).
- Rate limits: historical 3 req/s; quotes 1/s; orders 10/s, 400/min, 5,000/day. Source: https://kite.trade/docs/connect/v3/exceptions/ (accessed 18 Oct 2026).

### A6. NSE free archives

**Old F&O bhavcopy**

- URL pattern: `https://nsearchives.nseindia.com/content/historical/DERIVATIVES/{YYYY}/{MON}/fo{DD}{MON}{YYYY}bhav.csv.zip`, e.g. `.../2019/JAN/fo01JAN2019bhav.csv.zip`.
- Range verified on 18 Oct 2026 by 1-byte range requests: files exist for 12 Jun 2000, 4 Jan 2010, 1 Jan 2016, 1 Jan 2019, 5 Jul 2024; 8 Jul 2024 returns 404. So coverage is 12 Jun 2000 to 5 Jul 2024. A plain HEAD request returns 503, so use GET with a browser user-agent.
- Columns (old format): INSTRUMENT, SYMBOL, EXPIRY_DT, STRIKE_PR, OPTION_TYP, OPEN, HIGH, LOW, CLOSE, SETTLE_PR, CONTRACTS, VAL_INLAKH, OPEN_INT, CHG_IN_OI, TIMESTAMP. **Unconfirmed** on an official page (TradingQnA shows the first five plus OPEN_INT, CHG_IN_OI: https://tradingqna.com/t/read-nse-fno-bhavcopy/42141). Verify by reading one file's header.

**UDiFF common bhavcopy**

- URL pattern: `https://nsearchives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_{YYYYMMDD}_F_0000.csv.zip`.
- Verified 18 Oct 2026 by HEAD: 30 Sep 2026, 8 Jul 2024, 5 Jul 2024, 2 Jan 2024 and 1 Jan 2024 exist; 29 Dec 2023, 1 Nov 2023, 3 Jul 2023, 3 Jan 2022, 1 Jan 2019 return 404. So UDiFF history starts 1 Jan 2024, overlapping the old format until 5 Jul 2024.
- Columns: TradDt, BizDt, Sgmt, Src, FinInstrmTp, FinInstrmId, ISIN, TckrSymb, SctySrs, XpryDt, FininstrmActlXpryDt, StrkPric, OptnTp, FinInstrmNm, OpnPric, HghPric, LwPric, ClsPric, LastPric, PrvsClsgPric, UndrlygPric, SttlmPric, OpnIntrst, ChngInOpnIntrst, TtlTradgVol, TtlTrfVal, TtlNbOfTxsExctd, SsnId, NewBrdLotQty, Rmks, Rsvd1 to Rsvd4. Confirmed against downloaded files (no official spec found). Note TtlTradgVol is in contracts: TtlTrfVal divided by price and lot size matches it (checked on 14 Oct 2025 rows). NewBrdLotQty gives the lot size per row, which is the safest way to get lot size during transition periods.

**Format switch**

- NSE circular NSE/INVG/61292 (22 Mar 2024) first scheduled the old `foDDMMMYYYYbhav.csv.zip` for discontinuation on 20 May 2024. https://nsearchives.nseindia.com/content/circulars/INVG61292.pdf
- The actual cutoff was moved: NSE's derivatives reports page states the old files were discontinued w.e.f. 8 Jul 2024 per NSE circular 62424 dated 12 Jun 2024 (seen in search snippet of https://www.nseindia.com/all-reports-derivatives ; circular PDF not retrieved, so the circular itself is **unconfirmed**). This matches the file probe above (last old file 5 Jul 2024).

**India VIX daily**

- NSE page: https://www.nseindia.com/reports-indices-historical-vix (responds 200, 18 Oct 2026). Date-range download. Also available through Upstox v3 historical candles as `NSE_INDEX|India VIX` (daily from Jan 2000 per Upstox doc; actual VIX start is later, **unconfirmed**).

**NIFTY index daily**

- https://www.niftyindices.com/reports/historical-data (responds 200, 18 Oct 2026). Gives price, total return and PE/PB/div yield by date range. Download mechanics not checked (**unconfirmed**). Upstox v3 daily candles for `NSE_INDEX|Nifty 50` are an easier programmatic route.

### A7. Free 1-minute NIFTY history

- Kaggle, "NIFTY 50 minute data" by user debashis74017: https://www.kaggle.com/datasets/debashis74017/nifty-50-minute-data (page responds 200, 18 Oct 2026). Description per a mirror listing says Jan 2015 to Aug 2024, 1/3/5/15-minute and hourly, index only, no volume. Mirror: https://baselight.app/u/kaggle/dataset/debashis74017_nifty_50_minute_data . Same author has a NIFTY Bank minute dataset. Coverage **unconfirmed** until downloaded. Not an exchange source; check for gaps and timestamp conventions.
- IEEE DataPort has a NIFTY50 1-minute close-only dataset 2015 to 2022 (search result https://ieee-dataport.org/comment/9072 , **unconfirmed**).
- No free 1-minute NIFTY futures dataset was found.
- Best free programmatic alternative: Upstox v3 1-minute index candles from Jan 2022 (A1).

---

## Part B. Rules and costs for a 2019 to 2026 backtest

### B1. Lot sizes

General rule: during transitions, contracts with old and new lot sizes trade side by side. Take lot size from the contract record (UDiFF `NewBrdLotQty`, Upstox `lot_size`) rather than from a date lookup.

**NIFTY**

| Lot | Applies to | Source |
|---|---|---|
| 75 | In force at start of 2019 (present lot in the Mar 2021 circular) | NSE/FAOP/47854, 31 Mar 2021 |
| 50 | July 2021 monthly onward; weeklies from Aug 2021; long-dated options moved after 25 Jun 2021 expiry. Circular effective 30 Apr 2021 | https://nsearchives.nseindia.com/content/circulars/FAOP47854.pdf (31 Mar 2021) |
| 25 | All contracts trading from 26 Apr 2024; first weekly 2 May 2024; first monthly 30 May 2024; Apr 2024 monthly (25 Apr) stayed 50 | https://nsearchives.nseindia.com/content/circulars/FAOP61415.pdf (2 Apr 2024) |
| 75 | New contracts from 20 Nov 2024 (SEBI Rs 15 lakh minimum). Last weekly at 25: 19 Dec 2024; first weekly at 75: 2 Jan 2025. Last monthly at 25: 30 Jan 2025; first at 75: 27 Feb 2025. Quarterly/half-yearly switched 26 Dec 2024 EOD | https://nsearchives.nseindia.com/content/circulars/FAOP64625.pdf (18 Oct 2024) |
| 75 | Unchanged in the Mar 2025 revision | https://nsearchives.nseindia.com/content/circulars/FAOP67372.pdf (28 Mar 2025) |
| 65 | Circular effective 28 Oct 2025 EOD. Last weekly at 75: 23 Dec 2025; first weekly at 65: 6 Jan 2026. Last monthly at 75: 30 Dec 2025; first at 65: 27 Jan 2026. Quarterly/half-yearly switched 30 Dec 2025 EOD | https://nsearchives.nseindia.com/content/circulars/FAOP70616.pdf (3 Oct 2025) |

No NSE lot revision after the Oct 2025 circular was found (one search, nothing found). SEBI's Dec 2024 framework (SEBI/HO/MRD-PoD2/CIR/P/2024/00181, cited in FAOP70616) calls for periodic reviews, so check the current contract file. **Unconfirmed** that 65 is still the lot on 18 Oct 2026.

**BANKNIFTY**

| Lot | Applies to | Source |
|---|---|---|
| 20 | In force in 2019 | Zerodha bulletin 26 Jun 2020 (**unconfirmed** on NSE) |
| 25 | July 2020 monthly (30 Jul 2020) onward; July 2020 weeklies stayed 20 | https://zerodha.com/marketintel/bulletin/259066/change-in-bank-nifty-fo-lot-size-2 (26 Jun 2020). NSE circular not found, **unconfirmed** |
| 15 | July 2023 monthly onward; weeklies from Aug 2023 (July weeklies stayed 25); long-dated after 30 Jun 2023. Circular effective 28 Apr 2023 | https://nsearchives.nseindia.com/content/circulars/FAOP56233.pdf (31 Mar 2023) |
| 15 | Unchanged in Apr 2024 | FAOP61415 (2 Apr 2024) |
| 30 | New contracts from 20 Nov 2024. Last monthly at 15: 29 Jan 2025; first at 30: 26 Feb 2025. Quarterly switched 24 Dec 2024 EOD | FAOP64625 (18 Oct 2024) |
| 35 | First monthly at 35: 31 Jul 2025; quarterly contracts from 25 Apr 2025 at 35; Apr to Jun 2025 monthlies stayed 30 | FAOP67372 (28 Mar 2025) |
| 30 | First monthly at 30: 27 Jan 2026; last at 35: 30 Dec 2025; quarterly switched 30 Dec 2025 EOD | FAOP70616 (3 Oct 2025) |

### B2. Expiry days

**NIFTY weekly**

- Weekly NIFTY options launched in Feb 2019 with Thursday expiry (**unconfirmed**, launch date from memory).
- Thursday through 28 Aug 2025. NSE/FAOP/68747 (25 Jun 2025, modifying circular 68685 of 23 Jun 2025) moved NIFTY weekly from Thursday to Tuesday. Weeklies expiring on or before 31 Aug 2025 kept Thursday (3, 10, 17, 24 Jul; 7, 14, 21 Aug 2025). First Tuesday weekly: 2 Sep 2025. NIFTY monthly moved to last Tuesday (first: 30 Sep 2025 quarterly; 28 Oct 2025 new monthly). Long-dated options realigned 31 Jul 2025 EOD. Source: https://nsearchives.nseindia.com/content/circulars/FAOP68747.pdf
- Holiday rule: expiry moves to the previous trading day (e.g. 24 Dec 2025 in the old schedule because 25 Dec was a holiday; NSE annexure above).
- An earlier NSE plan (Mar 2025) to move to Monday from 4 Apr 2025 was deferred after a SEBI consultation paper (news: https://www.theweek.in/wire-updates/business/2025/03/28/dcm1-biz-nse.html , **unconfirmed** on NSE). It never took effect.
- SEBI restricting all exchanges to Tuesday or Thursday expiries (May 2025 circular) is **unconfirmed** here (not retrieved).

**BANKNIFTY**

- Weekly expiry Thursday until 1 Sep 2023; Wednesday from 4 Sep 2023 (first Wednesday expiry 6 Sep 2023) per NSE circular 119/2023 of 12 Jul 2023 (via broker summaries: https://zerodha.com/marketintel/bulletin/358889/revision-in-expiry-day-for-banknifty-weekly-options-contracts ; NSE PDF not retrieved, **unconfirmed**).
- Monthly/quarterly moved to last Wednesday from trade date 1 Mar 2024 (first: 27 Mar 2024) (broker summaries, **unconfirmed** on NSE).
- Last BANKNIFTY weekly expiry: 13 Nov 2024 (NSE circular of 10 Oct 2024, via broker summaries e.g. https://www.angelone.in/news/market-updates/nse-ends-weekly-expiry-for-key-index-derivatives ; **unconfirmed** on NSE). Consistent with SEBI's one-weekly-benchmark rule effective 20 Nov 2024 (below).
- Monthly was back on last Thursday by mid-2025 (FAOP68747 lists BANKNIFTY monthly current expiry as last Thursday). The exact date of the Wednesday-to-Thursday revert (likely around Jan 2025) is **unconfirmed**.
- Monthly and quarterly moved to last Tuesday with the Sep 2025 change (first: 30 Sep 2025 quarterly). FAOP68747.

**One weekly expiry per exchange**

- SEBI/HO/MRD/TPD-1/P/CIR/2024/132 (1 Oct 2024), para 5.5: each exchange may offer weekly expiry on only one benchmark index, effective 20 Nov 2024. https://www.sebi.gov.in/sebi_data/attachdocs/oct-2024/1727786261636.pdf . On NSE this left only NIFTY weekly. On BSE, SENSEX weekly continued (SENSEX weekday history Friday, then Tuesday from Jan 2025, then Thursday from Sep 2025, is **unconfirmed**).

### B3. SEBI F&O measures (Oct 2024) and later changes

From SEBI circular SEBI/HO/MRD/TPD-1/P/CIR/2024/132, 1 Oct 2024, para 7: https://www.sebi.gov.in/sebi_data/attachdocs/oct-2024/1727786261636.pdf

| Measure | Effective |
|---|---|
| Minimum contract size Rs 15 lakh at introduction, lot set so value is Rs 15 to 20 lakh on review day | 20 Nov 2024 |
| One weekly benchmark index per exchange | 20 Nov 2024 |
| Additional 2% ELM on short options expiring that day (open at start of day and initiated during the day) | 20 Nov 2024 |
| Upfront collection of option premium from buyers | 1 Feb 2025 |
| Removal of calendar spread benefit on expiry day | 1 Feb 2025 per SEBI; NSE Clearing deferred to **10 Feb 2025** (NCL/CMPT/66047, 9 Jan 2025: https://nsearchives.nseindia.com/content/circulars/CMPT66047.pdf) |
| Intraday monitoring of position limits | 1 Apr 2025 |

Later changes:

- SEBI circular SEBI/HO/MRD/TPD-1/P/CIR/2025/41 (28 Mar 2025): intraday breaches of index derivative position limits not penalised "until further directions" (search snippet from sebi.gov.in, **unconfirmed** on full text).
- SEBI circular SEBI/HO/MRD/TPD-1/P/CIR/2025/79 (29 May 2025) introduced Future Equivalent (delta-based) OI. A follow-up SEBI circular of 1 Sep 2025 (SEBI/HO/MRD/TPD/CIR/P/2025/122) set index option intraday limits; per NSE's SOP the intraday net FutEq limit is Rs 5,000 cr per entity (EOD Rs 1,500 cr), monitored via at least four random snapshots, effective 1 Oct 2025; expiry-day breaches attract additional surveillance deposit or penalty. Source: NSE SOP https://nsearchives.nseindia.com/content/circulars/SURV70553.pdf (seen via search snippet, not read in full, so figures are **unconfirmed**). Retail backtests at small size are unaffected, but note the rule exists.
- Pre-open session in F&O: from 8 Dec 2025, 9:00 to 9:15 call auction for current-month stock and index futures (next month in last 5 days before expiry); options excluded; SL and IOC not accepted; unmatched market orders convert to limit at the discovered price. NSE circular NSE/FAOP/71092 (3 Nov 2025) and mock-session circular NSE/FAOP/71640 (5 Dec 2025). Details from broker/news summaries (https://www.business-standard.com/markets/capital-market-news/nse-to-commence-pre-opening-session-in-f-o-segment-from-december-08-125110400728_1.html), NSE PDFs not read, so **unconfirmed** in detail. For a NIFTY futures backtest, the 9:15 open after Dec 2025 is an auction price.

### B4. STT on index options and futures

All rates on sale side unless noted. Exercised options: STT on intrinsic value, payable by the buyer who exercises.

| Period | Options (sale, on premium) | Exercised options (on intrinsic value) | Futures (sale) | Source |
|---|---|---|---|---|
| to 31 Mar 2023 | 0.05% | 0.125% | 0.01% | NSE/FATAX/56235 (1 Apr 2023) |
| 1 Apr 2023 to 30 Sep 2024 | 0.0625% | 0.125% | 0.0125% | NSE/FATAX/56235: https://nsearchives.nseindia.com/content/circulars/FATAX56235.pdf ; Finance Act 2023 |
| 1 Oct 2024 to 31 Mar 2026 | 0.1% | 0.125% | 0.02% | Budget July 2024 memorandum (Clause 155), https://www.indiabudget.gov.in/budget2024-25/doc/memo.pdf |
| from 1 Apr 2026 | 0.15% | 0.15% | 0.05% | Budget 2026-27 memorandum (Clause 143), https://www.indiabudget.gov.in/doc/memo.pdf ; Finance Act 2026 assent 30 Mar 2026 per NSE/FATAX/73524 (31 Mar 2026): https://nsearchives.nseindia.com/content/circulars/FATAX73524.pdf |

Note the 2026 change applies to transactions entered into on or after 1 Apr 2026. The 2026 hike makes short-premium and high-turnover strategies materially more expensive; model the regime switch explicitly.

### B5. Exchange and statutory charges (NSE equity derivatives)

**NSE transaction charges (client pays broker's pass-through)**

| Period | Options (on premium) | Futures | Source |
|---|---|---|---|
| to 31 Dec 2020 | slab: Rs 50 per lakh (0.050%) top slab, lower for high-volume members; flat Rs 2,500/month up to Rs 3 cr | Rs 1.90 per lakh (0.0019%) top slab | NSE/FA/46730 (18 Dec 2020), "existing" column: https://nsearchives.nseindia.com/content/circulars/FA46730.pdf |
| 1 Jan 2021 to 31 Mar 2023 | Rs 53 per lakh (0.053%) top slab | Rs 2.00 per lakh (0.0020%) | NSE/FA/46730 |
| 1 Apr 2023 to 30 Sep 2024 | Rs 50 per lakh (0.050%) top slab, plus IPFT Rs 50/cr (0.0005%) | Rs 1.90 per lakh (0.0019%), plus IPFT Rs 10/cr (0.0001%) | NSE/FA/56129 (24 Mar 2023): https://nsearchives.nseindia.com/content/circulars/FA56129.pdf |
| 1 Oct 2024 to 28 Feb 2026 | Rs 3,503/cr (0.03503%) uniform, plus IPFT Rs 50/cr | Rs 173/cr (0.00173%), plus IPFT Rs 10/cr | Uniform "true to label" rates per NSE/FA/64323 (27 Sep 2024, PDF not retrievable); the figures are the "existing" column in NSE/FA/73061 |
| from 1 Mar 2026 | Rs 3,552.99/cr transaction + Rs 0.01/cr IPFT = Rs 3,553/cr (0.03553%) total | Rs 182.99/cr + Rs 0.01/cr = Rs 183/cr (0.00183%) | NSE/FA/73061 (27 Feb 2026): https://nsearchives.nseindia.com/content/circulars/FA73061.pdf |

Notes: before Oct 2024 the slabs applied to the broker's total monthly turnover, so what a retail client was billed depended on the broker. Using the top-slab rate is a conservative approximation (**assumption**). Total member outflow did not change on 1 Mar 2026; IPFT was folded into transaction charges.

**Other levies (current, per Zerodha and Upstox charge pages, accessed 18 Oct 2026)**

- SEBI turnover fee: Rs 10 per crore (0.0001%) on both sides. https://zerodha.com/charges . Date of the change from Rs 15 to Rs 10 per crore is **unconfirmed** (believed 2020).
- Stamp duty (buy side only): options 0.003% (Rs 300/cr), futures 0.002% (Rs 200/cr). Same pages. Uniform national rates from 1 Jul 2020 under the amended Indian Stamp Act (**unconfirmed** date; before that it varied by state).
- GST: 18% on brokerage, exchange transaction charges and SEBI fee (Zerodha page). GST at 18% since 1 Jul 2017 (**unconfirmed** here, general knowledge).
- IPFT: Rs 0.01/cr since 1 Mar 2026 (NSE/FA/73061). Upstox's page still shows old IPFT rates in one section, so it has an internal inconsistency.
- BSE options transaction charge: 0.0325% of premium (Zerodha/Upstox pages, accessed 18 Oct 2026).

### B6. Brokerage (F&O)

| Broker | Futures | Options | API fee | Source (accessed 18 Oct 2026) |
|---|---|---|---|---|
| Upstox (Basic) | Rs 20 or 0.05%, lower | Rs 20 flat | API free; API orders Rs 10/order "valid till 31 Dec 2025" (current rate **unconfirmed**) | https://upstox.com/brokerage-charges/ |
| Upstox Plus | Rs 30 or 0.05% | Rs 30 | same | https://upstox.com/help-center/what-are-the-benefits-of-upstox-plus-264070/ |
| Groww | Rs 20 per executed order | Rs 20 | Trade API Rs 499/month + tax | https://groww.in/help/stocks,-f&o,-ipo-&-mtf/searchable/how-much-is-the-brokerage (via search) and https://groww.in/trade-api |
| Zerodha | Rs 20 or 0.03%, lower | Rs 20 flat | Kite Connect Rs 500/month (Personal free, no data) | https://zerodha.com/charges ; Kite support page above |
| Dhan | Rs 20 per executed order | Rs 20 | Trading APIs free; Data API Rs 499/month + tax | https://dhan.co/pricing/ ; Dhan support pages |
| ICICI Direct | plan-dependent: iValue/Neo Rs 20 per order (Neo page also shows Rs 0 futures); default MoneySaver 0.029% futures and Rs 49 per lot options | as left | Breeze free | https://www.icicidirect.com/brokerage , https://www.icicidirect.com/brokerage/neo-plan (via search). Conflicting pages, **unconfirmed** which plan applies |

Brokerage is per executed order; a sliced order above freeze quantity pays per child order.

### B7. SEBI retail algo framework

- SEBI circular SEBI/HO/MIRSD/MIRSD-PoD/P/CIR/2025/0000013, 4 Feb 2025: brokers are principals, algo providers agents; all API algo orders tagged with an exchange-provided unique ID; self-built algos by retail must be registered via broker only if they exceed the specified orders-per-second threshold; no open APIs, access only via unique vendor/client API key and static IP whitelisted by broker; OAuth only; 2FA; empanelled providers only; black-box algo providers must register as Research Analysts. Originally effective 1 Aug 2025. https://www.sebi.gov.in/sebi_data/attachdocs/feb-2025/1738665456458.pdf
- Extended to 1 Oct 2025 by SEBI circular of 29 Jul 2025 (cited in the Sep 2025 circular).
- SEBI/HO/MIRSD/MIRSD-PoD/P/CIR/2025/132, 30 Sep 2025: ready brokers go live 1 Oct 2025; glide path milestones 31 Oct 2025, 30 Nov 2025, mock session by 3 Jan 2026; non-compliant brokers barred from onboarding new API algo clients from 5 Jan 2026; **framework applies to all brokers from 1 Apr 2026**. https://www.sebi.gov.in/sebi_data/attachdocs/sep-2025/1759232056254.pdf
- NSE implementation standards, NSE/INVG/67858, 5 May 2025: https://nsearchives.nseindia.com/content/circulars/INVG67858.pdf
  - Static IP mandatory for API access; one primary plus optional secondary; change at most once per calendar week; one IP maps to one client (family sharing allowed with request).
  - All API sessions must be logged out daily before the next trading day.
  - Threshold: 10 orders per second per exchange/segment, measured by broker server calendar-clock second. Below it, no individual registration, but orders still carry a generic exchange algo ID. Above it, the algo must be registered with each exchange, gets its own algo ID.
  - Broker must reject or not process orders exceeding the OPS limit.
  - Exchanges may restrict order types or contracts for client algos.
- NSE operational modalities of 22 Jul 2025 require strategies to run on broker servers for vendor algos (per NSE FAQ https://nsearchives.nseindia.com/web/sites/default/files/inline-files/FAQ_Retail%20Algo_03112025_NSE.pdf , seen via search, **unconfirmed** in detail).

**Upstox implementation**

- All API orders must come from a registered static IP from 1 Apr 2026; one primary and one secondary; change once per calendar week via My Apps or `GET/PUT /user/ip`; IP update invalidates existing tokens; covers Place/Modify/Cancel, Multi Order, GTT, Exit All; not holdings, positions, funds or historical candles. Algos above 10 OPS need exchange registration; tag orders with `X-Algo-Name` header. Source: https://upstox.com/developer/api-documentation/announcements/algo-trading-circular/ (accessed 18 Oct 2026).
- Staff post 27 Mar 2026: only one active API app per user from 1 Apr 2026; market and SL-M orders get market protection (MPP), plain market orders not allowed. Family IP sharing supported from 7 May 2026. https://community.upstox.com/t/important-new-sebi-exchange-mandates-for-api-trading-effective-1st-april-2026/14822
- Rate limits for order APIs (combined Place/Modify/Cancel/Multi/GTT): unregistered algos 10/s, 500/min, 2,000 per 30 min; registered algos 50/s. https://upstox.com/developer/api-documentation/rate-limiting/
- Error for non-whitelisted IP: UDAPI1154 (GTT doc).

**Groww implementation**

- Groww's public docs pages read here do not mention static IP, algo ID or SEBI compliance (https://groww.in/trade-api/docs/curl , changelog, accessed 18 Oct 2026). Groww's implementation is **unconfirmed**; check the Groww Cloud API Keys page and any notice in-app before going live.

### B8. Upstox order API capabilities

- Place order v3: `POST https://api-hft.upstox.com/v3/order/place`. Order types MARKET, LIMIT, SL, SL-M; product I, D, MTF; validity DAY or IOC. Market orders over the API are blocked by the exchange (UDAPI1158) unless market protection applies; `market_protection` -1 (auto), 1 to 25 (%), 0 rejected for market orders; applies to MARKET and SL-M only. `slice: true` auto-splits by freeze quantity. `tag` up to 40 chars. Orders accepted 5:30 AM to midnight IST. Source: https://upstox.com/developer/api-documentation/v3/place-order/ (accessed 18 Oct 2026).
- SL-M on index options: Upstox docs do not restrict it. Whether NSE restricts SL-M for index options through APIs is **unconfirmed**. Practical advice: use SL (stop-limit) with a limit buffer.
- Multi order: `POST https://api.upstox.com/v2/order/multi/place`, max 10 lines per request (child slices count toward the 10), BUY lines executed before SELL lines, `correlation_id` required (max 20 chars), not atomic at execution (partial_success possible). https://upstox.com/developer/api-documentation/place-multi-order/
- GTT: `POST https://api.upstox.com/v3/order/gtt/place`, SINGLE or MULTIPLE (ENTRY + TARGET + STOPLOSS), trailing stop (beta), executes as LIMIT, valid up to one year. F&O support not stated (**unconfirmed**). https://upstox.com/developer/api-documentation/place-gtt-order/
- Freeze quantity, NIFTY: 3,510 (54 lots of 65) from 5 Oct 2026; BANKNIFTY 1,440. NSE/FAOP/76693 (1 Oct 2026): https://nsearchives.nseindia.com/content/circulars/FAOP76693.pdf . Before that, 1,800 from 1 Sep 2026 per news (https://www.angelone.in/news/market-updates/nse-updates-quantity-freeze-limits-for-indices-effective-september-1-2026 , **unconfirmed** on NSE). Historical freeze limits for 2019 to 2025 not researched; model slicing with the per-date freeze from contract files if needed.
- WebSocket market data v3: `wss` feed at `/feed/market-data-feed` via an authorize redirect, Protobuf-encoded. Modes ltpc, option_greeks, full (5-level depth + greeks), full_d30 (30-level, Plus only). Limits: 2 connections per user (5 on Plus); ltpc 5,000 instruments individually / 2,000 combined; option_greeks 3,000 / 2,000; full 2,000 / 1,500; full_d30 50 / 1,500. https://upstox.com/developer/api-documentation/v3/get-market-data-feed/ (accessed 18 Oct 2026).
- Sandbox: yes, for Place Order (incl. v3), Place Multi Order, Modify and Cancel. Separate sandbox app, token valid 30 days, one sandbox app per user. Market data is not listed as sandbox-enabled; not a full paper-trading simulator. https://upstox.com/developer/api-documentation/sandbox/ (accessed 18 Oct 2026).

### B9. NIFTY weekly option bid-ask spreads

- No credible public study of NIFTY weekly option spreads by moneyness and time of day was found in a short search. Results were broker blogs only. **Unconfirmed / not found.**
- Closest academic analogues (not India): index option spreads are widest near the open and narrow through the day (ap Gwilym, Buckle and Thomas 1997, FTSE 100 options); CBOE equity options show an L-shaped intraday spread pattern with OTM vs ATM differences (Chen 2018 thesis, https://harvest.usask.ca/handle/10388/8317). Use only as a shape prior.
- Recommended calibration route: record your own quotes. Upstox v3 `full` mode gives 5-level depth for up to 2,000 instruments (enough for the full NIFTY weekly chain near the money). Log best bid/ask every second for 4 to 6 weeks, bucket by moneyness (ATM, 1 to 2% OTM, far OTM, ITM), minutes to close, and days to expiry, and fit a spread model. Breeze 1-second data is OHLC, not quotes, so it cannot measure spread directly.
- Working assumption until measured (**assumption, not sourced**): near-ATM current-week NIFTY options are typically 1 to 2 ticks wide in mid-session (tick 0.05), wider in the first 15 minutes and in the last minutes of expiry day, and far-OTM options are 1 tick wide in rupees but very wide in percentage terms. Use a cost of at least half the spread plus 1 tick per side in the backtest, and stress-test at 2x.

---

## Recommendation

**(a) Long EOD options history (2019 onward, free).** Use NSE archives directly: old-format F&O bhavcopy for 1 Jan 2019 to 5 Jul 2024 and UDiFF bhavcopy from 1 Jan 2024 onward (overlap Jan to Jul 2024 lets you validate the mapping). It needs no account, covers every expired strike, and includes settle price, OI and, in UDiFF, the lot size per row. Pair it with India VIX from NSE and NIFTY index closes from niftyindices.com or Upstox v3 daily candles. Gotcha: bhavcopy close for illiquid strikes can be stale; filter by traded contracts or volume.

**(b) Intraday expired NIFTY options.** No free or cheap source found covers 1-minute expired options back to 2019. Practical layering:

1. **Groww first** (account exists, Rs 499/month). Docs claim FNO candles from 2020 with expiry and contract lookups. Test one 2020 or 2021 weekly NIFTY contract at 1-minute before paying for months. If it works, this is the widest cheap coverage (2020 onward, contract-level).
2. **Dhan as the second account** (Rs 499/month Data API). Rolling ATM-relative 1-minute data with OI, IV and spot for about 5 years (roughly Oct 2021 onward), up to ATM±10 near expiry. Best fit for ATM-relative strategies like straddles and strangles; awkward for fixed-strike positions.
3. **ICICI Breeze if you want 1-second bars** (free, needs an ICICI Direct account). Official depth claims conflict (3 vs 10 years); expired coverage is not documented. Treat as a test.
4. **Upstox Plus** only for the last ~6 months of expiries (activation said to be free initially, but F&O brokerage shows Rs 30 per order on Plus). Useful for recent out-of-sample checks and as a cross-check against Groww and Dhan.
5. For 2019 intraday, the only route found is paid vendor data; no vendor was researched here, so prices and quality are unknown.

Cross-validate any intraday source against the NSE bhavcopy daily close and OI for the same contracts before trusting it.
