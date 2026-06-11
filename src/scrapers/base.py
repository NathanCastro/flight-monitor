"""
base.py — Configuração compartilhada do browser Playwright com anti-detecção.
"""

import os
import random
import asyncio
import logging
import re
from playwright.async_api import async_playwright, Browser, Page

logger = logging.getLogger(__name__)

HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]


async def new_stealth_page(browser: Browser) -> Page:
    """Cria uma nova página com configurações anti-detecção."""
    context = await browser.new_context(
        user_agent=random.choice(USER_AGENTS),
        viewport={"width": 1366, "height": 768},
        locale="pt-BR",
        timezone_id="America/Sao_Paulo",
        extra_http_headers={
            "accept-language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )

    page = await context.new_page()

    # Remove sinais de webdriver
    await page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
        Object.defineProperty(navigator, 'languages', { get: () => ['pt-BR', 'pt', 'en'] });
        window.chrome = { runtime: {} };
    """)

    return page


async def random_delay(min_s: float = 1.5, max_s: float = 4.0):
    await asyncio.sleep(random.uniform(min_s, max_s))


def parse_price(text: str) -> float | None:
    """Converte 'R$ 1.234,56' → 1234.56"""
    if not text:
        return None
    # Remove tudo que não é dígito, vírgula ou ponto
    cleaned = re.sub(r"[^\d.,]", "", text.strip())
    # Formato brasileiro: 1.234,56
    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")
    try:
        val = float(cleaned)
        return val if val > 10 else None  # filtra lixo
    except ValueError:
        return None


async def launch_browser():
    pw = await async_playwright().__aenter__()
    browser = await pw.chromium.launch(
        headless=HEADLESS,
        args=[
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-blink-features=AutomationControlled",
        ],
    )
    return pw, browser
