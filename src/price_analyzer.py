"""
price_analyzer.py — Analisa preços coletados e decide se deve disparar alerta.
"""

import logging
from dataclasses import dataclass
from database import get_average, count_price_records

logger = logging.getLogger(__name__)


@dataclass
class RouteResult:
    route_id: str
    label: str
    price: float | None          # melhor preço atual (total, N passageiros)
    avg_7d: float | None         # média 7 dias
    source: str                  # skyscanner | google_flights | both


@dataclass
class AnalysisResult:
    should_alert: bool
    reason: str
    routes: list[RouteResult]
    international_total: float | None  # GIG→LIM + CUZ→GIG
    lima_cusco: float | None           # LIM→CUZ
    grand_total: float | None          # tudo


def analyze(
    results: list[RouteResult],
    thresholds: dict,
    cooldown_ok: bool,
    alert_on_first: bool = True,
) -> AnalysisResult:
    """
    Decide se deve enviar alerta com base nos preços coletados e nas metas.
    """
    prices = {r.route_id: r.price for r in results}

    gig_lim = prices.get("gig_lim")
    lim_cuz = prices.get("lim_cuz")
    cuz_gig = prices.get("cuz_gig")

    # Calcula totais
    intl_total = None
    if gig_lim is not None and cuz_gig is not None:
        intl_total = gig_lim + cuz_gig

    grand = None
    if intl_total is not None and lim_cuz is not None:
        grand = intl_total + lim_cuz

    result = AnalysisResult(
        should_alert=False,
        reason="",
        routes=results,
        international_total=intl_total,
        lima_cusco=lim_cuz,
        grand_total=grand,
    )

    # Verifica cooldown
    if not cooldown_ok:
        result.reason = "Cooldown ativo — alerta já enviado recentemente."
        logger.info(result.reason)
        return result

    # Verifica se temos preços suficientes
    if gig_lim is None or cuz_gig is None:
        result.reason = "Preços internacionais indisponíveis."
        logger.warning(result.reason)
        return result

    # Verifica metas
    intl_ok = intl_total is not None and intl_total <= thresholds.get("international_total", 4000)
    lc_ok = lim_cuz is not None and lim_cuz <= thresholds.get("lima_cusco_both", 700)
    grand_ok = grand is not None and grand <= thresholds.get("grand_total", 4700)

    # Lógica principal: alerta se trechos internacionais OK OU grand total OK
    triggered = intl_ok or grand_ok

    # Também verifica se preço está abaixo da média histórica
    below_avg = _check_below_avg(results)

    has_history = all(count_price_records(r.route_id) > 1 for r in results)

    if triggered:
        if has_history and not below_avg and not alert_on_first:
            result.reason = "Meta atingida, mas preço não está abaixo da média histórica."
            return result

        msgs = []
        if intl_ok:
            msgs.append(f"Internacionais R$ {intl_total:.0f} (meta ≤ R$ {thresholds['international_total']})")
        if lc_ok:
            msgs.append(f"Lima→Cusco R$ {lim_cuz:.0f} (meta ≤ R$ {thresholds['lima_cusco_both']})")
        if grand_ok:
            msgs.append(f"Grand total R$ {grand:.0f} (meta ≤ R$ {thresholds['grand_total']})")

        result.should_alert = True
        result.reason = " | ".join(msgs)
        logger.info(f"🚨 ALERTA disparado: {result.reason}")
    else:
        parts = []
        if intl_total:
            parts.append(f"Internacionais R$ {intl_total:.0f} (meta R$ {thresholds['international_total']})")
        if lim_cuz:
            parts.append(f"Lima→Cusco R$ {lim_cuz:.0f} (meta R$ {thresholds['lima_cusco_both']})")
        result.reason = "Metas não atingidas. " + " | ".join(parts)
        logger.info(result.reason)

    return result


def _check_below_avg(results: list[RouteResult]) -> bool:
    """Retorna True se pelo menos um preço está abaixo da média histórica."""
    for r in results:
        if r.price is not None and r.avg_7d is not None:
            if r.price < r.avg_7d * 0.98:  # 2% de margem
                return True
    return False
