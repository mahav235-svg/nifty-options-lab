# Research plan (written before any backtest was run)

Date fixed: 18 Oct 2026. Data: NSE F&O bhavcopy 2018-01-01 to 2026-10-16, NIFTY and India VIX daily
(2008 onward) and one-minute bars (2022 onward). Instrument: NIFTY index options (weekly from Feb
2019, monthly throughout), with BANKNIFTY weeklies (2018 to Nov 2024) as an out-of-market check.

The point of writing this down first is to fix the number of things tried, so the multiple-testing
correction is real, and to fix what counts as failure, so a weak result cannot be talked up later.

## Hypotheses

| id | Hypothesis | Economic reason | Structure | Data |
|---|---|---|---|---|
| H1 | Short-dated NIFTY options are overpriced relative to subsequent realised volatility, and a defined-risk short structure held to expiry earns a positive net premium | Retail lottery demand for weekly OTM options and institutional demand for protection; sellers are paid for jump risk they cannot hedge continuously (Coval and Shumway 2001; Carr and Wu 2009; Garg and Vipul 2015 for India) | Iron condor / iron fly, held to expiry | EOD |
| H1f | The H1 premium is larger when ATM implied vol is high relative to a HAR forecast of realised vol, and when no scheduled event falls in the holding window | VRP is persistent and forecastable (Garg and Vipul 2015); event risk is priced separately | Same, filtered | EOD |
| H2 | A trend-filtered short put spread on the monthly expiry earns the equity and put premia with smaller drawdowns than unfiltered | OTM puts are the most overpriced options (Coval and Shumway); volatility clusters in drawdowns | 0.25-delta put spread, 1 EM wide | EOD |
| H3 | An ATM straddle bought three sessions before an RBI decision or Budget and sold the session before gains from the implied-vol run-up | Hedgers buy protection late (Shaikh and Padhi 2013; Gao, Xing and Zhang 2018) | Long straddle, never held through the event | EOD |
| H4 | Short-option returns accrue overnight, not intraday; a close-to-open short straddle is profitable before costs and not after | Calendar-time pricing vs trading-time variance (Muravyev and Ni 2020; Bhat, Pandey and Rao 2024) | Close-to-open short straddle | EOD (open prints) |
| H5 | The NIFTY return from the open to 14:59 predicts the 15:00 to 15:29 return | Short-gamma hedging and close-window execution (Gao et al. 2018; Baltussen et al. 2021) | Futures, last half hour | 1-minute, 2022 onward |

## Parameter grids (the full set of variants that will be run)

* H1/H1f: entry sessions-to-expiry {2, 3, 4, 5} x short strikes {0, 0.5, 0.75, 1.0, 1.25} EM x wing width
  {0.5, 1.0} EM x VRP threshold {0, 1.0, 1.15, 1.3} x event filter {on, off} = 320 variants.
* H2: short delta {0.20, 0.25, 0.30} x width {0.75, 1.0} EM x trend filter {none, > 0} = 12.
* H3: entry offset {2, 3, 5} x event set {RBI, Budget, both} = 9.
* H4: 1 variant (replication).
* H5: thresholds {0, 0.25, 0.5} standard deviations of the signal = 3.

Total: 345 variants. Every Sharpe ratio reported is deflated for this count.

## Execution and cost assumptions

* Fill at the official close (last-half-hour VWAP for derivatives) plus a slippage allowance of
  max(1 tick, 0.5% of price) plus 1 tick per leg, each way. Stress tests at 2x and 3x.
* A leg fills only if the contract traded at least 50 contracts that day.
* Costs at the rates in force on each date (brokerage Rs 20 per order, STT, exchange, SEBI, stamp
  duty, GST); STT on long legs settled in the money.
* Hold-to-expiry trades settle at the official index close on expiry day.
* Account: Rs 1.5 lakh, one structure at a time, 1 lot (the minimum).

## What counts as an edge

All of the following, on out-of-sample trades only:

1. Walk-forward: parameters chosen each half-year using only the prior three years; the chosen
   variant is traded in the next half-year. The concatenated out-of-sample record is the result.
2. Mean net P&L per trade above zero with a block-bootstrap 95% interval excluding zero.
3. Deflated Sharpe ratio probability above 0.95 given 345 trials.
4. Positive in at least two of the three market-structure regimes: before 20 Nov 2024; 20 Nov 2024
   to 31 Aug 2025 (single weekly, Thursday); 1 Sep 2025 onward (Tuesday expiry, then the April 2026
   STT increase).
5. Survives the 2x slippage stress test.
6. Worst 5% of trades do not erase more than the gains of the rest.
7. Same rules, untouched, are not negative on BANKNIFTY weeklies (2018 to Nov 2024).

A variant that fails any of these is reported as failing, with its numbers.

## Known limitations fixed in advance

* No bid-ask quotes in the data; slippage is an assumption and is stress-tested.
* The close price is a VWAP, so a live order at 15:25 will fill near, not at, it.
* Weekly options exist only from Feb 2019; earlier years test the monthly expiry only.
* The current Tuesday-expiry regime has about 55 expiries; it can confirm, not prove.

---

# Round 2 (added 18 Oct 2026, after round 1 results, before running anything below)

Round 1 result: no pre-registered hypothesis met the bar (see RESULTS.md). One round-1 result was
strongly negative: buying the ATM straddle two sessions before an RBI MPC decision and selling it the
session before lost money on 41 of 54 events (t = -4.4). That suggests the opposite position earns a
premium. Because this idea comes from looking at round-1 output, it is tested as a new hypothesis,
with its own trials added to the multiple-testing count and a placebo test.

| id | Hypothesis | Economic reason | Structure |
|---|---|---|---|
| R2a | Selling ATM premium in the sessions just before a scheduled RBI MPC decision (or the Union Budget), and closing before the announcement, earns more than the same trade on ordinary days | "Calm before the storm": realised volatility falls in the sessions before scheduled announcements while implied volatility carries the event (Jones, Lamont and Lumsdaine 1998, JFE; Bomfim 2003, JBF; Shaikh and Padhi 2013 for India VIX) | Iron fly, wings at ATM +/- 1 EM, nearest expiry after the event; enter at the close k sessions before, exit at the close of the session before the event |
| R2b | Holding the same short position through the announcement (enter the close before, exit the close of event day) earns the implied-vol crush | Event jump premium in implied vol | Same iron fly, held over the event |

Grid: k in {2, 3} x events {RBI, RBI+Budget} for R2a (4 trials); events {RBI, RBI+Budget} for R2b
(2 trials). Naked straddle versions are computed for reference only (they need more margin than the
account has). Trials now total 345 + 6 = 351.

Placebo: the same structure, same entry rule relative to the nearest expiry, on every session that is
not within 5 sessions of a scheduled event. R2a passes only if its mean is above the placebo mean
with a difference-in-means t above 2, in addition to the round-1 criteria (bootstrap interval above
zero, deflated Sharpe above 0.95 at 351 trials, positive in at least two regimes, survives 2x slippage).
Event counts are small (about 54 RBI decisions since 2018), so the regime test uses pre/post Nov 2024
only.

## Round 2, addendum (added after the first R2 run, before running the variants below)

The first R2 run showed the event effect in the naked straddle (needs more margin than the account
and has unlimited risk) but not in the iron fly with wings at 1 EM, whose wings cost more than they
save. Wider, cheaper wings keep the loss defined and fit the account. Added trials: wings at 2 and 3
EM for the two T-2 to T-1 variants and the two T-3 to T-1 variants (8 trials). Trials now total 359.
Pass criteria unchanged.

## Round 2, confirmation tests (added after the corrected R2 run, before running them)

Best R2 variant, frozen exactly: iron fly, short ATM, wings at ATM +/- 3 EM, nearest expiry after the
event, open at the close two sessions before the event session, close at the close of the session
before it. It passed five of six criteria and failed the deflated Sharpe test (0.25 at 359 trials),
which 52 events cannot pass.

Two confirmation tests on samples the rule was not chosen on. No parameter is changed; these are
not new trials for selection.

* C1, BANKNIFTY around RBI MPC decisions (2018 onward). Banks are the sector most exposed to the
  policy rate, so the pre-announcement pattern should appear in bank-index options if it is real.
* C2, NIFTY around FOMC decisions (2021 onward). The FOMC announces after the NSE close, so the
  first NSE session that can react is the next one; the "session before" is the FOMC day itself.

Confirmation passes if each test has a positive mean and the pooled confirmation sample (C1 + C2)
has a bootstrap 95% interval above zero. Either way, the result is reported.
