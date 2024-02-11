import requests
import random

from dataclasses import dataclass
from typing import Optional, List, Dict
from bs4 import BeautifulSoup
from tabulate import tabulate
from dotenv import dotenv_values

from exceptions import (
    BrowserAgentFetchError,
    ExchangeRateFetchError,
    PriceInformationFetchError,
)

config = dotenv_values(".env")


@dataclass
class Stock:
    ticker: str
    exchange: str
    price: float = 0
    currency: str = "USD"
    usd_price: float = 0

    def __post_init__(self):
        price_info = get_price_information(self.ticker, self.exchange)

        if price_info["ticker"] == self.ticker:
            self.price = price_info["price"]
            self.currency = price_info["currency"]
            self.usd_price = price_info["usd_price"]


@dataclass
class Position:
    stock: Stock
    quantity: int


@dataclass
class Portfolio:
    positions: list[Position]

    def get_total_value(self):
        total_value = 0

        for position in self.positions:
            total_value += position.quantity * position.stock.usd_price

        return total_value


def get_random_browser_agent(num_results: int = 3) -> Optional[Dict[str, str]]:
    """
    Get random browser agents from an external service.

    Parameters:
    - num_results (int): Number of random browser agents to retrieve. Default is 3.

    Returns:
    - Optional[Dict[str, str]]: A dictionary representing a random browser agent,
      or None if no agents are found or an error occurs during the fetching process.
    """
    try:
        url: str = "https://headers.scrapeops.io/v1/browser-headers"
        params: Dict[str, str] = {
            "api_key": config["SCRAPE_OPS_API_KEY"],
            "num_results": str(num_results),
        }

        response = requests.get(url, params=params)
        response.raise_for_status()

        try:
            browser_agents: List[Dict[str, str]] = response.json().get("result", [])
        except ValueError as json_error:
            raise BrowserAgentFetchError(f"Error decoding JSON: {json_error}")

        if browser_agents:
            return random.choice(browser_agents)
        else:
            raise BrowserAgentFetchError("No browser agents found in the response.")
    except requests.RequestException as e:
        raise BrowserAgentFetchError(f"Error fetching browser agents: {e}")
    except BrowserAgentFetchError as fetch_error:
        raise fetch_error  # Re-raise the custom error for better handling
    except Exception as e:
        raise BrowserAgentFetchError(f"An unexpected error occurred: {e}")


def get_fx_to_usd(currency: str) -> Optional[float]:
    """
    Get the exchange rate of a given currency to USD.

    Parameters:
    - currency (str): The currency code.

    Returns:
    - Optional[float]: The exchange rate of the given currency to USD,
      or None if an error occurs during the fetching process.
    """
    try:
        fx_url: str = f"https://www.google.com/finance/quote/{currency}-USD"
        random_browser_agent: Dict[str, str] = get_random_browser_agent()

        resp = requests.get(url=fx_url, headers=random_browser_agent)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.content, "html.parser")

        fx_rate = soup.find(name="div", attrs={"data-last-price": True})
        if fx_rate is None:
            raise ExchangeRateFetchError("Unable to find exchange rate on the page.")

        fx = float(fx_rate["data-last-price"])
        return fx
    except requests.RequestException as request_error:
        raise ExchangeRateFetchError(f"Error fetching exchange rate: {request_error}")
    except (ValueError, TypeError) as conversion_error:
        raise ExchangeRateFetchError(
            f"Error converting exchange rate: {conversion_error}"
        )
    except ExchangeRateFetchError as fetch_error:
        raise fetch_error  # Re-raise the custom error for better handling
    except Exception as e:
        raise ExchangeRateFetchError(f"An unexpected error occurred: {e}")


def get_price_information(ticker: str, exchange: str) -> Optional[Dict[str, float]]:
    """
    Get price information for a given stock using its ticker and exchange.

    Parameters:
    - ticker (str): The stock ticker symbol.
    - exchange (str): The stock exchange code.

    Returns:
    - Optional[Dict[str, float]]: A dictionary containing price information,
      including the original price in the stock's currency and the equivalent
      price in USD, or None if the information is not available.
    """
    try:
        url: str = f"https://www.google.com/finance/quote/{ticker}:{exchange}"
        random_browser_agent: Dict[str, str] = get_random_browser_agent()
        resp = requests.get(url=url, headers=random_browser_agent)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.content, "html.parser")
        price_div = soup.find(name="div", attrs={"data-last-price": True})
        # print(price_div)

        if price_div is None:
            raise PriceInformationFetchError("Price information not found.")

        price: float = float(price_div["data-last-price"])
        currency: str = price_div["data-currency-code"]

        usd_price: float = price
        if currency != "USD":
            fx = get_fx_to_usd(currency=currency)
            usd_price = round(price * fx, 2)

        return {
            "ticker": ticker,
            "exchange": exchange,
            "price": price,
            "currency": currency,
            "usd_price": usd_price,
        }
    except requests.RequestException as request_error:
        raise PriceInformationFetchError(
            f"Error fetching price information: {request_error}"
        )
    except (ValueError, TypeError) as conversion_error:
        raise PriceInformationFetchError(
            f"Error converting price information: {conversion_error}"
        )
    except PriceInformationFetchError as fetch_error:
        raise fetch_error  # Re-raise the custom error for better handling
    except Exception as e:
        raise PriceInformationFetchError(f"An unexpected error occurred: {e}")


def display_portfolio_summary(portfolio):
    if not isinstance(portfolio, Portfolio):
        raise TypeError("Please provide an instance of the Portfolio type")

    portfolio_value = portfolio.get_total_value()

    position_data = []

    for position in sorted(
        portfolio.positions, key=lambda x: x.quantity * x.stock.usd_price, reverse=True
    ):
        position_data.append(
            [
                position.stock.ticker,
                position.stock.exchange,
                position.quantity,
                position.stock.usd_price,
                position.quantity * position.stock.usd_price,
                position.quantity * position.stock.usd_price / portfolio_value * 100,
            ]
        )

    print(
        tabulate(
            position_data,
            headers=[
                "Ticker",
                "Exchange",
                "Quantity",
                "Price",
                "Market Value",
                "% Allocation",
            ],
            tablefmt="psql",
            floatfmt=".2f",
        )
    )

    print(f"Total portfolio value: ${portfolio_value:,.2f}.")


if __name__ == "__main__":
    shop = Stock("SHOP", "TSE")  # CAD
    msft = Stock("MSFT", "NASDAQ")  # USD
    googl = Stock("GOOGL", "NASDAQ")
    bns = Stock("BNS", "TSE")

    positions = [
        Position(shop, 10),
        Position(msft, 2),
        Position(bns, 100),
        Position(googl, 30),
    ]

    portfolio = Portfolio(positions)

    display_portfolio_summary(portfolio)

    # Stock -> Position -> Portfolio
