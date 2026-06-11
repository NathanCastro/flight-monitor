"""
flight_agent.py — Orquestrador principal do Flight Monitor.

Executa via cron (2x/dia) ou manualmente:
  python flight_agent.py           # verificação normal
  python flight_agent.py --startup # verificação inicial (sem cooldown)
  python flight_agent.py --history # mostra histórico de preços
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

# Ajusta path para imports relativos
sys.path.insert(0, str(Path(__file__).parent))

from database import (
    init_db,
    save_price,
    get_average,
    last_alert_hours_ago,
    log_alert,
    get_history,
    count_price_records,
)
from price_analyzer import analyze, RouteResult
from notifier import send_alert
from scrapers.skyscanner import scrape as sky_scraper_scrape
from scrapers.google_flights import scrape as gf_scraper_scrape

# ── Logging ────────────────────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("flight_agent")

# ── Config ─────────────────────────────────────────────────────────────────
CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


# ── Scraping ───────────────────────────────────────────────────────────────
async def fetch_price(route: dict, passengers: int) -> tuple[float | None, str]:
    """
    Busca preço da rota no(s) scraper(s) configurado(s).
    Retorna (melhor_preco, fonte).
    """
    origin = route["origin"]
    destination = route["destination"]
    date = route["date"]
    scraper_cfg = route.get("scraper", "skyscanner")

    prices = {}

    if scraper_cfg in ("skyscanner", "both"):
        p = await sky_scraper_scrape(origin, destination, date, passengers)
        if p:
            prices["skyscanner"] = p

    if scraper_cfg in ("google_flights", "both"):
        p = await gf_scraper_scrape(origin, destination, date, passengers)
        if p:
            prices["google_flights"] = p

    if not prices:
        return None, "none"

    best_source = min(prices, key=prices.get)
    return prices[best_source], best_source


# ── Histórico ──────────────────────────────────────────────────────────────
def show_history(config: dict):
    for route in config["routes"]:
        rid = route["id"]
        label = route["label"]
        history = get_history(rid, limit=10)
        print(f"\n📊 {label} ({rid})")
        if not history:
            print("  (sem dados ainda)")
        for row in history:
            print(f"  {row['scraped_at'][:16]}  R$ {row['price']:,.2f}  [{row['source']}]")


# ── Main ───────────────────────────────────────────────────────────────────
async def run(startup: bool = False):
    config = load_config()
    passengers = config.get("passengers", 2)
    thresholds = config.get("thresholds", {})
    alert_cfg = config.get("alerts", {})

    logger.info(f"=== Flight Monitor {'(startup)' if startup else ''} ===")
    logger.info(f"Rotas: {len(config['routes'])} | Passageiros: {passengers}")

    init_db()

    # Coleta preços de todas as rotas
    route_results: list[RouteResult] = []

    for route in config["routes"]:
        rid = route["id"]
        label = route["label"]
        logger.info(f"Buscando: {label}...")

        price, source = await fetch_price(route, passengers)

        avg = get_average(rid, days=alert_cfg.get("require_below_avg_days", 7))

        if price is not None:
            save_price(rid, source, price, passengers)
            logger.info(f"  💰 R$ {price:,.2f} via {source} (média 7d: {f'R$ {avg:,.2f}' if avg else 'N/D'})")
        else:
            logger.warning(f"  ⚠️  Sem preço para {label}")

        route_results.append(RouteResult(
            route_id=rid,
            label=label,
            price=price,
            avg_7d=avg,
            source=source,
        ))

    # Verifica cooldown (bypass no startup)
    cooldown_hours = alert_cfg.get("cooldown_hours", 24)
    in_cooldown = last_alert_hours_ago(cooldown_hours)
    cooldown_ok = startup or not in_cooldown

    # Analisa e decide se alerta
    analysis = analyze(
        results=route_results,
        thresholds=thresholds,
        cooldown_ok=cooldown_ok,
        alert_on_first=alert_cfg.get("alert_on_first_collect", True),
    )

    logger.info(f"Análise: {analysis.reason}")

    if analysis.should_alert:
        logger.info("📧 Enviando alerta por e-mail...")
        sent = send_alert(analysis)
        if sent:
            log_alert(
                routes_json=json.dumps([
                    {"id": r.route_id, "price": r.price} for r in route_results
                ]),
                total_price=analysis.grand_total or 0,
            )
    else:
        logger.info("✅ Sem alerta necessário neste ciclo.")

    # Resumo final
    logger.info("=== Resumo ===")
    for r in route_results:
        status = f"R$ {r.price:,.2f}" if r.price else "INDISPONÍVEL"
        logger.info(f"  {r.label}: {status}")
    if analysis.grand_total:
        logger.info(f"  TOTAL ESTIMADO: R$ {analysis.grand_total:,.2f}")


def main():
    parser = argparse.ArgumentParser(description="Flight Monitor")
    parser.add_argument("--startup", action="store_true", help="Modo startup (ignora cooldown)")
    parser.add_argument("--history", action="store_true", help="Mostra histórico de preços")
    args = parser.parse_args()

    if args.history:
        config = load_config()
        show_history(config)
        return

    asyncio.run(run(startup=args.startup))


if __name__ == "__main__":
    main()
