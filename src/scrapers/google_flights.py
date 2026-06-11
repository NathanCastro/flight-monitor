"""
google_flights.py — Scraper do Google Flights para preços de passagens.
"""

import logging
from datetime import datetime
from .base import new_stealth_page, random_delay, parse_price, launch_browser

logger = logging.getLogger(__name__)

PRICE_SELECTORS = [
    '[aria-label*="R$"]',
    '[aria-label*="BRL"]',
    '.YMlIz',
    '.U3gSDe',
    'span[data-gs]',
    '[class*="price"]',
]


def _build_url(origin: str, destination: str, date: str, passengers: int) -> str:
    """
    Monta URL de busca do Google Flights via query de texto.
    date: 'YYYY-MM-DD'
    """
    d = datetime.strptime(date, "%Y-%m-%d")
    date_fmt = d.strftime("%Y-%m-%d")
    query = f"Voos+de+{origin}+para+{destination}+em+{date_fmt}"
    return (
        f"https://www.google.com/travel/flights/search"
        f"?q={query}&curr=BRL&hl=pt-BR&gl=BR"
        f"&adults={passengers}"
    )


async def scrape(origin: str, destination: str, date: str, passengers: int = 2) -> float | None:
    """
    Raspa o menor preço disponível no Google Flights para a rota/data.
    Retorna o preço total para N passageiros, ou None em caso de falha.
    """
    url = _build_url(origin, destination, date, passengers)
    logger.info(f"[GoogleFlights] Buscando {origin}→{destination} em {date}")

    pw, browser = await launch_browser()
    try:
        page = await new_stealth_page(browser)
        await page.goto(url, wait_until="domcontentloaded", timeout=45_000)
        await random_delay(3, 5)

        # Scroll para carregar resultados
        await page.evaluate("window.scrollBy(0, 400)")
        await random_delay(2, 4)

        prices = []

        for selector in PRICE_SELECTORS:
            try:
                elements = await page.query_selector_all(selector)
                for el in elements:
                    text = await el.inner_text()
                    if not text:
                        label = await el.get_attribute("aria-label") or ""
                        text = label
                    price = parse_price(text)
                    if price and 50 < price < 50_000:
                        prices.append(price)
            except Exception:
                continue

        if not prices:
            logger.warning(f"[GoogleFlights] Nenhum preço encontrado para {origin}→{destination}")
            return None

        best = min(prices)
        logger.info(f"[GoogleFlights] {origin}→{destination}: R$ {best:.2f} ({len(prices)} opções)")
        return best

    except Exception as e:
        logger.error(f"[GoogleFlights] Erro em {origin}→{destination}: {e}")
        return None
    finally:
        await browser.close()
        await pw.__aexit__(None, None, None)
