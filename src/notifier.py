"""
notifier.py — Envia e-mail de alerta de preço via SMTP.
"""

import os
import smtplib
import logging
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


def _fmt(value: float | None, default: str = "N/D") -> str:
    if value is None:
        return default
    return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def build_email_html(analysis) -> str:
    routes = {r.route_id: r for r in analysis.routes}

    gig_lim = routes.get("gig_lim")
    lim_cuz = routes.get("lim_cuz")
    cuz_gig = routes.get("cuz_gig")

    p_gig_lim = _fmt(gig_lim.price if gig_lim else None)
    p_lim_cuz = _fmt(lim_cuz.price if lim_cuz else None)
    p_cuz_gig = _fmt(cuz_gig.price if cuz_gig else None)

    avg_gig_lim = _fmt(gig_lim.avg_7d if gig_lim else None)
    avg_lim_cuz = _fmt(lim_cuz.avg_7d if lim_cuz else None)
    avg_cuz_gig = _fmt(cuz_gig.avg_7d if cuz_gig else None)

    grand = analysis.grand_total
    grand_fmt = _fmt(grand)
    savings = _fmt((4700 - grand) if grand else None)
    timestamp = datetime.now().strftime("%d/%m/%Y às %H:%M")

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <style>
    body {{ font-family: Arial, sans-serif; background: #f4f4f4; margin: 0; padding: 20px; }}
    .card {{ background: white; border-radius: 12px; padding: 24px; max-width: 600px; margin: 0 auto; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
    .header {{ background: #1a56db; color: white; border-radius: 8px; padding: 16px; text-align: center; margin-bottom: 20px; }}
    .alert-badge {{ background: #d1fae5; color: #065f46; padding: 4px 12px; border-radius: 20px; font-size: 13px; font-weight: bold; display: inline-block; margin-bottom: 8px; }}
    .route {{ border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; margin-bottom: 12px; }}
    .route-name {{ font-weight: bold; color: #1f2937; font-size: 16px; }}
    .price-now {{ font-size: 28px; font-weight: bold; color: #059669; }}
    .price-old {{ color: #9ca3af; font-size: 14px; margin-top: 2px; }}
    .total-box {{ background: #eff6ff; border: 2px solid #1a56db; border-radius: 8px; padding: 16px; text-align: center; margin-top: 16px; }}
    .total-value {{ font-size: 32px; font-weight: bold; color: #1a56db; }}
    .cta {{ display: block; background: #1a56db; color: white; text-align: center; padding: 14px; border-radius: 8px; text-decoration: none; font-weight: bold; margin-top: 20px; }}
    .footer {{ text-align: center; color: #9ca3af; font-size: 12px; margin-top: 16px; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="header">
      <div class="alert-badge">✈️ ALERTA DE PREÇO</div>
      <h1 style="margin:8px 0 0;font-size:20px;">Passagens abaixo da sua meta!</h1>
    </div>

    <div class="route">
      <div class="route-name">✈ Rio de Janeiro → Lima</div>
      <div style="font-size:13px;color:#6b7280;">10 de Novembro de 2026 · 2 adultos</div>
      <div class="price-now">R$ {p_gig_lim}</div>
      <div class="price-old">Média 7 dias: R$ {avg_gig_lim}</div>
    </div>

    <div class="route">
      <div class="route-name">✈ Lima → Cusco</div>
      <div style="font-size:13px;color:#6b7280;">15 de Novembro de 2026 · 2 adultos</div>
      <div class="price-now">R$ {p_lim_cuz}</div>
      <div class="price-old">Média 7 dias: R$ {avg_lim_cuz}</div>
    </div>

    <div class="route">
      <div class="route-name">✈ Cusco → Rio de Janeiro</div>
      <div style="font-size:13px;color:#6b7280;">20 de Novembro de 2026 · 2 adultos</div>
      <div class="price-now">R$ {p_cuz_gig}</div>
      <div class="price-old">Média 7 dias: R$ {avg_cuz_gig}</div>
    </div>

    <div class="total-box">
      <div style="color:#1e40af;font-size:14px;">TOTAL ESTIMADO (2 pessoas)</div>
      <div class="total-value">R$ {grand_fmt}</div>
      <div style="font-size:13px;color:#1e40af;margin-top:4px;">
        Meta: R$ 4.700 · Economizando: R$ {savings}
      </div>
    </div>

    <a href="https://www.skyscanner.com.br" class="cta">🔍 Ver passagens agora</a>
    <a href="https://www.google.com/travel/flights" class="cta" style="background:#34a853;margin-top:8px;">🔍 Buscar no Google Flights</a>

    <div class="footer">
      Monitorado em {timestamp} · Flight Monitor Bot<br>
      <small>Para parar os alertas, execute: docker compose down</small>
    </div>
  </div>
</body>
</html>"""


def send_alert(analysis) -> bool:
    """Envia o e-mail de alerta. Retorna True se enviado com sucesso."""
    smtp_host = os.environ["SMTP_HOST"]
    smtp_port = int(os.environ["SMTP_PORT"])
    smtp_user = os.environ["SMTP_USER"]
    smtp_pass = os.environ["SMTP_PASS"]
    alert_email = os.environ["ALERT_EMAIL"]

    grand = analysis.grand_total
    subject = f"✈️ ALERTA: Passagens RIO→PERU por R$ {_fmt(grand)} (meta: R$ 4.700)"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp_user
    msg["To"] = alert_email

    html = build_email_html(analysis)
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, [alert_email], msg.as_string())
        logger.info(f"✅ E-mail de alerta enviado para {alert_email}")
        return True
    except Exception as e:
        logger.error(f"❌ Falha ao enviar e-mail: {e}")
        return False
