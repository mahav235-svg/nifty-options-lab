# NIFTY options and futures: literature review of candidate edges

Prepared 18 Oct 2026. Scope: NIFTY weekly index options (Tuesday expiry), NIFTY monthly options and NIFTY futures, for a small retail account (about INR 1 to 2 lakh for defined-risk selling, under INR 1 lakh for buying).

These are research notes, not a recommendation to trade. Every strategy below can lose money, including the full defined risk on every position. The base rate in Indian index options is poor: SEBI's own studies find that roughly 9 in 10 individual F&O traders lose money in a typical year. Nothing here should be read as a claim that a strategy will be profitable. The purpose is to decide what is worth testing and how to test it without fooling ourselves.

How to read the confidence tags:

- **[verified]** means I confirmed the citation details (authors, venue, a headline number) during this review from the paper page, a reputable abstract index, or consistent press coverage.
- **[from memory]** means a well-known paper whose details I am confident about but did not re-check while writing these notes. Check the exact numbers before quoting them anywhere.
- **[unverified]** means a lead found in search results that I could not confirm (preprints, blog summaries, titles without authors). Treat as a pointer, not evidence.

---

## 0. Market structure facts that change how the literature applies

These matter more than any single paper, because most of the published evidence is on S&P 500 options with a very different cost and contract structure.

**Contract and expiry rules (verify against current NSE circulars before trading).**

- SEBI circular of 1 Oct 2024 (SEBI/HO/MRD/TPD-1/P/CIR/2024/132), effective from 20 Nov 2024: each exchange may offer weekly expiries on one benchmark index only (NSE kept NIFTY, BSE kept SENSEX); minimum index derivative contract value raised to about INR 15 lakh; an extra 2% Extreme Loss Margin on short options on expiry day; upfront collection of option premium from buyers; removal of the calendar-spread margin benefit on expiry day (reported effective 1 Feb 2025). [verified, press and broker summaries]
- NIFTY weekly expiry moved from Thursday to Tuesday from 1 Sept 2025, following SEBI's 2025 decision to restrict equity derivative expiries to Tuesday or Thursday. If Tuesday is a holiday, expiry moves to the previous trading day. [verified, secondary sources; I did not open the NSE circular itself]
- NIFTY lot size went from 25 to 75 in Nov 2024 and was reported cut to 65 for contracts expiring after Dec 2025. At an index level of 25,000, one lot of 65 is about INR 16 lakh notional. [lot size 65: secondary sources only, confirm on NSE contract specs]
- SEBI's intraday position monitoring framework (circular of 1 Sept 2025, net cap INR 5,000 crore futures-equivalent per entity, checked by random intraday snapshots, expiry-day provisions from 6 Dec 2025) targets large players, not a 1-lot retail account, but it changes how big liquidity providers behave on expiry days. [verified]
- Union Budget 2026-27 raised STT from 1 Apr 2026: futures 0.02% to 0.05% (sell side), options 0.10% to 0.15% of premium (sell side), and exercised options reported at 0.15% of intrinsic value. [verified, multiple outlets] On a 1-lot NIFTY futures round trip at INR 16 lakh notional, STT alone is about INR 800. That kills most high-frequency futures ideas at this account size.
- SEBI's chairman said in Sept 2025 that the regulator "will consider weekly expiry", with no timeline. I found no 2026 consultation paper ending weekly expiries, but this is a live regulatory risk. Any strategy that only works on 1 to 2 day options could be regulated away. Strategies that also work on monthly options are more durable. [verified that the statement exists; status as of Oct 2026 not confirmed]
- SEBI interim order against Jane Street entities (3 Jul 2025) alleged that a large algorithmic firm moved BANKNIFTY constituents on expiry days to profit on index options positions, with reported index options profits of about INR 43,289 crore (Jan 2023 to Mar 2025) and INR 4,843 crore impounded. The firm disputes the findings. [verified, press] The practical lesson for us: expiry-day price paths in Indian index options can be driven by participants far larger and better informed than a retail short-gamma position.

**Settlement mechanics.** NIFTY options are cash settled on the closing value of the index on expiry day. NSE closing prices for constituents are computed as a volume-weighted average over the last 30 minutes, so the index "close" is a smoothed number. This matters for any test that uses closing prices, and it means the last half hour of expiry day carries settlement risk. [from memory, verify with NSE methodology note]

**Who loses money: SEBI's studies.**

- Jan 2023 study (FY22): about 89% of individual equity F&O traders lost money; average loss about INR 1.1 lakh. Loss-makers reportedly spent an extra 28% of their trading losses on transaction costs. [89% verified; cost share from memory]
- Sept 2024 study (FY22 to FY24): 93% of over 1 crore individual F&O traders lost money, aggregate losses over INR 1.8 lakh crore, average loss about INR 2 lakh per trader including costs. Only about 7.2% were profitable and about 1% made more than INR 1 lakh after costs. Over 75% of loss-makers kept trading. Proprietary traders and FPIs made gross trading profits of about INR 33,000 crore and INR 28,000 crore in FY24, with 96% and 97% of those profits from algorithmic trading. [verified, press]
- Jul 2025 study (FY25): about 91% of individual traders lost money; net losses INR 1,05,603 crore versus INR 74,812 crore in FY24; average loss about INR 1.1 lakh; unique individual traders down about 20% year on year after the Nov 2024 measures. Losses concentrated in weekly index options. [verified, press]
- FY26 data (reported Aug 2026, Rajya Sabha reply of 11 Aug 2026): 82.1% of individuals lost before costs and 87.7% after costs; net losses about INR 91,685 crore; individual traders down to about 78.6 lakh; transaction costs about INR 24,859 crore, equal to 35% of gross losses for losing traders and 21% of gross profits for winning traders; about 4.4 lakh traders were profitable before costs and loss-making after. Traders who lost two years in a row and continued lost again about 90% of the time. [verified, press]

What this implies for edge hunting: the counterparties earning money in Indian index options are mostly algorithmic proprietary desks and FPIs. A retail account that wants to be on the "right" side has to sell what retail over-buys (short-dated, out-of-the-money options) while paying higher costs than those desks and without their flow information. The FY26 cost numbers say costs alone flip a meaningful share of pre-cost winners into losers. Every test below must use a realistic cost model, not just brokerage.

---

## 1. Variance risk premium and short-volatility returns

### Claimed edge

Index options are priced above what they pay out on average. Implied variance exceeds subsequently realized variance, so sellers of index volatility earn a premium on average, at the cost of large losses in crashes.

### Core evidence

- **Coval and Shumway (2001), "Expected Option Returns", Journal of Finance 56(3).** Zero-beta, at-the-money S&P 500 straddles lost roughly 3% per week on average. OTM puts had the most negative returns. Their reading: volatility (or a crash factor) is priced. [from memory]
- **Bakshi and Kapadia (2003), "Delta-Hedged Gains and the Negative Market Volatility Risk Premium", Review of Financial Studies 16(2).** Delta-hedged long index option positions lose money on average, and losses are largest for ATM options and in high-volatility periods. [from memory]
- **Carr and Wu (2009), "Variance Risk Premiums", Review of Financial Studies 22(3).** Using synthetic variance swaps, S&P 500 realized variance averages well below the swap rate. Long variance has strongly negative average returns, not explained by standard factors. [from memory]
- **Bollerslev, Tauchen and Zhou (2009), Review of Financial Studies.** The variance risk premium (implied minus realized variance) predicts equity index returns at horizons of a few months. [verified via a JFQA paper citing it]
- **Term structure of the premium.** Andries, Eisenbach, Schmalz and Wang, "The Term Structure of the Price of Volatility Risk" (New York Fed Staff Report 736): the price of variance risk is largest at the shortest maturities, and straddle Sharpe ratios are significantly negative for the first two maturity buckets and shrink in absolute value with maturity. [verified, abstract] Dew-Becker, Giglio, Le and Rodriguez (2017), "The Price of Variance Risk", Journal of Financial Economics 123(2): investors pay to hedge realized variance shocks but barely pay for news about future variance, so the premium sits at the short end. [from memory] This is the theoretical case for why weekly NIFTY options should carry the richest premium per unit time.
- **Israelov and Nielsen (2015), "Covered Calls Uncovered", Financial Analysts Journal 71(6) (AQR).** Covered-call returns decompose into equity exposure, a short-volatility component and an equity "reversal" (timing) component. The short-vol piece earned a Sharpe ratio near 1.0 but contributed about 10% of risk; the timing piece contributed about 25% of risk with little return. Hedging the timing piece improves the Sharpe ratio. [verified] The lesson carries over: if you want the volatility premium, isolate it rather than take unpaid directional bets alongside it.
- **Other Israelov work (AQR) [from memory]:** "Still Not Cheap: Portfolio Protection in Calm Markets" (Israelov and Nielsen, Journal of Portfolio Management 2015) argues low implied vol does not make puts cheap relative to subsequent realized vol; "Pathetic Protection: The Elusive Benefits of Protective Puts" (Israelov, Journal of Alternative Investments 2019) argues protective puts are an expensive and path-dependent hedge; Israelov and Klein (2016) on collars. AQR's white paper "Understanding the Volatility Risk Premium" (2018) is a readable practitioner summary. [AQR paper existence verified]
- **CBOE benchmark studies.** Black and Szado (2016) studied CBOE options-selling indexes from mid-1986 to 2015: the indexes had returns similar to the S&P 500 with lower volatility and lower drawdowns; PUT returned about 10.13% annualized. [verified, CBOE release] Bondarenko's CBOE-sponsored study (2019) covers June 1986 to Dec 2018: average VIX of 19.3% versus average realized volatility of 15.1% over 1990 to 2018. [verified] Bondarenko (2016) compared weekly (WPUT) and monthly (PUT) put-writing. [verified that it exists] CBOE's CNDR (iron condor, short legs near 0.15 to 0.20 delta with long wings) and BFLY (iron butterfly, ATM short, 5% OTM wings) indexes give defined-risk benchmarks; CBOE's own material is marketing, not independent research. Performance numbers in these index studies are gross of costs. [verified]
- **Ilmanen (2012), "Do Financial Markets Reward Buying or Selling Insurance and Lottery Tickets?", Financial Analysts Journal.** Across asset classes, selling insurance and lottery-like payoffs has historically earned a premium, with crash risk. [from memory]
- **Dörries, Korn and Power (2021), "How Should the Long-term Investor Harvest Variance Risk Premiums?"** (Quantpedia summary). Compares straddles, strangles, butterflies, condors, delta-hedged options and variance swaps on S&P 500 1996 to 2021. Under equal risk exposure the strategies look similar; all carry positive market correlation; crash losses are the main risk. [verified, summary only]

### India-specific evidence

- **Garg and Vipul (2015), "Volatility Risk Premium in Indian Options Prices", Journal of Futures Markets 35(9), 795-812.** The VRP is priced in Indian options and follows an autoregressive process (so it is persistent and partly forecastable). Option strategies exploiting it show significant daily returns before costs, but these shrink substantially after normal transaction costs; benefits accrue "only to those option writers who have sufficiently low transaction costs". [verified]
- **Sankar, Ramachandran and Lukose (2020), "Dynamics of Variance Risk Premium: Evidence from India", International Review of Economics and Finance 70, 321-334.** Rejects the hypothesis that variance risk is not priced in a retail-heavy market. Only past continuous variance (not jumps) predicts short-term synthetic variance swap returns. [verified, abstract]
- **Bhat, Pandey and Rao (2024), "The Asymmetry in Day and Night Option Returns: Evidence from an Emerging Market", Journal of Futures Markets 44(8).** On NIFTY options, short option returns are strongly positive overnight and not intraday; the VRP is mainly compensation for overnight risk; post-noon returns are significantly negative for short calls and positive for short puts; the gap shrinks with moneyness and maturity. A sell-at-close, cover-at-open strategy is profitable before costs but not after explicit and implicit costs. [verified, via a summary of the paper]
- **Chakrabarti and Kumar (2017), Multinational Finance Journal,** on whether volatility demand in NIFTY option order flow drives the VRP. [unverified detail]
- **Jain, Varma and Agarwalla (2019), "Indian Equity Options: Smile, Risk Premiums, and Efficiency", Journal of Futures Markets 39(2).** Single-stock options; the IV risk premium looks larger than in other markets. Varma's blog argues single-stock IV in India exceeds realized vol by more than a rational premium would explain. Not index options, but consistent with heavy retail option buying. [verified]
- **NSE Working Paper 9/2013 on India VIX and risk:** finds a significant negative relation between index returns and volatility, the leverage effect that makes short vol a crash-exposed bet. [verified title; could not open the PDF]
- **Pillai, "Trading the Volatility Risk Premium on Nifty 50: Strategy Backtest with Realistic Frictions", SSRN 6876580.** A search summary says it tests four monthly short-vol strategies over 119 expiries (Jan 2015 to Apr 2025), finds all negative after costs, and attributes losses mainly to tail risk. Preprint, not peer reviewed, and I could not confirm the details. [unverified] If accurate, it is the most direct warning in this review.

### Economic rationale (who pays)

Institutions and FPIs buy index puts for portfolio protection and to meet risk limits; retail buys short-dated OTM calls and puts for lottery-like payoffs (see Beckmeyer et al. below, and SEBI's loss data). Dealers and sellers demand compensation for jump and crash risk they cannot hedge continuously. In India the persistent net-buying of weekly OTM options by retail is a plausible extra source of overpricing at the short end.

### When it fails

- Crashes and volatility spikes: Feb 2018 "Volmageddon" in the US (one inverse-VIX note fell over 90%); March 2020 (India VIX closed above 80); 4 Jun 2024 election results day, when NIFTY fell about 5.9% in one session. [2018 and 2024 figures from memory or press; verify exact numbers]
- Cheng (2019), "The VIX Premium", Review of Financial Studies: the VIX futures premium falls, and can turn negative, when risk rises. The premium does not reliably widen exactly when sellers need it. [from memory]
- Crowding: practitioner and academic work around 2018 warned that crowded short-vol positions create shared nonlinear risk. [verified that such papers exist]

### Conditioning signals

- **IV minus forecast realized vol.** Garg and Vipul show the Indian VRP is autoregressive, so a positive spread today tends to persist. Use a HAR forecast of realized vol (section 8) rather than trailing 20-day vol.
- **VIX term structure.** Johnson (2017), "Risk Premia and the VIX Term Structure", JFQA 52(6): the slope factor predicts excess returns on variance swaps, VIX futures and S&P 500 straddles; low or inverted slope predicts higher returns to long-variance positions (worse for sellers). Sample 1996 to 2013. [verified] Lehnert (2025), "Does It Take Two to ConTango?", Journal of Derivatives: an S&P 500 short straddle scaled by VIX term-structure shape earned large variance-risk-adjusted alpha; costs not confirmed. [verified abstract] India has no liquid VIX futures, so the proxy is weekly ATM IV versus next-month ATM IV from the option chain.
- **Trend filters.** Evidence is mostly practitioner backtests (blogs, Quantpedia). The intuition is sound: volatility clusters in drawdowns (leverage effect), so standing aside when the index is below a long moving average removes some crash exposure. Treat as weakly evidenced and test it rather than assume it.

### Strength of evidence

Strong in the US across decades and many papers. Moderate in India: the premium exists (three peer-reviewed papers), but two of them explicitly say costs eat most of it for typical traders, and one unverified preprint finds negative net returns. Post-publication decay: the VRP has not disappeared in the US, consistent with a risk premium rather than an anomaly, but realized returns are lumpy.

### Applicability to NIFTY weeklies

High relevance, low margin for error. The premium should be richest at the short end, but a 1-lot minimum with INR 16 lakh notional means one adverse weekly move of 2 to 3% on an undefined-risk position can exceed the whole account. Defined-risk structures (iron condor, iron fly, put spreads) are necessary at this size. They give up some premium to the wings, and the wings are also priced with a premium, so a condor captures less VRP than a naked strangle.

### Data needed

EOD option chain (NSE F&O bhavcopy: close, settle price, OI per strike) is enough for hold-to-expiry tests. India VIX history from NSE. Bhavcopy has no bid-ask, so a spread haircut must be assumed and stress-tested.

---

## 2. Weekly and 0DTE option behaviour, expiry-day pinning and gamma

### Claimed edges

(a) Very short-dated options carry a VRP that sellers can harvest. (b) Retail buyers of 0DTE options lose systematically. (c) Prices pin to high open-interest strikes near expiry. (d) Dealer gamma drives intraday moves.

### Evidence

- **Beckmeyer, Branger and Gayda (2023), "Retail Traders Love 0DTE Options... But Should They?", SSRN 4404704.** CBOE trade data Jan 2021 to Feb 2023. Retail lost about USD 358,000 per day (secondary sources also say about USD 350,000 per day, about USD 125 million in total) in SPX 0DTE options after daily expirations launched. 0DTE made up over 75% of retail SPX option volume in 2022 and 2023. [verified via summaries; SSRN page blocked] My recollection is that the authors attribute much of the loss to bid-ask spreads rather than gross mispricing; check this before relying on it.
- **Vilkov, "0DTE Trading Rules", SSRN 4641356.** S&P 500 0DTE options, Sept 2016 to Jan 2024, static daily rules held to expiry. A VRP exists even at same-day horizons, but return distributions are very wide; most strategy averages are not statistically significant; much of the P&L is explained by realized intraday skewness. Some trades (selling OTM calls and puts) look profitable at the median. [verified, summary]
- **Bandi, Fusari and Renò (2023), "0DTE Option Pricing", SSRN 4503344.** New pricing model for the 0DTE surface (jumps for OTM, continuous vol for ATM). Return and VRP results are presented as suggestive, not conclusive. [verified]
- **Dim, Eraker and Vilkov, "0DTEs: Trading, Gamma Risk and Volatility Propagation".** High 0DTE open-interest gamma is associated with lower intraday realized volatility and does not propagate volatility. This argues against the popular claim that 0DTE dealer hedging amplifies moves. [verified via seminar abstract; co-authors not confirmed in search]
- **Andersen, Fusari and Todorov (2017), "Short-Term Market Risks Implied by Weekly Options", Journal of Finance.** Weekly options isolate jump tail risk; the negative jump tail factor varies over time, is not spanned by volatility, and predicts equity returns. [verified]
- **Ni, Pearson and Poteshman (2005), "Stock Price Clustering on Option Expiration Dates", Journal of Financial Economics 78.** Optionable US stocks close near strikes on expiry more often than otherwise, consistent with delta-hedge rebalancing by net-long market makers and some manipulation. [from memory]
- **Golez and Jackwerth (2012), "Pinning in the S&P 500 Futures", Journal of Financial Economics 106(3).** Evidence of pinning in index futures around option expiry. [from memory]
- **Ni, Pearson, Poteshman and White (2021), "Does Option Trading Have a Pervasive Impact on Underlying Stock Prices?", Review of Financial Studies.** Market makers' net gamma position affects underlying volatility. [from memory]
- **Baltussen, Da, Lammers and Martens (2021), "Hedging Demand and Market Intraday Momentum", Journal of Financial Economics 142(1), 377-403.** See section 3; links end-of-day momentum to short-gamma hedging. [verified]
- **India expiry effects.** Vipul (2005), "Futures and Options Expiration-Day Effects: The Indian Evidence", Journal of Futures Markets 25(11): prices slightly depressed the day before expiry and stronger the day after, with abnormal volume, linked to arbitrage and short-sale restrictions. Later studies are mixed: a 2009 study of NIFTY futures 2001 to 2009 found higher expiry volume but no price distortion over the full sample; a 2016 study found significant but not disruptive effects; a 2020 study on Bank Nifty found no volatility effect; another study found stock volatility rises in the last half hour of expiry day, tied to VWAP settlement. [verified, abstracts]
- **Practitioner data.** Option Alpha's platform data on SPY 0DTE: iron butterflies won 72% of 4,959 trades and iron condors 63% of 3,170, but the article does not show loss sizes and it is a self-selected sample of platform users. [verified] High win rates say nothing about expectancy. SpotGamma and similar services publish dealer-gamma notes; the academic results above (Dim, Eraker and Vilkov) are a useful check on those claims.

### Rationale

Retail lottery demand for same-day OTM options is the most plausible source of 0DTE overpricing. Market makers charge wide spreads relative to premium. Pinning, where it exists, comes from hedging flows of net-long-gamma dealers and from expiry-day positioning by large players.

### Strength of evidence

Retail losses on 0DTE: consistent (US paper plus SEBI's India data). Harvestable 0DTE VRP for an outsider after costs: weak. Pinning: documented in US single stocks and index futures but small and unreliable for trading. Dealer-gamma-drives-the-market narratives: mixed to negative in recent academic work.

### Applicability to NIFTY

Directly relevant: the Tuesday NIFTY weekly is effectively a 0DTE instrument on Tuesday and a 1DTE on Monday. Expiry-day costs are higher for sellers (2% extra ELM ties up margin; no calendar-spread margin offset on expiry day). The Jane Street order shows expiry-day paths can be driven by large players. Expect ATM gamma on Tuesday to be extreme: a 1% NIFTY move late in the day can turn an ATM short into a loss of many times the credit.

### Data needed

Hold-to-settlement tests need only EOD (Monday close prices and Tuesday settlement). Anything with intraday entry or exit (09:20 entries, 10:00 exits, stops) needs minute-level option prices, ideally with bid-ask.

### Main risks

Gap risk overnight into Tuesday, late-day trend moves, settlement on the VWAP-based close, regulatory change to weekly expiries.

---

## 3. Intraday momentum

### Claimed edge

The return over most of the trading day predicts the direction of the last 30 minutes.

### Evidence

- **Gao, Han, Li and Zhou (2018), "Market Intraday Momentum", Journal of Financial Economics 129(2).** SPY 1993 to 2013: first half-hour return predicts the last half-hour return with slope 0.069 and R-squared about 1.6%; adding the second-to-last half hour raises R-squared to about 2.6%. Stronger on high-volatility, high-volume days and in recessions. Some commentators note much of the predictability comes from the financial-crisis period. [verified]
- **Baltussen, Da, Lammers and Martens (2021), JFE.** Over 60 futures (equities, bonds, commodities, FX), 1974 to 2020: the rest-of-day return predicts the last 30 minutes. They link it to gamma hedging by option market makers and leveraged ETFs: when dealers are short gamma they must buy into rallies and sell into declines near the close. [verified]
- **Li, Sakkas and Urquhart (2022), Journal of Financial Markets.** Intraday time-series momentum is economically sizable and significant in and out of sample in most of 16 developed markets. [verified]
- **Against:** Rosa (2022), Journal of Futures Markets 42(12): predictability (overnight return predicting the last half hour) disappears out of sample. An Asia-Pacific study finds momentum mainly in China and Japan, weak in Korea, absent in Hong Kong and Singapore, and weaker during Covid. Pandemic-period studies on the S&P 500 and CSI 300 find the effect weakened. [verified as summaries]
- **India.** A paper titled "Hedging Demand and Intraday Momentum within the Indian Stock Market" (ResearchGate) reports strong last-half-hour momentum in India using the Baltussen approach. I could not confirm authors or venue. [unverified] Murphy and Thirumalai (2017) document interday cross-sectional momentum in Indian stocks linked to institutional order splitting. [unverified detail] An older NIFTY study finds an opening jump effect and a persistent end-of-session effect. [unverified detail]

### Rationale

Short-gamma hedgers and late-day institutional order execution trade in the direction of the day's move near the close. In India, the 15:00 to 15:30 window also contains the VWAP window that determines official closing prices and futures settlement prices, which concentrates institutional flows.

### Strength of evidence

Moderate in-sample and in futures across markets; mixed out of sample; weak and unverified in India. R-squared is a few percent, so the signal is right only slightly more often than wrong.

### Applicability

Possible in NIFTY futures, but costs are a serious hurdle after the Apr 2026 STT increase (about 0.05% on the sell leg) plus slippage. One lot of futures needs roughly INR 2 lakh or more of margin, which is above the buying budget; deep ITM options can substitute at the cost of wider spreads. A more realistic use for a small account is defensive: avoid holding short-gamma option positions into the close on strong trend days, especially on Tuesday expiry.

### Data needed

Minute bars of NIFTY futures (and spot). Use last traded prices, not the VWAP-based official close. Not available in bhavcopy.

---

## 4. Overnight versus intraday returns

### Claimed edge

Equity returns accrue mostly overnight; intraday returns are near zero or negative on average.

### Evidence

- **Lou, Polk and Skouras (2019), "A Tug of War: Overnight Versus Intraday Expected Returns", Journal of Financial Economics 134(1), 192-213.** US stocks: average excess overnight return 0.95% per month (t = 2.95) versus 0.04% intraday; momentum profits accrue overnight, other factors intraday; linked to investor clienteles. [verified]
- **Cliff, Cooper and Gulen (2008), "Return Differences between Trading and Non-trading Hours: Like Night and Day".** US equity premium earned overnight. [from memory]
- **Muravyev and Ni (2020), "Why Do Option Returns Change Sign from Day to Night?", Journal of Financial Economics 136(1), 219-238.** Delta-hedged S&P 500 option returns average about -0.7% per day: about -1.0% overnight and about +0.3% intraday (for option holders). Option prices do not fully reflect that volatility is much higher during trading hours. [verified]
- **Bhat, Pandey and Rao (2024)** find the same pattern in NIFTY options (section 1). [verified]
- **India equities overnight vs intraday:** I found no peer-reviewed study of NIFTY index overnight versus intraday returns in this review. A Substack post claims 8 of the top 10 NIFTY stocks have higher overnight than intraday returns, without data or method details. [unverified] GIFT Nifty trades for most of the Indian night, so "overnight" for NSE is partly price discovery that happens in GIFT City.

### Rationale

For the underlying: clientele effects and the timing of news and order flow. For options: implied volatility is quoted per calendar time, but realized volatility is concentrated in trading hours, so option sellers are overpaid for the overnight interval and underpaid for the trading session.

### Strength

Strong for options in the US (Muravyev and Ni) and one solid Indian replication (Bhat et al.). Untested for NIFTY index returns in what I found.

### Applicability

For the underlying, a daily overnight-only futures hold costs two trades per day with 0.05% STT on the sell side, which almost certainly exceeds any overnight drift at this size. For options, the finding is directly useful as a design rule: an option seller wants to hold positions overnight and over weekends, and has little reason to open short premium at 09:20 and close at 15:15. The popular Indian "09:20 short straddle" intraday template runs against both papers' findings.

### Data needed

NIFTY open and close from NSE Indices (EOD, free). Option open prices are in bhavcopy (OPEN field), but opening prints in options are noisy; intraday data is better for open-based tests.

---

## 5. Event volatility (RBI, Budget, elections, FOMC)

### Claimed edges

(a) Implied vol runs up before scheduled events and collapses after ("IV crush"); (b) investors underprice event uncertainty early, so buying straddles a few days before and selling just before the event earns positive returns; (c) political uncertainty is priced.

### Evidence

- **Shaikh and Padhi (2013), "Macroeconomic Announcements and the Implied Volatility Index: Evidence from India VIX", Margin: The Journal of Applied Economic Research 7(4), 417-442.** India VIX rises before scheduled macro announcements (including RBI policy) and returns to normal after uncertainty resolves. [verified]
- **Gao, Xing and Zhang (2018), "Anticipating Uncertainty: Straddles around Earnings Announcements", JFQA 53(6), 2587-2617.** ATM straddles bought three days before US earnings announcements and held to the announcement date earned a highly significant 3.34% average return; stronger for small, volatile, less liquid firms. [verified] This is single-stock evidence; index events are fewer and better covered by professionals.
- **Dubinsky, Johannes, Kaeck and Seeger (2019), "Option Pricing of Earnings Announcement Risks", Review of Financial Studies.** Model of announcement jump risk priced into options. [from memory]
- **Kelly, Pástor and Veronesi (2016), "The Price of Political Uncertainty: Theory and Evidence from the Option Market", Journal of Finance.** Options whose lives span national elections and global summits are more expensive, more so in weak economies. [from memory] Relevant to Indian general elections.
- **Lucca and Moench (2015), "The Pre-FOMC Announcement Drift", Journal of Finance:** large S&P 500 gains in the 24 hours before FOMC announcements. Kurov, Wolfe and Gilbert (2021, Finance Research Letters) report the drift largely disappeared after publication. A clean example of post-publication decay. [from memory]
- **India election day 2024:** NIFTY fell about 5.9% on 4 Jun 2024 results day, a move larger than the implied move priced the day before. One observation, but a reminder that short-vol through elections can be catastrophic. [figure from memory]

### Rationale

Hedgers buy protection late, closer to the event, which pushes IV up into the event. After the event, the jump component disappears from the surface. The crush itself is predictable and priced; the edge, if any, is in the timing of the run-up or in the implied move being too large or too small.

### Strength

Moderate for the IV run-up (India VIX study plus US single-stock straddle evidence). Weak for any claim that index event implied moves are systematically too high or too low. Sample sizes for India are small: about 6 RBI MPC decisions a year since Oct 2016, one Budget a year, one general election every five years.

### Applicability

Usable with weekly or monthly options. The pre-event long straddle fits the buying budget and has defined risk (the premium paid). Selling through events is the riskiest way to collect the crush.

### Data needed

EOD bhavcopy plus an event calendar (RBI MPC dates, Budget dates, election counting dates). Announcement time is fixed (RBI policy statement usually around 10:00 IST), so exiting at the prior day's close is clean with EOD data.

---

## 6. Day-of-week and weekend theta effects

### Claimed edge

Options are overpriced over non-trading periods because pricing treats calendar days as if they carry trading-day variance.

### Evidence

- **Jones and Shemesh (2018), "Option Mispricing Around Nontrading Periods", Journal of Finance 73(2).** US option returns are significantly lower (worse for holders) over weekends and holidays, consistent with market participants not fully adjusting for the low variance of non-trading periods. [from memory]
- **Muravyev and Ni (2020)** is the intraday version of the same idea (section 4).
- **India:** I found no academic study of weekend effects in NIFTY options. Sensibull's 2017 blog notes that Indian market makers lower IV on Fridays to pre-price weekend decay, and its worked example shows the expected weekend decay did not fully show up because of vega changes. [verified as a blog] Older academic work on NIFTY day-of-week effects in the index itself is mixed and tied to settlement-cycle changes. Bhat et al. (2024) report the NIFTY day-night gap is not explained by a weekend effect. [verified]

### Rationale

The same calendar-versus-trading-time mismatch as the overnight effect. If dealers already mark IV down on Friday, the effect is priced in and disappears.

### Strength

Good in the US, untested for NIFTY. Practitioner commentary suggests Indian market makers adjust for it, which would remove the edge.

### Applicability

The Tuesday expiry places a weekend inside the last four calendar days of each weekly option. A Thursday or Friday close entry captures the weekend. This is cheap to test with EOD data: compare Friday-close to Monday-close option P&L (two non-trading days) with average weekday close-to-close P&L, after adjusting for delta.

---

## 7. Skew, risk reversals, put-call ratio and open-interest signals

### Claimed edges

Steep skew or high put-call ratios forecast index direction; open-interest concentrations act as support and resistance; "max pain" predicts the expiry settlement.

### Evidence for

- **Andersen, Fusari and Todorov (2017):** the left-tail factor from weekly options predicts equity returns. [verified]
- **Bollerslev, Tauchen and Zhou (2009):** VRP predicts index returns at multi-month horizons. [verified]
- **Single-stock skew and volume:** Xing, Zhang and Zhao (2010, JFQA) and Cremers and Weinbaum (2010, JFQA) show stock-level skew and put-call parity deviations predict stock returns; Pan and Poteshman (2006, RFS) show option volume predicts stock returns, but the information sits in non-public opening-buy volume, and publicly observable put-call ratios carry much weaker signals. [from memory] These are cross-sectional stock results, not index timing.
- **India:** Jena, Tiwari and Mitra (2019), "Put-Call Ratio Volume vs. Open Interest in Predicting Market Return: A Frequency Domain Rolling Causality Analysis", Economies 7(1):24. NIFTY options 2001 to 2013: volume PCR shows causality to returns at about 2.5 days, OI PCR at about 12 days. This is a causality test, not a tradable backtest with costs. [verified]

### Evidence against

- **Kozhan, Neuberger and Schneider (2013), "The Skew Risk Premium in the Equity Index Market", Review of Financial Studies.** Most of the skew premium is explained by the variance premium. Selling skew (risk reversals) is largely the same bet as selling variance, not a separate edge. [from memory]
- **Bollen and Whaley (2004, JF) and Gârleanu, Pedersen and Poteshman (2009, RFS):** the shape of the smile reflects net buying pressure and dealers' hedging costs. Skew is a price of hedging demand, not a forecast of direction. [from memory]
- **Singh and Chaudhary (2023), Bank Nifty options:** PCR predictive power much weaker than claimed, weaker for index options than single stocks; only one year of data. [unverified detail]
- **Max pain and OI support/resistance:** no academic evidence found in this review. The underlying claim (writers "defend" strikes) conflicts with the fact that OI is two-sided and the largest writers hedge dynamically. Pinning research (section 2) finds small effects, not reliable targets.

### Strength

Weak for index-level timing with public PCR, OI or skew. The most defensible use of skew is as a cost input (OTM puts are the most overpriced options, per Coval and Shumway), not as a direction signal.

### Applicability and data

PCR and OI are in bhavcopy (EOD). If tested, register the hypothesis in advance (for example, "OI PCR above its 1-year 80th percentile predicts positive 10-day NIFTY return") and apply multiple-testing corrections. Expect nothing.

---

## 8. Machine learning, volatility forecasting and overfitting

### Volatility forecasting

- **Corsi (2009), "A Simple Approximate Long-Memory Model of Realized Volatility", Journal of Financial Econometrics 7(2).** HAR-RV: regress future realized variance on daily, weekly and monthly averages of past realized variance. Simple, robust, hard to beat. [from memory]
- **Christensen, Siggaard and Veliyev (2023), "A Machine Learning Approach to Volatility Forecasting", Journal of Financial Econometrics 21(5), 1680-1727.** On 29 DJIA stocks (about 2001 to 2017), regularized regressions, trees and neural nets beat HAR-type models even with only HAR inputs, with larger gains at longer horizons. [verified] Gains reported in secondary summaries are in the order of 10% MSE reduction, a meaningful but modest improvement. [unverified magnitude]
- **Bucci (2020), Journal of Financial Econometrics,** on neural nets for realized volatility; HARNet (CFS working paper); hybrid HAR-LSTM on Chinese data (Yao and Li). Results for LSTM versus HAR are mixed; a thesis on S&P 500 found LSTM underperformed and was sensitive to hyperparameters. [partly verified]
- **Kumar (2010),** HAR and variants for NIFTY daily volatility (IIT Madras). [verified title] A HAR model with India VIX as an extra regressor (HAR-X) is a natural low-parameter benchmark for NIFTY.
- **Bali, Beckmeyer, Mörke and Weigert (2023), "Option Return Predictability with Machine Learning and Big Data", Review of Financial Studies.** Delta-hedged single-stock option returns are predictable with ML, but profits concentrate in options that are costly to trade. [from memory]

For our purposes, the forecast only needs to be good enough to tell whether weekly ATM IV is clearly above expected realized vol. HAR or HAR-X with intraday-based realized variance (5-minute returns) is likely sufficient; daily-close data gives a noisier estimate. ML is unlikely to change a trading decision often enough to justify its overfitting risk at this sample size.

### Overfitting and multiple testing

- **Bailey and López de Prado (2014), "The Deflated Sharpe Ratio", Journal of Portfolio Management 40(5).** Adjusts a backtest Sharpe ratio for the number of trials, non-normal returns and sample length. [from memory]
- **Bailey, Borwein, López de Prado and Zhu (2017), "The Probability of Backtest Overfitting", Journal of Computational Finance;** also "Pseudo-Mathematics and Financial Charlatanism" (Notices of the AMS, 2014). Combinatorially symmetric cross-validation estimates how often the in-sample best configuration underperforms out of sample. [from memory]
- **Harvey, Liu and Zhu (2016), "...and the Cross-Section of Expected Returns", Review of Financial Studies 29(1).** Given hundreds of tested factors, a new factor should clear a t-statistic of about 3.0, not 2.0. [from memory]
- **McLean and Pontiff (2016), "Does Academic Research Destroy Stock Return Predictability?", Journal of Finance.** Anomaly returns are about 26% lower out of sample and about 58% lower post-publication. [from memory] Plan on any published edge being smaller than reported.

### Sample-size arithmetic for NIFTY weeklies

A rough rule: years of data needed for a given t-statistic is about (t / annualized Sharpe) squared. A true Sharpe of 1.0 needs about 4 years for t = 2 and about 9 years for t = 3. NIFTY weekly options started in Feb 2019, so there are about 7.5 years of weeklies, and the regime has changed three times since (Nov 2024 lot size and single weekly; Sept 2025 Tuesday expiry; Apr 2026 STT). The current Tuesday-expiry regime has only about 55 expiries. Any strategy that "works" only in the post-Sept 2025 window cannot be distinguished from luck. Test on the full Thursday-expiry history using equivalent days-to-expiry windows, then check the Tuesday period for consistency, not for proof.

---

## 9. Books and practitioner sources (what each is useful for)

- **Sheldon Natenberg, "Option Volatility and Pricing" (2nd ed., 2015).** Standard reference on pricing, Greeks, spreads and volatility trading mechanics. Read first for structure choice and risk of spreads.
- **Euan Sinclair, "Volatility Trading" (2nd ed., 2013).** VRP evidence, volatility measurement and forecasting, sizing (Kelly-style reasoning), and why most retail option strategies lack an edge.
- **Euan Sinclair, "Option Trading: Pricing and Volatility Strategies and Techniques" (2010)** and **"Positional Option Trading: An Advanced Guide" (2020).** The 2020 book is the most directly relevant: it insists an edge needs a reason (who pays you and why), centres on the VRP and a few documented anomalies, and treats trade structure and sizing as risk management rather than edge.
- **Colin Bennett, "Trading Volatility: Trading Volatility, Correlation, Term Structure and Skew" (2014).** Practitioner treatment of term structure, skew dynamics (sticky strike versus sticky delta), and how dealers think about event and non-trading-day volatility.
- **Nassim Nicholas Taleb, "Dynamic Hedging" (1997).** Pin risk, expiry-day gamma, liquidity holes, and the tail-risk case against unhedged option selling. His later writing is the standard critique of "picking up pennies" short-vol strategies.
- **AQR (Israelov and others):** papers listed in section 1. Useful for decomposing what option strategies are really paid for.
- **CBOE benchmark studies:** PUT, BXM, WPUT, CNDR, BFLY (section 1).
- **Quantpedia summaries, CXO Advisory, Alpha Architect:** reliable secondary summaries of academic papers; always go back to the paper.
- **Moontower (Kris Abdelmessih):** conceptual writing on option pricing, VRP and why vol selling is not free money. Good for intuition; not evidence.
- **Option Alpha research:** large platform-user samples on SPY 0DTE; win rates without loss sizes, self-selected users. Low evidentiary value.
- **SpotGamma research notes:** dealer-gamma interpretations; check against Dim, Eraker and Vilkov and Ni, Pearson, Poteshman and White before acting.
- **Robeco, Man Group, Two Sigma, Resonanz:** I did not find specific VRP or Indian options whitepapers from these firms in this review. Not cited.

---

## 10. Ranked shortlist: five candidate strategies to test on NIFTY

Common rules for all five:

- One lot only during testing and any later paper trading. Defined risk on every position.
- Cost model per leg: brokerage, STT at post-Apr 2026 rates (0.15% of premium on option sells; 0.15% of intrinsic on exercised ITM options; 0.05% on futures sells), exchange charges, 18% GST on brokerage and exchange charges, stamp duty, and a bid-ask haircut (start with half the typical spread per leg, then double it as a stress test). Bhavcopy has no quotes, so the haircut is an assumption that must be stress-tested.
- Expected move (EM) = price of the ATM straddle at entry. Strikes are rounded to the nearest 50 points.
- Report net P&L per trade, hit rate, average win and loss, worst week, 5% CVaR, and the share of total P&L from the worst 5% of trades. Compute the deflated Sharpe ratio using the true number of variants tried.
- Split results by regime: before Nov 2024, Nov 2024 to Aug 2025 (single weekly, Thursday), Sept 2025 onward (Tuesday).

### Rank 1: Filtered weekly iron condor, Thursday close to Tuesday expiry

**Why first:** the VRP is the best-documented option premium globally, it is richest at short maturities, it exists in India (Garg and Vipul; Sankar et al.), it accrues overnight and over weekends (Bhat et al.; Jones and Shemesh), and a hold-to-expiry structure keeps costs to one entry.

**Rules sketch**

- Entry: Thursday at 15:20 to 15:25 IST (backtest: Thursday close), into the following Tuesday weekly. Holding period: Friday, the weekend, Monday and Tuesday (three sessions plus weekend). Robustness variant: Friday close entry.
- Short call and short put at ATM plus and minus 1.0 x EM. Long wings at ATM plus and minus 2.0 x EM. Two structural parameters, both scaled to volatility.
- Exit: hold to expiry; OTM legs expire worthless with no exit cost. Optional variant (needs intraday data): close everything at 15:00 on Tuesday to avoid the settlement window.
- No stop loss in the baseline (the wings define the risk). Test a stop at 1.5 x credit only as a variant and count it as an extra trial.

**Signal and filters (trade only if all hold)**

1. VRP filter: weekly ATM IV greater than 1.1 x HAR-X forecast of realized vol over the remaining life.
2. Term structure: weekly ATM IV no higher than next-monthly ATM IV (no inversion).
3. Event filter: skip if an RBI MPC decision, Union Budget or election counting day falls within the holding period.

**Why it should persist:** structural demand for short-dated protection and lottery-like OTM options from hedgers and retail; sellers bear jump risk that cannot be hedged continuously. This is a risk premium, so it should survive publication, but it can be thin after costs.

**What would falsify it:** net mean P&L per trade not distinguishable from zero (t below 2) over 2019 to 2026 using equivalent days-to-expiry windows; filtered version not better than unfiltered; or the worst 5% of weeks wiping out more than the cumulative credit of the rest.

**Data:** EOD bhavcopy only (Thursday close prices, expiry settlement), plus India VIX and a daily realized-vol series. Intraday data improves the HAR inputs but is not required.

**Size check (illustrative):** with EM of 300 points and a net credit of about 60 points, the maximum loss is about (300 minus 60) x 65 = INR 15,600 per lot, roughly 10% of a INR 1.5 lakh account. A run of five or six maximum losses, which happens in volatile periods, would take a large share of the account.

### Rank 2: Trend-filtered short put spread on the monthly expiry

**Why second:** it combines three documented premia (equity premium, VRP, and OTM put overpricing per Coval and Shumway and the CBOE PUT studies), the trend filter is a single interpretable rule, and it uses the monthly expiry, so it survives if weekly expiries are removed.

**Rules sketch**

- Entry: close of the first trading day after the monthly expiry (last Tuesday of the month), into the next monthly expiry (about 20 sessions).
- Sell the put nearest 0.25 delta; buy the put 1.0 x monthly EM below it.
- Exit: hold to expiry. Variant: close at the session close when the spread has captured 50% of its maximum profit (one extra parameter; count it as a trial).

**Filters**

1. Trend: NIFTY close above its 100-day moving average on the entry day.
2. Term structure: front-month ATM IV no higher than second-month ATM IV.

**Why it should persist:** institutional demand for index puts is structural (mandates, risk limits); the trend filter targets the regime where volatility clusters with drawdowns.

**What would falsify it:** filtered returns no better than unfiltered after costs; or positive results only in the 2020 to 2021 rebound period; or results driven entirely by the equity premium (a long NIFTY futures position scaled to the same delta does as well).

**Data:** EOD bhavcopy only.

### Rank 3: Expiry-eve iron fly, Monday close to Tuesday settlement

**Why third:** it targets the overnight component of the NIFTY VRP that Bhat et al. found and the 0DTE retail demand that Beckmeyer et al. and SEBI's data imply. Holding to settlement avoids the exit costs that killed the close-to-open version in Bhat et al. It ranks below the first two because expiry-day risk is adversarial (gamma, Jane Street-style flows, 2% extra ELM) and the weekly expiry may not last.

**Rules sketch**

- Entry: Monday at 15:20 to 15:25 IST (backtest: Monday close).
- Short ATM call and put (strike nearest the NIFTY futures price); long wings at ATM plus and minus 1.0 x EM.
- Exit: hold to Tuesday settlement. Variant (needs intraday data): close at 10:00 Tuesday, to capture only the overnight component.

**Filters**

1. Same VRP filter as Rank 1, using 1-day HAR-X forecast.
2. Skip if India VIX rose more than 10% on Monday (fresh shock) or if a scheduled event falls on Tuesday.

**Why it should persist:** the calendar-versus-trading-time mismatch in option pricing (Muravyev and Ni; Jones and Shemesh) and retail same-day lottery demand. Both are behavioural and structural; neither requires an information advantage.

**What would falsify it:** net mean P&L at or below zero; or Monday-close-to-Tuesday-open P&L no better than the average weekday overnight; or P&L dominated by a handful of quiet Tuesdays with large tail losses on trend days.

**Data:** EOD bhavcopy for the hold-to-settlement version; minute data for the 10:00 exit variant.

### Rank 4: Pre-event implied-vol run-up, long straddle (buying budget)

**Why fourth:** fits the under-INR 1 lakh buying budget with risk limited to the premium; documented IV run-up into Indian macro announcements (Shaikh and Padhi) and positive pre-event straddle returns in US single stocks (Gao, Xing and Zhang). Ranks lower because the number of index events is small and the effect is less tested at index level.

**Rules sketch**

- Events: RBI MPC decision days and Union Budget day. (General election counting days are too rare to test; treat separately.)
- Entry: close of T minus 3 sessions before the announcement day. Buy the ATM straddle of the nearest expiry that falls after the announcement.
- Exit: close of T minus 1. Never hold through the announcement.
- Variant: long calendar (sell the weekly that expires before the event, buy the weekly that expires after), a debit structure with lower theta cost.

**Signal:** the event itself. Optional filter: skip if India VIX is already above its 1-year 80th percentile (run-up likely already priced).

**Why it should persist:** hedgers buy protection late; supply of event options from sellers is limited because of jump risk.

**What would falsify it:** average net return from T minus 3 to T minus 1 at or below zero across roughly 60 MPC events since Oct 2016 plus 10 Budgets. Low statistical power: even a true positive effect may not reach t = 2. Pre-commit to the rules before looking at results.

**Data:** EOD bhavcopy plus an event calendar.

### Rank 5: Last-half-hour momentum in NIFTY futures (research only)

**Why fifth:** the evidence is real in global futures (Gao et al.; Baltussen et al.; Li, Sakkas and Urquhart) but mixed out of sample and unverified in India. Post-Apr 2026 STT makes it expensive, and one futures lot is beyond the buying budget. Its main value may be defensive: identifying days when short-gamma option positions should not be held into the close.

**Rules sketch**

- Signal at 15:00:00 IST: return of NIFTY near-month futures from the prior session's 15:29 last traded price to 15:00 today (Baltussen-style "rest of day").
- Trade only if the absolute signal exceeds 0.5 x the HAR forecast of daily volatility. Enter in the signal's direction at 15:00; exit at 15:29 at market.
- Instrument: one lot of near-month futures, or a deep ITM option (delta about 0.8) to reduce capital, at the cost of wider spreads.
- Split results: Tuesday expiry days versus other days (the hedging-demand story predicts a stronger effect on expiry days).

**Why it might persist:** short-gamma hedging and late institutional execution concentrate in the closing VWAP window.

**What would falsify it:** net mean per trade at or below zero after STT and a 1-point slippage per side; or effect present only before 2020.

**Data:** minute bars of NIFTY futures and spot. Not available from bhavcopy.

### Not recommended for testing (on current evidence)

- Unhedged short straddles or strangles: margin exceeds the account, and one gap can exceed it.
- 09:20 intraday short straddles: the intraday leg of the option premium is weak or negative in both US and NIFTY studies.
- Buying OTM options on expiry day: the retail losing trade documented by Beckmeyer et al. and implied by SEBI's data.
- PCR, max pain and OI support or resistance as direction signals: no credible evidence of tradable value after costs.

---

## 11. Suggested test order

1. Build the cost model and an EOD dataset from NSE bhavcopy (2019 onward) plus India VIX; compute IV per strike with Black-76 on the futures price.
2. Run the holding-window decomposition once for ATM iron flies: Thursday close to Tuesday, Friday close to Tuesday, Monday close to Tuesday, Friday close to Monday close. This single study tests the core claims behind Ranks 1 and 3 and the weekend effect.
3. Add filters one at a time, logging every variant for the deflated Sharpe ratio.
4. Rank 2 and Rank 4 next (EOD only).
5. Rank 5 only if minute data becomes available from a source the user signs up for.
6. Paper trade the survivor(s) for at least three months before risking money, and compare live fills with assumed costs.

---

## Sources consulted in this review

India regulation and market structure
- [SEBI FY25 study coverage, Business Standard](https://www.business-standard.com/amp/markets/news/net-losses-of-traders-in-fo-widens-in-fy25-sebi-study-125070701221_1.html)
- [FY25 average loss, Value Research](https://www.valueresearchonline.com/stories/225398/average-trader-lost-rs-1-1-lakh-fo-fy25/)
- [SEBI FY22-FY24 study coverage, Outlook Money](https://www.outlookmoney.com/invest/93-of-individual-traders-suffered-losses-in-fo-in-last-3-years-sebi-study)
- [SEBI FY24 study and algo profits, Wright Research](https://wrightresearch.in/blog/sebi-futures-and-option-report-individual-traders-in-fandos-incur-rs-18-lakh-crore-loss-over-3-years)
- [SEBI FY26 study and costs, Outlook Money](https://www.outlookmoney.com/invest/sebi-futures-options-study-transaction-costs-traders-losses-fy26)
- [FY26 Rajya Sabha figures, Moneylife](https://www.moneylife.in/article/retail-fo-traders-lose-rs91685-crore-in-fy26-despite-sebi-curbs-average-loss-hits-rs117-lakh-govt/81318.html)
- [SEBI Oct 2024 measures, Zerodha Z-Connect](https://zerodha.com/z-connect/business-updates/sebis-new-rules-for-index-derivatives-heres-whats-changing)
- [New F&O rules effective Nov 2024, Business Standard](https://www.business-standard.com/amp/markets/news/new-f-o-rule-to-come-into-effect-from-thursday-nov-21-here-s-what-changes-124112000292_1.html)
- [Weekly expiry on Tuesday, OneTradeJournal](https://onetradejournal.com/glossary/weekly-expiry)
- [NIFTY lot size, PL India](https://www.plindia.com/blogs/what-is-nifty-lot-size/)
- [Intraday position limits framework, SCC Online](https://www.scconline.com/blog/post/2025/09/03/sebi-equity-derivatives-intraday-limits-2025/)
- [STT hike from Apr 2026, 5paisa](https://www.5paisa.com/news/stt-hike-on-fo-to-take-effect-from-april-1-amid-rising-options-activity)
- [SEBI chairman on weekly expiry, Outlook Money](https://www.outlookmoney.com/news/sebi-to-float-consultation-paper-on-endin-futures-and-options-weekly-expiry-soon-tuhin-kanta-pandey)
- [SEBI consultation on Tuesday/Thursday expiry, Kotak](https://www.kotaksecurities.com/investing-guide/articles/sebi-proposal-on-derivatives-expirty-date)
- [Jane Street interim order, Moneylife](https://www.moneylife.in/article/jane-street-accused-of-massively-rigging-of-indias-derivatives-market-sebi-orders-ban-escrow-of-rs4843-crore-illegal-gains/77585.html)
- [Jane Street episode, ECGI blog](https://www.ecgi.global/publications/blog/expiry-day-and-the-governance-of-algorithmic-trading-the-jane-street-episode)

India academic evidence
- [Garg and Vipul 2015, IDEAS](https://ideas.repec.org/a/wly/jfutmk/v35y2015i9p795-812.html)
- [Sankar, Ramachandran and Lukose 2020, IDEAS](https://ideas.repec.org/a/eee/reveco/v70y2020icp321-334.html)
- [Bhat, Pandey and Rao 2024, summary on Harbourfront Quant](https://harbourfrontquant.substack.com/p/volatility-risk-premium-is-a-reward)
- [Bhat, Pandey and Rao 2024, IDEAS listing](https://ideas.repec.org/a/wly/jfutmk/v44y2024i8p1320-1337.html)
- [Jain, Varma and Agarwalla 2019, IDEAS](https://ideas.repec.org/a/wly/jfutmk/v39y2019i2p150-163.html)
- [Varma blog on Indian option smile](https://www.jrvarma.in/blog/Y2018-19/smile-paper.html)
- [Pillai preprint, SSRN 6876580 (unverified)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6876580)
- [NSE Working Paper 9/2013 on India VIX](https://nsearchives.nseindia.com/research/content/res_WorkingPaper9.pdf)
- [Shaikh and Padhi 2013, IDEAS](https://ideas.repec.org/a/sae/mareco/v7y2013i4p417-442.html)
- [Vipul 2005 expiration-day effects, IDEAS](https://ideas.repec.org/a/wly/jfutmk/v25y2005i11p1045-1065.html)
- [Jena, Tiwari and Mitra 2019, MDPI Economies](https://www.mdpi.com/2227-7099/7/1/24)
- [PCR in index options, Harbourfront Quant](https://harbourfrontquant.substack.com/p/is-the-put-call-ratio-a-reliable)
- [Hedging demand and intraday momentum in India, ResearchGate (unverified)](https://www.researchgate.net/publication/383567351_Hedging_Demand_and_Intraday_Momentum_within_the_Indian_Stock_Market)
- [Sensibull on the weekend effect](https://blog.sensibull.com/2017/12/26/the-weekend-effect/)
- [Overnight vs intraday in NIFTY stocks, Substack (unverified)](https://theschrodingercat.substack.com/p/the-market-gives-during-the-night)

0DTE and short-dated options
- [Beckmeyer, Branger and Gayda, CXO Advisory summary](https://cxoadvisory.com/individual-investing/retail-0dte-option-trader-performance)
- [Beckmeyer et al., Neudata review](https://www.neudata.co/literature-reviews/zero-day-to-expiry-options-a-losing-bet-for-retail-traders)
- [Vilkov 0DTE Trading Rules, Hull Tactical summary](https://hulltactical.com/2026/07/08/0dte-options-tiny-edge-huge-distribution/)
- [Bandi, Fusari and Renò, EconBiz record](https://econbiz.de/Record/0dte-option-pricing-bandi-federico/10014348685)
- [0DTE gamma and volatility, Harbourfront Quant](https://harbourfrontquant.substack.com/p/the-rise-of-0dte-options-cause-for)
- [Andersen, Fusari and Todorov 2017, Kellogg](https://www.kellogg.northwestern.edu/academics-research/research/detail/2017/short-term-market-risks-implied-by-weekly-options/)
- [Term structure of variance risk, NY Fed SR 736](https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr736.pdf)
- [Option Alpha 0DTE data](https://optionalpha.com/blog/0dte)

VRP, practitioner and CBOE
- [Israelov and Nielsen, Covered Calls Uncovered, AQR](https://www.aqr.com/Insights/Research/Journal-Article/Covered-Calls-Uncovered)
- [AQR, Understanding the Volatility Risk Premium](https://www.aqr.com/Insights/Research/White-Papers/Understanding-the-Volatility-Risk-Premium)
- [CBOE put-write study (Bondarenko 2019)](https://www.cboe.com/insights/posts/white-paper-shows-volatility-risk-premium-facilitated-higher-risk-adjusted-returns-for-put-index/)
- [CBOE options-selling index study 2016](https://ir.cboe.com/news/news-details/2016/Study-Analyzes-Performance-of-CBOE-SP-500-SPX-Options-Selling-Indexes-02-23-2016/default.aspx)
- [CBOE BFLY and CNDR](https://www.cboe.com/insights/posts/benchmark-indices-series-volatility-management-with-cboes-bfly-and-cndr-indices/)
- [Dörries, Korn and Power, Quantpedia summary](https://quantpedia.com/?p=23956)
- [Johnson 2017 JFQA, IDEAS](https://ideas.repec.org/a/cup/jfinqa/v52y2017i06p2461-2490_00.html)
- [VIX term structure slope, CXO Advisory](https://www.cxoadvisory.com/volatility-effects/vix-term-structure-slope-and-variance-asset-future-returns/)

Intraday momentum, overnight returns, events
- [Gao, Han, Li and Zhou, working paper](https://www.smallake.kr/wp-content/uploads/2015/01/SSRN-id2440866.pdf)
- [Baltussen, Da, Lammers and Martens](https://www3.nd.edu/~zda/intramom.pdf)
- [Rosa 2022, IDEAS](https://ideas.repec.org/a/wly/jfutmk/v42y2022i12p2218-2234.html)
- [Lou, Polk and Skouras 2019](https://personal.lse.ac.uk/polk/research/TugOfWar.pdf)
- [Muravyev and Ni 2020, IDEAS](https://ideas.repec.org/a/eee/jfinec/v136y2020i1p219-238.html)
- [Gao, Xing and Zhang 2018, Cambridge](https://resolve.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis/article/anticipating-uncertainty-straddles-around-earnings-announcements/7B34877AD5E06304BA3C55FBA3219FDD)

Volatility forecasting
- [Christensen, Siggaard and Veliyev, CREATES working paper](https://repec.econ.au.dk/repec/creates/rp/21/rp21_03.pdf)
- [Can LSTM outperform volatility-econometric models?, arXiv](https://arxiv.org/pdf/2202.11581)
- [HARNet, IDEAS](https://ideas.repec.org/p/zbw/cfswop/680.html)
