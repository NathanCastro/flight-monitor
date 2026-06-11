"""
database.py — Gerencia o histórico de preços e alertas enviados.
"""

import sqlite3
import argparse
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path("/app/data/flights.db")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Cria as tabelas se não existirem."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS price_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                route_id    TEXT NOT NULL,
                source      TEXT NOT NULL,
                price       REAL NOT NULL,
                passengers  INTEGER NOT NULL DEFAULT 2,
                scraped_at  TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_route_scraped
                ON price_history(route_id, scraped_at);

            CREATE TABLE IF NOT EXISTS alert_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                routes_json TEXT NOT NULL,
                total_price REAL NOT NULL,
                sent_at     TEXT NOT NULL
            );
        """)
    print("✅ Banco inicializado:", DB_PATH)


def save_price(route_id: str, source: str, price: float, passengers: int = 2):
    """Persiste um preço coletado."""
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO price_history (route_id, source, price, passengers, scraped_at) VALUES (?,?,?,?,?)",
            (route_id, source, price, passengers, datetime.utcnow().isoformat()),
        )


def get_average(route_id: str, days: int = 7) -> float | None:
    """Retorna a média de preços dos últimos N dias. None se não houver dados."""
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT AVG(price) as avg FROM price_history WHERE route_id=? AND scraped_at>=?",
            (route_id, cutoff),
        ).fetchone()
    return row["avg"] if row and row["avg"] is not None else None


def get_history(route_id: str, limit: int = 30) -> list[dict]:
    """Retorna histórico de preços de uma rota."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM price_history WHERE route_id=? ORDER BY scraped_at DESC LIMIT ?",
            (route_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def last_alert_hours_ago(cooldown_hours: int = 24) -> bool:
    """Retorna True se o último alerta foi há menos de cooldown_hours."""
    cutoff = (datetime.utcnow() - timedelta(hours=cooldown_hours)).isoformat()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM alert_log WHERE sent_at >= ?", (cutoff,)
        ).fetchone()
    return row["cnt"] > 0


def log_alert(routes_json: str, total_price: float):
    """Registra um alerta enviado."""
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO alert_log (routes_json, total_price, sent_at) VALUES (?,?,?)",
            (routes_json, total_price, datetime.utcnow().isoformat()),
        )


def count_price_records(route_id: str) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM price_history WHERE route_id=?", (route_id,)
        ).fetchone()
    return row["cnt"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--init", action="store_true")
    args = parser.parse_args()
    if args.init:
        init_db()
