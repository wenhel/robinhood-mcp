"""FastMCP server for Robinhood portfolio research."""

import sys
import threading
import time
from typing import Literal

from dotenv import load_dotenv
from fastmcp import FastMCP

from .auth import AuthenticationError, EnvironmentVariablesError, is_logged_in, login
from .tools import (
    RobinhoodError,
    batch_enrich,
    batch_options,
    batch_screen,
    get_dividends,
    get_earnings,
    get_fundamentals,
    get_historicals,
    get_news,
    get_option_details,
    get_option_market_data,
    get_options_chain,
    get_options_expirations,
    get_options_positions,
    get_portfolio,
    get_positions,
    get_quote,
    get_ratings,
    get_watchlist,
    search_symbols,
)

# Load environment variables
load_dotenv()

# Initialize FastMCP server (older versions don't accept description kwarg).
try:
    mcp = FastMCP(
        "robinhood-mcp",
        description="Read-only research tools for Robinhood portfolio data",
    )
except TypeError:
    mcp = FastMCP("robinhood-mcp")

# Track login state
_login_attempted = False
_login_error: str | None = None
_login_lock = threading.Lock()
_cached_login_status: bool | None = None
_cached_login_status_ts = 0.0
_LOGIN_STATUS_TTL_SECONDS = 5.0


def _is_session_valid_cached() -> bool:
    """Return cached login status when fresh, otherwise probe Robinhood once."""
    global _cached_login_status, _cached_login_status_ts

    now = time.monotonic()
    if (
        _cached_login_status is not None
        and (now - _cached_login_status_ts) < _LOGIN_STATUS_TTL_SECONDS
    ):
        return _cached_login_status

    status = is_logged_in()
    _cached_login_status = status
    _cached_login_status_ts = now
    return status


def _ensure_logged_in() -> None:
    """Ensure we're logged in before API calls, re-attempting if session expired."""
    global _login_attempted, _login_error, _cached_login_status, _cached_login_status_ts

    with _login_lock:
        # Only explicit credential/config errors are treated as permanent.
        if _login_error:
            raise RobinhoodError(f"Not logged in: {_login_error}")

        session_valid = _is_session_valid_cached() if _login_attempted else False
        if not _login_attempted or not session_valid:
            _login_attempted = True
            _login_error = None
            try:
                login()
                _cached_login_status = True
                _cached_login_status_ts = time.monotonic()
                print("[robinhood-mcp] Logged in to Robinhood", file=sys.stderr)
            except EnvironmentVariablesError as e:
                _cached_login_status = False
                _cached_login_status_ts = time.monotonic()
                _login_error = str(e)
                print(f"[robinhood-mcp] Login failed: {e}", file=sys.stderr)
                raise RobinhoodError(f"Not logged in: {_login_error}") from e
            except AuthenticationError as e:
                _cached_login_status = False
                _cached_login_status_ts = time.monotonic()
                message = str(e)
                print(f"[robinhood-mcp] Login failed: {e}", file=sys.stderr)
                raise RobinhoodError(f"Not logged in: {message}") from e


@mcp.tool()
def robinhood_get_portfolio() -> dict:
    """Get current portfolio value and performance metrics.

    Returns portfolio profile with equity, extended hours equity,
    withdrawable amount, and other account details.
    """
    _ensure_logged_in()
    return get_portfolio()


@mcp.tool()
def robinhood_get_positions() -> dict:
    """Get all current stock positions with details.

    Returns a dict mapping stock symbols to position details including
    price, quantity, average buy price, equity, and percent change.
    """
    _ensure_logged_in()
    return get_positions()


@mcp.tool()
def robinhood_get_watchlist(name: str = "Default") -> list:
    """Get stocks in a watchlist.

    Args:
        name: Watchlist name (default: "Default")

    Returns list of watchlist items with instrument details.
    """
    _ensure_logged_in()
    return get_watchlist(name)


@mcp.tool()
def robinhood_get_quote(symbol: str) -> dict:
    """Get real-time quote for a stock symbol.

    Args:
        symbol: Stock ticker symbol (e.g., "AAPL", "TSLA")

    Returns quote data including last trade price, bid, ask,
    previous close, and trading status.
    """
    _ensure_logged_in()
    return get_quote(symbol)


@mcp.tool()
def robinhood_get_fundamentals(symbol: str) -> dict:
    """Get fundamental data for a stock.

    Args:
        symbol: Stock ticker symbol

    Returns fundamentals including P/E ratio, market cap,
    dividend yield, 52-week high/low, and more.
    """
    _ensure_logged_in()
    return get_fundamentals(symbol)


@mcp.tool()
def robinhood_get_historicals(
    symbol: str,
    interval: Literal["5minute", "10minute", "hour", "day", "week"] = "day",
    span: Literal["day", "week", "month", "3month", "year", "5year"] = "month",
) -> list:
    """Get historical price data for a stock.

    Args:
        symbol: Stock ticker symbol
        interval: Time interval (5minute, 10minute, hour, day, week)
        span: Time span (day, week, month, 3month, year, 5year)

    Returns list of OHLCV data points (open, high, low, close, volume).
    """
    _ensure_logged_in()
    return get_historicals(symbol, interval, span)


@mcp.tool()
def robinhood_get_news(symbol: str) -> list:
    """Get recent news articles for a stock.

    Args:
        symbol: Stock ticker symbol

    Returns list of news articles with title, URL, source,
    and publication date.
    """
    _ensure_logged_in()
    return get_news(symbol)


@mcp.tool()
def robinhood_get_earnings(symbol: str) -> list:
    """Get earnings data for a stock.

    Args:
        symbol: Stock ticker symbol

    Returns list of earnings reports with EPS, report date,
    analyst estimates, and actual vs expected.
    """
    _ensure_logged_in()
    return get_earnings(symbol)


@mcp.tool()
def robinhood_get_ratings(symbol: str) -> dict:
    """Get analyst ratings summary for a stock.

    Args:
        symbol: Stock ticker symbol

    Returns ratings summary with buy, hold, sell counts,
    and overall recommendation.
    """
    _ensure_logged_in()
    return get_ratings(symbol)


@mcp.tool()
def robinhood_get_dividends() -> list:
    """Get all dividend payments received.

    Returns list of dividend payments with amount, payable date,
    record date, and instrument details.
    """
    _ensure_logged_in()
    return get_dividends()


@mcp.tool()
def robinhood_get_options_positions() -> list:
    """Get all current options positions (read-only).

    Returns list of options positions with chain symbol, type,
    strike price, expiration, and quantity.
    """
    _ensure_logged_in()
    return get_options_positions()


@mcp.tool()
def robinhood_get_options_expirations(symbol: str) -> list:
    """Get all available option expiration dates for a ticker (sorted, nearest first).

    Args:
        symbol: Stock ticker (e.g., "META", "NVDA")

    Returns sorted list of YYYY-MM-DD expiration date strings.
    """
    _ensure_logged_in()
    return get_options_expirations(symbol)


@mcp.tool()
def robinhood_get_options_chain(
    symbol: str,
    expiration_date: str,
    option_type: str = "call",
    strike_min: float | None = None,
    strike_max: float | None = None,
) -> list:
    """Get the full option chain at a given expiration with live greeks (Robinhood real-time).

    Each contract includes strike_price, bid/ask/adjusted_mark, delta, gamma, theta, vega,
    rho, implied_volatility, open_interest, volume, break_even_price, chance_of_profit_long,
    instrument_id. Sorted by strike ascending.

    Args:
        symbol: Stock ticker
        expiration_date: 'YYYY-MM-DD' (use robinhood_get_options_expirations to find valid dates)
        option_type: 'call' or 'put' (default 'call')
        strike_min: Optional inclusive lower strike bound
        strike_max: Optional inclusive upper strike bound

    Returns sorted list of option contract dicts.
    """
    _ensure_logged_in()
    return get_options_chain(symbol, expiration_date, option_type, strike_min, strike_max)


@mcp.tool()
def robinhood_get_option_details(option_id: str) -> dict:
    """Get strike, expiration, type, and chain symbol for an option contract.

    Args:
        option_id: Option instrument UUID (from `option_id` field of an options position)

    Returns dict with chain_symbol, strike_price, expiration_date, type ('call'/'put').
    """
    _ensure_logged_in()
    return get_option_details(option_id)


@mcp.tool()
def robinhood_get_option_market_data(option_id: str) -> dict:
    """Get live bid/ask/mark, IV, greeks (delta/gamma/theta/vega), OI, volume for an option.

    Args:
        option_id: Option instrument UUID

    Returns market data dict including adjusted_mark_price, bid_price, ask_price,
    open_interest, volume, implied_volatility, delta, gamma, theta, vega.
    """
    _ensure_logged_in()
    return get_option_market_data(option_id)


@mcp.tool()
def robinhood_batch_screen(tickers: list) -> dict:
    """Fetch quotes + fundamentals for ALL tickers in exactly 2 API calls.

    Replaces N individual get_quote + get_fundamentals calls with a single
    batched request per endpoint. Use this as the first step of any market scan.

    Args:
        tickers: List of stock ticker symbols, e.g. ["AAPL", "MSFT", "NVDA"]

    Returns dict mapping each symbol to:
        price, prev_close, change_pct, high_52w, low_52w, pct_from_52w_high,
        pe_ratio (trailing), market_cap, volume, sector
    """
    _ensure_logged_in()
    return batch_screen(tickers)


@mcp.tool()
def robinhood_batch_options(
    tickers: list,
    year: int = 2027,
    strike_min: float | None = None,
    strike_max: float | None = None,
) -> dict:
    """Fetch LEAPS option chains for multiple tickers in parallel.

    Runs ThreadPoolExecutor(max_workers=5) internally — one concurrent
    Robinhood API call per ticker instead of sequential calls.

    Args:
        tickers: List of ticker symbols, typically top 3-5 candidates.
        year: Target LEAPS expiry year (default 2027; falls back to year+1).
        strike_min: Optional lower strike bound.
        strike_max: Optional upper strike bound.

    Returns dict mapping each symbol to {expiration, contracts} or {error}.
    """
    _ensure_logged_in()
    return batch_options(tickers, year, strike_min, strike_max)


@mcp.tool()
def robinhood_batch_enrich(tickers: list) -> dict:
    """Fetch news + earnings for multiple tickers in parallel.

    Runs ThreadPoolExecutor(max_workers=5) — parallel news + earnings
    fetches instead of sequential MCP calls.

    Args:
        tickers: List of ticker symbols, typically top 3-5 candidates.

    Returns dict mapping each symbol to {news: [...], earnings: [...]}.
    """
    _ensure_logged_in()
    return batch_enrich(tickers)


@mcp.tool()
def robinhood_search_symbols(query: str) -> list:
    """Search for stock symbols by company name or ticker.

    Args:
        query: Search query (company name or partial ticker)

    Returns list of matching instruments with symbol, name,
    and other details.
    """
    _ensure_logged_in()
    return search_symbols(query)


def main() -> None:
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
