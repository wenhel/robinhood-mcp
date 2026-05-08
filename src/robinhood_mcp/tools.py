"""Read-only Robinhood tools wrapping robin_stocks library."""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Literal

import robin_stocks.robinhood as rh


class RobinhoodError(Exception):
    """Error from Robinhood API call."""

    pass


def _safe_call(func: Callable[..., Any], *args, **kwargs) -> Any:
    """Safely call a robin_stocks function with error handling.

    Args:
        func: The robin_stocks function to call.
        *args: Positional arguments.
        **kwargs: Keyword arguments.

    Returns:
        The function result.

    Raises:
        RobinhoodError: If the call fails.
    """
    try:
        result = func(*args, **kwargs)
        if result is None:
            raise RobinhoodError("API returned None - you may need to login first")
        return result
    except RobinhoodError:
        raise
    except Exception as e:
        raise RobinhoodError(f"API call failed: {e}") from e


def get_portfolio() -> dict[str, Any]:
    """Get current portfolio value and performance metrics.

    Returns:
        Portfolio profile with equity, extended hours equity, market value, etc.
    """
    return _safe_call(rh.profiles.load_portfolio_profile)


def get_positions() -> dict[str, dict[str, Any]]:
    """Get all current stock positions with details.

    Returns:
        Dict mapping symbol to position details including:
        - price, quantity, average_buy_price
        - equity, percent_change, equity_change
    """
    return _safe_call(rh.account.build_holdings)


def get_watchlist(name: str = "Default") -> list[dict[str, Any]]:
    """Get stocks in a watchlist.

    Args:
        name: Watchlist name (default: "Default").

    Returns:
        List of watchlist items with instrument details.
    """
    result = _safe_call(rh.account.get_watchlist_by_name, name=name)
    return result if isinstance(result, list) else []


def get_quote(symbol: str) -> dict[str, Any]:
    """Get real-time quote for a stock symbol.

    Args:
        symbol: Stock ticker symbol (e.g., "AAPL").

    Returns:
        Quote data including last_trade_price, bid, ask, etc.
    """
    if not symbol or not isinstance(symbol, str):
        raise RobinhoodError("Symbol must be a non-empty string")

    symbol = symbol.upper().strip()
    result = _safe_call(rh.stocks.get_quotes, symbol)

    if isinstance(result, list) and len(result) > 0:
        return result[0]
    raise RobinhoodError(f"No quote found for symbol: {symbol}")


def get_fundamentals(symbol: str) -> dict[str, Any]:
    """Get fundamental data for a stock.

    Args:
        symbol: Stock ticker symbol.

    Returns:
        Fundamentals including pe_ratio, market_cap, dividend_yield, etc.
    """
    if not symbol or not isinstance(symbol, str):
        raise RobinhoodError("Symbol must be a non-empty string")

    symbol = symbol.upper().strip()
    result = _safe_call(rh.stocks.get_fundamentals, symbol)

    if isinstance(result, list) and len(result) > 0:
        return result[0]
    raise RobinhoodError(f"No fundamentals found for symbol: {symbol}")


def get_historicals(
    symbol: str,
    interval: Literal["5minute", "10minute", "hour", "day", "week"] = "day",
    span: Literal["day", "week", "month", "3month", "year", "5year"] = "month",
) -> list[dict[str, Any]]:
    """Get historical price data for a stock.

    Args:
        symbol: Stock ticker symbol.
        interval: Time interval (5minute, 10minute, hour, day, week).
        span: Time span (day, week, month, 3month, year, 5year).

    Returns:
        List of historical data points with open, close, high, low, volume.
    """
    if not symbol or not isinstance(symbol, str):
        raise RobinhoodError("Symbol must be a non-empty string")

    symbol = symbol.upper().strip()

    valid_intervals = {"5minute", "10minute", "hour", "day", "week"}
    valid_spans = {"day", "week", "month", "3month", "year", "5year"}

    if interval not in valid_intervals:
        raise RobinhoodError(f"Invalid interval. Must be one of: {valid_intervals}")
    if span not in valid_spans:
        raise RobinhoodError(f"Invalid span. Must be one of: {valid_spans}")

    result = _safe_call(rh.stocks.get_stock_historicals, symbol, interval=interval, span=span)
    return result if isinstance(result, list) else []


def get_news(symbol: str) -> list[dict[str, Any]]:
    """Get recent news articles for a stock.

    Args:
        symbol: Stock ticker symbol.

    Returns:
        List of news articles with title, url, source, published_at, etc.
    """
    if not symbol or not isinstance(symbol, str):
        raise RobinhoodError("Symbol must be a non-empty string")

    symbol = symbol.upper().strip()
    result = _safe_call(rh.stocks.get_news, symbol)
    return result if isinstance(result, list) else []


def get_earnings(symbol: str) -> list[dict[str, Any]]:
    """Get earnings data for a stock.

    Args:
        symbol: Stock ticker symbol.

    Returns:
        List of earnings reports with eps, report date, estimates, etc.
    """
    if not symbol or not isinstance(symbol, str):
        raise RobinhoodError("Symbol must be a non-empty string")

    symbol = symbol.upper().strip()
    result = _safe_call(rh.stocks.get_earnings, symbol)
    return result if isinstance(result, list) else []


def get_ratings(symbol: str) -> dict[str, Any]:
    """Get analyst ratings summary for a stock.

    Args:
        symbol: Stock ticker symbol.

    Returns:
        Ratings summary with buy, hold, sell counts and summary.
    """
    if not symbol or not isinstance(symbol, str):
        raise RobinhoodError("Symbol must be a non-empty string")

    symbol = symbol.upper().strip()
    result = _safe_call(rh.stocks.get_ratings, symbol)

    if isinstance(result, dict):
        return result
    raise RobinhoodError(f"No ratings found for symbol: {symbol}")


def get_dividends() -> list[dict[str, Any]]:
    """Get all dividend payments received.

    Returns:
        List of dividend payments with amount, payable_date, record_date, etc.
    """
    result = _safe_call(rh.account.get_dividends)
    return result if isinstance(result, list) else []


def get_options_positions() -> list[dict[str, Any]]:
    """Get all current options positions, enriched with strike/type/mark/greeks.

    Returns:
        List of options positions. Each entry includes the raw position fields plus
        strike_price, option_type, adjusted_mark_price, bid_price, ask_price,
        open_interest, volume, implied_volatility, delta, gamma, theta, vega.
    """
    result = _safe_call(rh.options.get_open_option_positions)
    if not isinstance(result, list):
        return []

    for pos in result:
        oid = pos.get("option_id") or pos.get("option", "").rstrip("/").rsplit("/", 1)[-1]
        if not oid:
            continue
        try:
            inst = rh.options.get_option_instrument_data_by_id(oid) or {}
            pos["strike_price"] = inst.get("strike_price")
            pos["option_type"] = inst.get("type")
        except Exception:
            pass
        try:
            mkt = rh.options.get_option_market_data_by_id(oid)
            if isinstance(mkt, list):
                mkt = mkt[0] if mkt else {}
            mkt = mkt or {}
            for k in (
                "adjusted_mark_price", "bid_price", "ask_price",
                "open_interest", "volume", "implied_volatility",
                "delta", "gamma", "theta", "vega",
            ):
                if k in mkt:
                    pos[k] = mkt[k]
        except Exception:
            pass
    return result


def get_options_expirations(symbol: str) -> list[str]:
    """Get all available option expiration dates for a ticker.

    Args:
        symbol: Stock ticker (e.g., "META", "NVDA").

    Returns:
        Sorted list of expiration dates (YYYY-MM-DD), nearest first.
    """
    if not symbol or not isinstance(symbol, str):
        raise RobinhoodError("symbol must be a non-empty string")
    chain = _safe_call(rh.options.get_chains, symbol.upper()) or {}
    exps = chain.get("expiration_dates", [])
    return sorted(exps) if isinstance(exps, list) else []


def get_options_chain(
    symbol: str,
    expiration_date: str,
    option_type: str = "call",
    strike_min: float | None = None,
    strike_max: float | None = None,
) -> list[dict[str, Any]]:
    """Get the full option chain for a ticker at a given expiration, with live greeks.

    Each contract includes: strike_price, bid_price, ask_price, adjusted_mark_price,
    delta, gamma, theta, vega, rho, implied_volatility, open_interest, volume,
    break_even_price, chance_of_profit_long, bid_size, ask_size, instrument_id.

    Args:
        symbol: Stock ticker.
        expiration_date: 'YYYY-MM-DD' (must match an available expiration).
        option_type: 'call' or 'put' (default 'call').
        strike_min: Optional inclusive lower bound on strike.
        strike_max: Optional inclusive upper bound on strike.

    Returns:
        List of option contract dicts sorted by strike ascending.
    """
    if not symbol or not isinstance(symbol, str):
        raise RobinhoodError("symbol must be a non-empty string")
    if option_type not in ("call", "put"):
        raise RobinhoodError("option_type must be 'call' or 'put'")
    if not expiration_date:
        raise RobinhoodError("expiration_date required (YYYY-MM-DD)")

    result = _safe_call(
        rh.options.find_options_by_expiration,
        symbol.upper(),
        expiration_date,
        option_type,
    )
    if not isinstance(result, list):
        return []

    rows = []
    for c in result:
        try:
            sp = float(c.get("strike_price", 0))
        except (TypeError, ValueError):
            continue
        if strike_min is not None and sp < strike_min:
            continue
        if strike_max is not None and sp > strike_max:
            continue
        rows.append(c)
    rows.sort(key=lambda c: float(c.get("strike_price", 0)))
    return rows


def get_option_details(option_id: str) -> dict[str, Any]:
    """Get an option contract's strike, expiration, type, and chain symbol.

    Args:
        option_id: The option instrument UUID (from option_id field of an options position).

    Returns:
        Dict with chain_symbol, strike_price, expiration_date, type ('call'/'put'), state.
    """
    if not option_id or not isinstance(option_id, str):
        raise RobinhoodError("option_id must be a non-empty string")
    return _safe_call(rh.options.get_option_instrument_data_by_id, option_id) or {}


def get_option_market_data(option_id: str) -> dict[str, Any]:
    """Get live market data for an option contract: bid/ask, mark, IV, greeks, OI.

    Args:
        option_id: The option instrument UUID.

    Returns:
        Dict with adjusted_mark_price, bid_price, ask_price, open_interest, volume,
        implied_volatility, delta, gamma, theta, vega, rho, chance_of_profit_*.
    """
    if not option_id or not isinstance(option_id, str):
        raise RobinhoodError("option_id must be a non-empty string")
    result = _safe_call(rh.options.get_option_market_data_by_id, option_id)
    if isinstance(result, list):
        return result[0] if result else {}
    return result or {}


def _to_float(val: Any) -> float | None:
    try:
        v = float(val)
        return v if v != 0.0 else None
    except (TypeError, ValueError):
        return None


def batch_screen(tickers: list[str]) -> dict[str, dict[str, Any]]:
    """Fetch quotes + fundamentals for all tickers in exactly 2 API calls.

    Args:
        tickers: List of stock ticker symbols.

    Returns:
        Dict mapping symbol to {price, prev_close, change_pct, high_52w, low_52w,
        pct_from_52w_high, pe_ratio, market_cap, volume, sector}.
        pe_ratio is Robinhood trailing PE (not forward PE).
    """
    if not tickers:
        return {}

    symbols = [t.upper().strip() for t in tickers if t.strip()]
    quotes_raw = _safe_call(rh.stocks.get_quotes, symbols) or []
    fundas_raw = _safe_call(rh.stocks.get_fundamentals, symbols) or []

    quotes = {q["symbol"]: q for q in quotes_raw if q and q.get("symbol")}
    fundas = {f["symbol"]: f for f in fundas_raw if f and f.get("symbol")}

    result: dict[str, dict[str, Any]] = {}
    for t in symbols:
        q = quotes.get(t, {})
        f = fundas.get(t, {})

        price = _to_float(q.get("last_trade_price"))
        prev = _to_float(q.get("adjusted_previous_close") or q.get("previous_close"))
        change_pct = round((price - prev) / prev * 100, 2) if price and prev else None

        high_52w = _to_float(f.get("high_52_weeks"))
        pct_from_high = (
            round((price - high_52w) / high_52w * 100, 2)
            if price and high_52w
            else None
        )

        result[t] = {
            "price": price,
            "prev_close": prev,
            "change_pct": change_pct,
            "high_52w": high_52w,
            "low_52w": _to_float(f.get("low_52_weeks")),
            "pct_from_52w_high": pct_from_high,
            "pe_ratio": _to_float(f.get("pe_ratio")),
            "market_cap": f.get("market_cap"),
            "volume": f.get("volume"),
            "sector": f.get("sector"),
        }

    return result


def _fetch_options_one(
    ticker: str,
    year: int,
    strike_min: float | None,
    strike_max: float | None,
) -> dict[str, Any]:
    try:
        chain = rh.options.get_chains(ticker) or {}
        exps = sorted(chain.get("expiration_dates", []))

        leaps_exp = next((e for e in exps if e.startswith(str(year))), None)
        if not leaps_exp:
            leaps_exp = next((e for e in exps if e.startswith(str(year + 1))), None)
        if not leaps_exp:
            return {"ticker": ticker, "error": f"No LEAPS expiry for {year}/{year + 1}", "available_expirations": exps[:12]}

        contracts = rh.options.find_options_by_expiration(ticker, leaps_exp, "call") or []

        if strike_min is not None or strike_max is not None:
            contracts = [
                c for c in contracts
                if (_to_float(c.get("strike_price")) or 0) >= (strike_min or 0)
                and (strike_max is None or (_to_float(c.get("strike_price")) or 0) <= strike_max)
            ]

        return {"ticker": ticker, "expiration": leaps_exp, "available_expirations": exps, "contracts": contracts}
    except Exception as e:
        return {"ticker": ticker, "error": str(e)}


def batch_options(
    tickers: list[str],
    year: int = 2027,
    strike_min: float | None = None,
    strike_max: float | None = None,
) -> dict[str, Any]:
    """Fetch LEAPS option chains for multiple tickers in parallel (ThreadPoolExecutor).

    Args:
        tickers: List of stock ticker symbols (typically top 5 candidates).
        year: Target LEAPS expiry year (default 2027; falls back to year+1 if unavailable).
        strike_min: Optional lower bound on strike price.
        strike_max: Optional upper bound on strike price.

    Returns:
        Dict mapping symbol to {expiration, available_expirations, contracts} or {error}.
    """
    if not tickers:
        return {}

    symbols = [t.upper().strip() for t in tickers if t.strip()]
    results: dict[str, Any] = {}
    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = {
            ex.submit(_fetch_options_one, t, year, strike_min, strike_max): t
            for t in symbols
        }
        for fut in as_completed(futures):
            data = fut.result()
            results[data["ticker"]] = data

    return results


def _fetch_enrich_one(ticker: str) -> dict[str, Any]:
    try:
        news = rh.stocks.get_news(ticker) or []
        earnings = rh.stocks.get_earnings(ticker) or []
        return {"ticker": ticker, "news": news[:5], "earnings": earnings[:4]}
    except Exception as e:
        return {"ticker": ticker, "error": str(e)}


def batch_enrich(tickers: list[str]) -> dict[str, Any]:
    """Fetch news + earnings for multiple tickers in parallel.

    Args:
        tickers: List of stock ticker symbols (typically top 5 candidates).

    Returns:
        Dict mapping symbol to {news: [...], earnings: [...]}.
    """
    if not tickers:
        return {}

    symbols = [t.upper().strip() for t in tickers if t.strip()]
    results: dict[str, Any] = {}
    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = {ex.submit(_fetch_enrich_one, t): t for t in symbols}
        for fut in as_completed(futures):
            data = fut.result()
            results[data["ticker"]] = data

    return results


def search_symbols(query: str) -> list[dict[str, Any]]:
    """Search for stock symbols by company name or ticker.

    Args:
        query: Search query (company name or partial ticker).

    Returns:
        List of matching instruments with symbol, name, etc.
    """
    if not query or not isinstance(query, str):
        raise RobinhoodError("Query must be a non-empty string")

    query = query.strip()

    # Try to get instruments by the query
    try:
        result = rh.stocks.get_instruments_by_symbols(query.upper())
        if result and isinstance(result, list):
            return result
    except Exception:
        pass

    # If exact match fails, try search
    try:
        result = rh.stocks.find_instrument_data(query)
        return result if isinstance(result, list) else []
    except Exception as e:
        raise RobinhoodError(f"Search failed: {e}") from e
