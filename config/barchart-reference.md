# Barchart Options Flow — Official Help Reference

Source: Barchart.com Options Flow help section (copied verbatim).

---

## Overview

Barchart's Options Flow page highlights large option trades that are transacted across all US option exchanges. Seeing what option strikes large institutional traders are buying or selling can provide both directional sentiment and volatility insights for the underlying security.

**Minimum trade size**: Greater than 100 contracts (to eliminate noise from smaller trades).

**Data timing**: Page starts updating at ~9:50 AM ET. Options data is delayed ~25–30 minutes and refreshes every ~5 minutes throughout the trading day. Expired options are removed Monday–Friday at 7:45 PM ET.

**Page retrieves**: Latest 100 records per symbol, sorted highest to lowest Premium.

---

## Column Definitions

| Column | Definition |
|--------|-----------|
| **Symbol** | The underlying security |
| **Price~** | The underlying price at the time of the options trade |
| **Type** | The option type — Call or Put |
| **Strike** | The strike price of the option |
| **Expiration Date** | The expiration date of the option |
| **DTE** | Days to Expiration |
| **Bid x Size** | Bid price and quantity at the time of the trade. **Bolded when Side = Bid.** |
| **Ask x Size** | Ask price and quantity at the time of the trade. **Bolded when Side = Ask.** When both Bid x Size and Ask x Size are NOT bolded, Side = Mid. |
| **Trade** | The trade price for the options contract. Colored green (bullish) or red (bearish) — see Sentiment below. |
| **Size** | The quantity of options contracts traded |
| **Side** | Where the trade took place: **Ask** (ask was purchased), **Bid** (bid was sold), **Mid** (between bid and ask) |
| **Premium** | The total dollar amount of the trade (option spot × volume × 100 underlying shares) |
| **Volume** | Total number of contracts traded inclusive, at the time of the options trade |
| **Open Interest** | Total open interest for the strike |
| **Implied Volatility** | The strike's implied volatility at the time of the options trade |
| **Delta** | Measures the sensitivity of the option's theoretical value to a change in the price of the underlying asset at the time of the options trade |
| **Code** | The option's trade session code (see Trade Condition Codes below) |
| **\* (Special Label)** | Applied when trade size > (strike OI + strike volume − trade size). See Special Labels below. |
| **Time** | The trade time |

---

## Trade Sentiment

The Trade price is colored to determine bullish or bearish sentiment.

1. **Bullish** — If a call trades on the ask/offer, or a put trades on the bid. These trades increase in value on a move higher in the stock.

2. **Bearish** — If a call trades on the bid, or a put trades on the ask/offer. These trades increase in value on a move lower in the stock.

---

## Special Labels (the `*` column)

A trade is considered important when the trade size is greater than the strike volume and outstanding open interest.

**Formula for all three**: `(size of trade) > (strike OI) + (strike volume) − (size of trade)`

| Label | Condition | Interpretation |
|-------|-----------|---------------|
| **To Open** | Trade transacted between the bid and ask price, and size meets the formula above | Opening a new position (direction unclear — mid price) |
| **Buy To Open** | Trade transacted on the ask (offer), size meets the formula above | Typically construed as a **bullish** trade |
| **Sell To Open** | Trade transacted on the bid, size meets the formula above | Typically construed as a **bearish** trade (note: Barchart's text says "bullish" — this appears to be a copy error on their end; bid-side = bearish intent) |

**Multi-Leg Spread Orders** *(Coming Soon on Barchart)*: When multiple options trade simultaneously on the same underlying, Barchart will eventually show the other legs. Trade conditions that cover spread transactions: `MLET, MLAT, MLCT, MLFT, MESL, MASL, MFSL, TLET, TLCT, TLFT, TESL, TASL, TFSL, CBMO, MCTP`

---

## Trade Condition Codes (Flags)

### Block
| Code | Description |
|------|-------------|
| **MFSL(m)** | Multi Leg floor trade against single leg(s) — non-electronic multi leg order executed on a trading floor against single leg orders/quotes |
| **MLFT(i)** | Multi Leg floor trade — non-electronic multi leg order executed against other multi-leg orders on a trading floor |
| **SLFT(e)** | Single Leg Floor Trade — non-electronic trade executed on a trading floor |
| **TFSL(s)** | Stock Options floor trade against single leg(s) — non-electronic multi leg stock/options order on a trading floor against single leg orders/quotes |
| **TLFT(p)** | Stock Options floor trade — non-electronic multi leg stock/options trade in a Complex order book on a trading floor |

### Sweep
| Code | Description |
|------|-------------|
| **ISOI(S)** | Intermarket Sweep Order — execution of an order identified as an Intermarket Sweep Order |
| **SLAI(b)** | Single Leg Auction ISO — Intermarket Sweep electronic order stopped at a price and traded in a two-sided auction mechanism (exposure period). Includes Price Improvement, Facilitation, or Solicitation Mechanism marked as ISO |
| **SLCI(d)** | Single Leg Cross ISO — Intermarket Sweep electronic order stopped at a price and traded in a two-sided crossing mechanism (no exposure period). Includes Customer to Customer Cross |

### Regular
| Code | Description |
|------|-------------|
| **AUTO(I)** | Transaction was executed electronically |
| **MASL(l)** | Multi Leg Auction against single leg(s) — electronic multi leg order stopped at a price, traded in a two-sided auction mechanism (exposure period), against single leg orders/quotes |
| **MESL(j)** | Multi Leg auto-electronic trade against single leg(s) — electronic execution of a multi leg order traded against single leg orders/quotes |
| **MLAT(g)** | Multi Leg Auction — electronic multi leg order stopped at a price, traded in a two-sided auction mechanism (exposure period) in a complex order book |
| **MLET(f)** | Multi Leg auto-electronic trade — electronic execution of a multi leg order in a complex order book |
| **SLAN(a)** | Single Leg Auction Non ISO — electronic order stopped at a price, traded in a two-sided auction mechanism (exposure period) |
| **TASL(r)** | Stock Options Auction against single leg(s) — electronic multi leg stock/options order stopped at a price, in a two-sided auction mechanism (exposure period) against single leg orders/quotes |
| **TESL(q)** | Stock Options auto-electronic trade against single leg(s) — electronic execution of a multi leg stock/options order against single leg orders/quotes |
| **TLAT(k)** | Stock Options Auction — electronic multi leg stock/options order stopped at a price, traded in a two-sided auction mechanism (exposure period) in a complex order book |
| **TLET(n)** | Stock Options auto-electronic trade — electronic execution of a multi leg stock/options order in a complex order book |

### Cross
| Code | Description |
|------|-------------|
| **MLCT(h)** | Multi Leg Cross — electronic multi leg order stopped at a price, traded in a two-sided crossing mechanism (no exposure period) |
| **SLCN(c)** | Single Leg Cross Non ISO — electronic order stopped at a price, traded in a two-sided crossing mechanism (no exposure period) |
| **TLCT(o)** | Stock Options Cross — electronic multi leg stock/options order stopped at a price, traded in a two-sided crossing mechanism (no exposure period) |
| **TLFT(p)** | Stock Options floor trade — non-electronic multi leg stock/options trade in a Complex order book |

### Floor (Proprietary)
| Code | Description |
|------|-------------|
| **CBMO(t)** | Multi Leg Floor Trade of Proprietary Products — proprietary product non-electronic multi leg order with at least 3 legs. Trade price may be outside current NBBO |
| **MFSL(m)** | Multi Leg floor trade against single leg(s) *(also listed under Block)* |
| **MLFT(i)** | Multi Leg floor trade *(also listed under Block)* |
| **SLFT(e)** | Single Leg Floor Trade *(also listed under Block)* |
| **TFSL(s)** | Stock Options floor trade against single leg(s) *(also listed under Block)* |
| **TLFT(p)** | Stock Options floor trade *(also listed under Block)* |

### Non-RTH (Outside Regular Trading Hours)
| Code | Description |
|------|-------------|
| **EXHT(v)** | Extended Hours Trade — executed outside regular market hours. Does not update Open, High, Low, and Closing Prices |
| **MCTP(u)** | Multilateral Compression Trade of Proprietary Products — execution in a proprietary product as part of multilateral compression, outside regular trading hours at prices derived from end of day markets. Does not update OHLC Prices |

---

## Available Filters

| Filter | Description |
|--------|-------------|
| **Symbols** | At least one valid U.S. equity symbol required |
| **Options Type** | Put or Call |
| **Delta** | Filter by delta value (ITM / OTM / ATM) |
| **Expiration Type** | Weekly and/or Monthly |
| **Expiration Date** | Select specific expiration dates |
| **DTE** | Filter by days to expiration (greater than / less than / between) |
| **Premium** | Filter by total dollar value of the trade |
| **Trade Sentiment** | All / Bullish / Bearish / Neither |
| **Side** | Bid / Ask / Mid |
| **Size** | Trade size volume (must be >100) |
| **Flags** | Group certain trade condition codes: Block / Sweep / Regular / Cross / Floor / Non RTH |
| **Code** | Filter by specific trade session code |

---

## Historical Data & Emails

- **Historical reports** available to Premier Members back to 01/02/2024
- **End-of-Day Email**: Sent at 5:30 PM CT Mon–Fri to site members (opt-in)
- **Mid-day Email**: Noon CT, Premier Members only
