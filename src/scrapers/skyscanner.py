"""
skyscanner.py — Scraper do Skyscanner para preços de passagens.
"""

import logging
from datetime import datetime
from .base import new_stealth_page, random_delay, parse_price, launch_browser

logger = logging.getLogger(__name__)

PRICE_SELECTORS = [
    '[data-testid="price-text"]',
    '[data-testid="price"]',
    '.BpkText_bpk-text--xl__MBAho',
    '[class*="Price_container"]',
    '[aria-label*="R$"]',
    '[class*="price"]',
]


def _build_url(origin: str, destination: str, date: str, passengers: int) -> str:
    """
    date: 'YYYY-MM-DD' → formata para YYMMDD
    Exemplo: GIG → LIM em 2026-11-10, 2 adultos
    """
    d = datetime.strptime(date, "%Y-%m-%d")
    date_str = d.strftime("%y%m%d")
    orig = origin.lower()
    dest = destination.lower()
    return (
        f"https://www.skyscanner.com.br/transporte/passagens-aereas/{orig}/{dest}/{date_str}/"
        f"?adults={passengers}&currency=BRL"
    )


async def scrape(origin: str, destination: str, date: str, passengers: int = 2) -> float | None:
    """
    Raspa o menor preço disponível no Skyscanner para a rota/data.
    Retorna o preço total para N passageiros, ou None em caso de falha.
    """
    url = _build_url(origin, destination, date, passengers)
    logger.info(f"[Skyscanner] Buscando {origin}→{destination} em {date}: {url}")

    pw, browser = await launch_browser()
    try:
        page = await new_stealth_page(browser)
        await page.goto(url, wait_until="domcontentloaded", timeout=45_000)
        await random_delay(3, 6)

        # Scroll suave para carregar preços lazy
        await page.evaluate("window.scrollBy(0, window.innerHeight * 0.6)")
        await random_delay(2, 4)

        prices = []

        for selector in PRICE_SELECTORS:
            try:
                elements = await page.query_selector_all(selector)
                for el in elements:
                    text = await el.inner_text()
                    price = parse_price(text)
                    if price and 50 < price < 50_000:
                        prices.append(price)
            except Exception:
                continue

        if not prices:
            logger.warning(f"[Skyscanner] Nenhum preço encontrado para {origin}→{destination}")
            return None

        best = min(prices)
        logger.info(f"[Skyscanner] {origin}→{destination}: R$ {best:.2f} ({len(prices)} opções)")
        return best

    except Exception as e:
        logger.error(f"[Skyscanner] Erro em {origin}→{destination}: {e}")
        return None
    finally:
        await browser.close()
        await pw.__aexit__(None, None, None)
