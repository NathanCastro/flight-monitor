"""
google_flights.py — Scraper do Google Flights.
"""

import logging
from datetime import datetime
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)


async def scrape(origin: str, destination: str, date: str, passengers: int = 2) -> float | None:
    import re
    
    d = datetime.strptime(date, "%Y-%m-%d")
    date_fmt = d.strftime("%Y-%m-%d")
    
    logger.info(f"[GoogleFlights] Buscando {origin}→{destination} em {date}")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=["--no-sandbox"])
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            viewport={"width": 1366, "height": 768},
        )
        page = await context.new_page()
        
        try:
            url = f"https://www.google.com/travel/flights?q=Voos+de+{origin}+para+{destination}+em+{date_fmt}&curr=BRL"
            await page.goto(url, wait_until="domcontentloaded", timeout=45_000)
            await page.wait_for_timeout(3000)
            await page.evaluate("window.scrollBy(0, 400)")
            await page.wait_for_timeout(2000)

            prices = []
            elements = await page.query_selector_all("span")
            for el in elements:
                try:
                    text = await el.inner_text()
                    if "R$" in text:
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
                    pass

            if not prices:
                logger.warning(f"[GoogleFlights] Nenhum preço encontrado para {origin}→{destination}")
                return None

            best = min(prices)
            logger.info(f"[GoogleFlights] {origin}→{destination}: R$ {best:.2f}")
            return best

        except Exception as e:
            logger.error(f"[GoogleFlights] Erro: {e}")
            return None
        finally:
            await browser.close()
