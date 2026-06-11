"""
skyscanner.py — Scraper do Skyscanner.
"""

import logging
from datetime import datetime
from playwright.async_api import async_playwright

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
    from datetime import datetime
    d = datetime.strptime(date, "%Y-%m-%d")
    date_str = d.strftime("%y%m%d")
    return (
        f"https://www.skyscanner.com.br/transporte/passagens-aereas/"
        f"{origin.lower()}/{destination.lower()}/{date_str}/"
        f"?adults={passengers}&currency=BRL"
    )


async def scrape(origin: str, destination: str, date: str, passengers: int = 2) -> float | None:
    import re
    
    url = _build_url(origin, destination, date, passengers)
    logger.info(f"[Skyscanner] Buscando {origin}→{destination} em {date}: {url}")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=["--no-sandbox"])
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            viewport={"width": 1366, "height": 768},
        )
        page = await context.new_page()
        
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=45_000)
            await page.wait_for_timeout(3000)
            await page.evaluate("window.scrollBy(0, 400)")
            await page.wait_for_timeout(2000)

            prices = []
            for selector in PRICE_SELECTORS:
                try:
                    elements = await page.query_selector_all(selector)
                    for el in elements:
                        text = await el.inner_text()
                        if text:
                            cleaned = re.sub(r"[^\d.,]", "", text)
                            if "," in cleaned and "." in cleaned:
                                cleaned = cleaned.replace(".", "").replace(",", ".")
                            elif "," in cleaned:
                                cleaned = cleaned.replace(",", ".")
                            try:
                                price = float(cleaned)
                                if 50 < price < 50_000:
                                    prices.append(price)
                            except ValueError:
                                pass
                except Exception:
                    continue

            if not prices:
                logger.warning(f"[Skyscanner] Nenhum preço encontrado para {origin}→{destination}")
                return None

            best = min(prices)
            logger.info(f"[Skyscanner] {origin}→{destination}: R$ {best:.2f}")
            return best

        except Exception as e:
            logger.error(f"[Skyscanner] Erro: {e}")
            return None
        finally:
            await browser.close()
