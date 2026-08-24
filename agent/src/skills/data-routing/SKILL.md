---
name: data-routing
category: data-source
description: The single ROUTER for every data need. Load this skill BEFORE any backtest, data-fetch, or research task to pick the best available source/tool, honour auth (env) requirements, and avoid ban-risk providers.
---
# Data Routing (Router)

This is the one router. It maps (a) every registered backtest data **source** to its
markets / auth / skill, and (b) every research **data need** to the concrete **tool**
that serves it, its market, and the env key it requires. Source names below are a
strict subset of `backtest.loaders.registry.VALID_SOURCES` (enforced by
`tests/test_data_routing_sources_subset.py`).

## Source Overview

Every name here is a registered OHLCV/backtest source in `VALID_SOURCES`.
"Runner-internal" sources are selected by the backtest runner, not authored as a
per-source skill.

| Source | Markets | Auth (env key) | Network | Skill |
|--------|---------|----------------|---------|-------|
| yahoo | US, HK, Canada (TSX/TSXV), India (NSE/BSE) equities | No (IP-throttled) | Needs Yahoo access | data-routing |
| yfinance | US, HK, Canada (TSX/TSXV) stocks, ETFs | No | Needs Yahoo access | yfinance |
| okx | Crypto (OKX exchange) | No | Needs okx.com access | okx-market |
| binance | Crypto (Binance) | No | Needs binance.com access | data-routing |
| ccxt | Crypto (100+ exchanges) | No | Needs exchange access | ccxt |
| futu | A/HK/US via OpenD gateway | Yes (OpenD running) | Local gateway | data-routing (runner-internal) |
| mt5 | Forex & metals (your broker's MT5 feed) | Yes (running, logged-in MT5 terminal; optional `~/.vibe-trading/mt5.json`) | Local terminal (Windows) | data-routing (runner-internal) |
| tickerall | Forex & metals (same broker MT5 feed, hosted) | Yes (`TICKERALL_API_KEY` + `TICKERALL_ACCOUNT_ID`; read-only) | Hosted API (any OS, no terminal) | data-routing (runner-internal; **explicit `source=tickerall` only**) |
| local | User CSV/parquet on disk | No | Offline | data-routing (runner-internal) |
| india_broker | India NSE/BSE via broker (Shoonya/Dhan) | Yes (broker login) | Broker API | data-routing |
| pykrx | Korea KOSPI/KOSDAQ | No | Needs KRX access | data-routing |
| longbridge | US/HK via Longbridge | Yes (`LONGBRIDGE_*`) | Longbridge API | data-routing |
| stooq | US equities (daily OHLCV) | No | Unrestricted | data-routing |
| finnhub | US equities | Yes (`FINNHUB_API_KEY`) | Unrestricted | data-routing |
| alphavantage | US equities | Yes (`ALPHAVANTAGE_API_KEY`) | Unrestricted | data-routing |
| tiingo | US equities | Yes (`TIINGO_API_KEY`) | Unrestricted | data-routing |
| fmp | US equities | Yes (`FMP_API_KEY`) | Unrestricted | data-routing |
| qveris | Global multi-asset (paid, credits) | Yes (`QVERIS_API_KEY` / Settings) | QVeris API | qveris <!-- QVERIS-INTEGRATION --> |

> **China-free build:** A-share (`*.SH/*.SZ/*.BJ`), HK (`*.HK`), and related `tencent/mootdx/eastmoney/baostock/akshare/tushare/sina` sources are intentionally removed. Their symbols resolve to `_unresolved` without network (fail-closed). Use `*.NS/*.BO` (India) or `*.US` (US) via `yahoo`→`yfinance`→`india_broker`.

## Capability → Tool Routing

Pick the tool by the data need. "Market" is the universe the tool covers; "Env key"
is required only where listed (no key listed = free / no auth).

| Data need | Tool | Market | Env key |
|-----------|------|--------|---------|
| OHLCV price bars | `get_market_data` | A-share / US / HK / Canada / crypto / futures / forex | per-source (see Source Overview) |
| Fund flow (资金流向) | `get_fund_flow` | A-share, HK, US | — |
| Dragon-tiger (龙虎榜) | `get_dragon_tiger` | A-share | — |
| Northbound flow (北向资金) | `get_northbound_flow` | A-share | — |
| Margin trading (融资融券) | `get_margin_trading` | A-share | — |
| Block trades (大宗交易) | `get_block_trades` | A-share | — |
| Shareholder count (股东户数) | `get_shareholder_count` | A-share | — |
| Lockup expiry (限售解禁) | `get_lockup_expiry` | A-share | — |
| Sector / board taxonomy (板块) | `get_sector_info` | A-share | — |
| Sell-side research reports | `get_research_reports` | A-share | — |
| Stock news | `get_stock_news` | A-share, US, HK | — |
| SEC filings (EDGAR) | `get_sec_filings` | US | — |
| Financial statements | `get_financial_statements` | A-share, US, HK | — |
| Options chain | `get_options_chain` | US | — |
| Stock profile / fundamentals | `get_stock_profile` | US | — |
| Market screen | `screen_market` | A-share | — |
| Symbol search | `search_symbol` | A-share, US, HK, Canada, crypto/index/FX | — |
| Macro / FRED series | `get_macro_series` | Macro (US/global) | `FRED_API_KEY` |
| iWenCai NL search (问财) | `iwencai_search` | A-share | `VIBE_TRADING_IWENCAI_KEY` |

Notes:
- `get_financial_statements` reads US statements from SEC EDGAR companyfacts
  (ticker -> CIK -> XBRL concepts) and A-share/HK statements from the Eastmoney
  datacenter report API (per-market F10 report names).
- `get_stock_news` routes A-share (SH/SZ/BJ) to an Eastmoney news client and
  US (.US) / HK (.HK) to a Yahoo search client; a failure on one upstream is
  returned as an error envelope, never raised, so a single bad symbol never
  aborts a batch.

## Decision Tree

### Backtest scenario (writing config.json)

Use `source: "auto"` — the runner routes by symbol pattern and falls back across
same-market sources automatically. Only set a concrete source when the user asks.

### Analysis / research scenario

1. Identify the data need, then read the Capability table for the tool + env key.
2. If the need is plain OHLCV, call `get_market_data` and let source fallback run.
3. Set any required env key before calling a key-gated tool; if it is missing,
   report the missing key rather than failing silently.

### Source priority (for OHLCV by market)

- **A-shares**: China-free — no source. Symbols `*.SH/*.SZ/*.BJ` resolve to `_unresolved` (fail-closed, no network). Use India `*.NS/*.BO` or US `*.US`.
- **US stocks**: `yahoo` only (single source; if `yahoo` misses → `_unresolved`). Previous `stooq/sina/eastmoney/yfinance/tiingo/fmp` fallbacks removed for China-free.
- **HK stocks**: China-free — no source. Symbols `*.HK` resolve to `_unresolved`. Use `*.US` or `*.NS`.
- **India (NSE/BSE)**: `yahoo` → `yfinance` → `india_broker` → `local` (SLO: all three miss → `_unresolved`).
- **Korea (KRX)**: `pykrx` → `yahoo` → `yfinance` → `local`.
- **Canada (TSX/TSXV)**: `yahoo` → `yfinance` → `local`; use Yahoo's canonical `.TO`/`.V` suffixes (e.g. `TD.TO`, `PNG.V`).
- **Vietnam (HOSE)**: `yahoo` → `yfinance` → `local`.
- **Crypto**: `okx` → `binance` → `ccxt` → `yfinance` → `local`.
- **Futures / fund / macro**: China-free — no source, `_unresolved`.
- **Forex / metals**: `mt5` (local MetaTrader 5 terminal, Windows) → `yfinance` → `local`. TickerAll (`source="tickerall"`) is a hosted, no-terminal alternative to the *same* broker feed (any OS) — opt-in and **explicit-only**: it never joins this automatic chain, so a user's broker credential is used only when deliberately requested.

## Symbol Format Reference

| Market | Format | Examples |
|--------|--------|----------|
| A-shares | `NNNNNN.SZ/SH/BJ` | 000001.SZ, 600000.SH, 430139.BJ |
| US stocks | `TICKER.US` | AAPL.US, MSFT.US |
| HK stocks | `NNNNN.HK` | 00700.HK, 09988.HK |
| Canada TSX / TSXV | `TICKER.TO` / `TICKER.V` | TD.TO, BBD-B.TO, PNG.V |
| Crypto | `SYMBOL-USDT` | BTC-USDT, ETH-USDT |
| Futures | `XXNNNN.EXCHANGE` | CU2406.SHFE |
| Forex | `XXX/YYY` | USD/CNY, EUR/USD |

## Ban-Risk & Fallback Notes

- **China-free:** `tencent/mootdx/eastmoney/baostock/akshare/tushare/sina` are absent — any request naming them or using `*.SH/*.HK` returns `_unresolved` without hitting `web.ifzq.gtimg.cn`.
- **Yahoo throttles by IP** — per-host wrapper, same fallback rule. US equities now have single source `yahoo`; if Yahoo throttles, result is `_unresolved` (no silent fallback).
- **Key-gated sources need their env key** (`FINNHUB_API_KEY`, `ALPHAVANTAGE_API_KEY`, `TIINGO_API_KEY`, `FMP_API_KEY`, `FRED_API_KEY`). If the key is absent the loader is unavailable — route to a free same-market source instead of erroring out (`TUSHARE_TOKEN`/`VIBE_TRADING_IWENCAI_KEY` are China-free no-ops).
- A single failing symbol or transient HTTP error is reported inside the envelope; it never aborts the surrounding batch.

## Data Verification Discipline

When a number will drive a conclusion (valuation, screening, report), do not trust a
single source. Cross-check it:

- **Verify material figures across ≥2 independent sources** before citing them.
  Prioritize original disclosures (company annual/quarterly reports, exchange filings)
  over third-party aggregators.
- **Flag any deviation >1%** between sources as a ⚠️ caliber mismatch — usually a
  definition difference (GAAP vs Non-GAAP, consolidated vs parent-only, currency,
  TTM vs annual). Do not silently pick one; state both and which you adopt.
- **Use the `financial_rigor` tool's `cross_validate` command** to do this exactly:
  pass `{source: value, ...}` and it returns the median consensus + per-source
  deviation + an `all_consistent` flag at a configurable tolerance (default 2%).
- **Mark unverified numbers** as "single-source" or "estimate" — never present an
  uncorroborated figure as established fact.

This discipline is what separates analysis from aggregation.

## Testing Chart Providers (China-free)

When the user says "test all the chart providers connected to this app":

1. Enumerate active providers: `from backtest.loaders.registry import VALID_SOURCES, FALLBACK_CHAINS` — expect 18 (`yahoo`, `yfinance`, `india_broker`, `pykrx`, `okx`, `binance`, `ccxt`, `stooq`, `futu`, `mt5`, `tickerall`, `local`, `qveris`, `longbridge`, `finnhub`, `alphavantage`, `tiingo`, `fmp` plus `auto`).
2. Probe one symbol per market via `get_market_data` with `source="auto"` and `include_provenance=True`:
   - US: `AAPL.US` → expect `yahoo` (`_provenance.source=="yahoo"`)
   - India: `RELIANCE.NS` → `yahoo`→`yfinance`→`india_broker` chain
   - Korea: `005930.KS` → `pykrx`→`yahoo`
   - Canada: `TD.TO` → `yahoo`→`yfinance`
   - Crypto: `BTC-USDT` → `okx`→`binance`→`ccxt`
   - Forex: `EUR/USD` → `mt5`→`yfinance`
3. For China symbols (`600519.SH`, `00700.HK`) expect `{"_unresolved":["600519.SH"]}` without network to `web.ifzq.gtimg.cn` — report as **China-free fail-closed**, not error.
4. Report table: provider | market | sample symbol | source | rows | volume_unit | status. Use capped rows and provenance.

Example success envelope: `{"RELIANCE.NS":[...], "_provenance":{"RELIANCE.NS":{"source":"yahoo","fallback_used":false}}, "_unresolved":["600519.SH"]}` is correct.
