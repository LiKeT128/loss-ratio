"""June loss-ratio scorecard for a fictional Bratislava insurer.

Frequency, severity, and loss ratio are SQL measures on a star schema.
A large-claim flag comes from an assumption row, not from a hardcoded filter.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data" / "portfolio.db"
REPORT_PATH = ROOT / "scorecard" / "index.html"
SCHEMA = (ROOT / "schema.sql").read_text(encoding="utf-8")


def euro(amount: int) -> str:
    return f"€{amount:,}"


def per_euro(bps: int) -> str:
    whole = bps // 10000
    cents = (bps % 10000) // 100
    return f"€{whole}.{cents:02d}"


def pct(bps: int) -> str:
    return f"{bps // 100}.{bps % 100:02d}%"


def per_hundred(bps: int) -> str:
    return f"{bps // 100}.{bps % 100:02d}"


def build() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.executemany(
        "INSERT INTO dim_product (product_id, name) VALUES (?, ?)",
        [(1, "Motor"), (2, "Home"), (3, "Travel")],
    )
    conn.executemany(
        "INSERT INTO fact_exposure (product_id, policies, earned_premium_eur) VALUES (?, ?, ?)",
        [
            (1, 2000, 250_000),
            (2, 500, 100_000),
            (3, 2500, 50_000),
        ],
    )
    conn.execute(
        "INSERT INTO assumption (name, value_eur) VALUES ('large_claim_eur', 10000)"
    )
    claims: list[tuple[int, int, int]] = []
    claims.extend((2000 + i, 1, 1500) for i in range(100))
    claims.extend((1100 + i, 2, 2500) for i in range(8))
    claims.extend([(1001, 2, 50_000), (1002, 2, 50_000)])
    claims.extend((3000 + i, 3, 400) for i in range(25))
    conn.executemany(
        "INSERT INTO fact_claim (claim_id, product_id, paid_eur) VALUES (?, ?, ?)",
        claims,
    )
    conn.commit()
    return conn


def query(conn: sqlite3.Connection, name: str) -> list[sqlite3.Row]:
    sql = (ROOT / "sql" / name).read_text(encoding="utf-8")
    return list(conn.execute(sql))


def render(conn: sqlite3.Connection) -> None:
    rows = query(conn, "01_scorecard.sql")
    large = query(conn, "02_large_claims.sql")
    book = query(conn, "03_portfolio.sql")[0]

    for row in rows:
        if row["severity_tie_eur"] != 0 or row["frequency_tie"] != 0 or row["loss_ratio_tie"] != 0:
            raise SystemExit(f"{row['name']} does not tie")
    if book["unexplained_eur"] != 0 or book["claim_count_tie"] != 0 or book["weight_tie"] != 0:
        raise SystemExit(
            f"portfolio does not tie: {book['unexplained_eur']} "
            f"{book['claim_count_tie']} {book['weight_tie']}"
        )

    worst = max(rows, key=lambda row: int(row["loss_ratio_bps"]))
    if worst["name"] != "Home" or worst["loss_ratio_bps"] != 12000:
        raise SystemExit("expected Home at 120%")
    if worst["loss_ratio_ex_large_bps"] != 2000 or worst["large_count"] != 2:
        raise SystemExit("expected Home to fall to 20% without two large claims")
    if book["loss_ratio_bps"] != 7000 or len(large) != 2:
        raise SystemExit("expected a 70% book and two large claims")
    if len({int(row["paid_eur"]) for row in large}) != 1:
        raise SystemExit("expected the large claims to share one amount")

    cards = []
    for row in rows:
        mark = " hot" if row["product_id"] == worst["product_id"] else ""
        cards.append(
            f"<article class='card{mark}'>"
            f"<p class='ratio'>{pct(row['loss_ratio_bps'])}</p>"
            f"<h2>{row['name']}</h2>"
            f"<p>{per_euro(row['loss_ratio_bps'])} of claims per €1 of premium</p>"
            f"<p>{per_hundred(row['frequency_bps'])} claims per 100 policies · "
            f"severity {euro(row['severity_eur'])}</p>"
            "</article>"
        )
    body = []
    for row in rows:
        body.append(
            "<tr>"
            f"<td>{row['name']}</td>"
            f"<td class='num'>{row['policies']:,}</td>"
            f"<td class='num'>{euro(row['earned_premium_eur'])}</td>"
            f"<td class='num'>{row['claim_count']}</td>"
            f"<td class='num'>{per_hundred(row['frequency_bps'])}</td>"
            f"<td class='num'>{euro(row['severity_eur'])}</td>"
            f"<td class='num'>{euro(row['paid_eur'])}</td>"
            f"<td class='num'>{pct(row['loss_ratio_bps'])}</td>"
            f"<td class='num'>{pct(row['loss_ratio_ex_large_bps'])}</td>"
            "</tr>"
        )
    attritional = list(
        conn.execute(
            """
            SELECT paid_eur, COUNT(*) AS n
            FROM v_claim
            WHERE product_id = ? AND is_large = 0
            GROUP BY paid_eur
            ORDER BY n DESC
            """,
            (worst["product_id"],),
        )
    )
    if len(attritional) != 1:
        raise SystemExit("expected one attritional claim size on the worst product")
    small_paid = int(attritional[0]["paid_eur"])
    small_n = int(attritional[0]["n"])
    large_rows = "".join(
        f"<li>{row['name']} claim {row['claim_id']}: {euro(row['paid_eur'])}</li>"
        for row in large
    )
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>June loss ratio · Hron Mutual</title>
  <style>
    body {{ margin: 0; background: #f4f1ea; color: #1a1a1a; font-family: Aptos, "Segoe UI", sans-serif; }}
    main {{ width: min(980px, calc(100% - 32px)); margin: 0 auto; padding: 36px 0 64px; }}
    .kicker {{ font-size: 12px; letter-spacing: 0.14em; text-transform: uppercase; margin: 0; color: #5c564c; }}
    h1 {{ font-size: 34px; font-weight: 650; letter-spacing: -0.03em; line-height: 1.15; margin: 10px 0 8px; max-width: 22ch; }}
    .lead {{ max-width: 62ch; line-height: 1.45; margin-top: 0; }}
    .grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin: 28px 0; }}
    .card {{ background: #fff; border: 1px solid #e2dcd0; padding: 16px 16px 12px; }}
    .card.hot {{ background: #1a1a1a; color: #f4f1ea; border-color: #1a1a1a; }}
    .ratio {{ font-size: 42px; font-weight: 650; letter-spacing: -0.04em; margin: 0; font-variant-numeric: tabular-nums; }}
    .card h2 {{ margin: 4px 0 8px; font-size: 16px; font-weight: 650; }}
    .card p {{ margin: 0 0 6px; font-size: 14px; line-height: 1.35; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; font-size: 14px; }}
    th, td {{ text-align: left; padding: 8px 8px; border-bottom: 1px solid #e2dcd0; }}
    th {{ font-size: 11px; letter-spacing: 0.04em; text-transform: uppercase; color: #5c564c; }}
    .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
    h2.section {{ font-size: 13px; letter-spacing: 0.08em; text-transform: uppercase; margin: 28px 0 8px; }}
    ul {{ margin: 0; padding-left: 18px; }}
    footer {{ margin-top: 22px; color: #5c564c; font-size: 13px; max-width: 78ch; line-height: 1.45; }}
    @media (max-width: 720px) {{
      .grid {{ grid-template-columns: 1fr; }}
      h1 {{ font-size: 28px; }}
    }}
  </style>
</head>
<body>
<main>
  <p class="kicker">Hron Mutual · Bratislava · June 2026 · fictional</p>
  <h1>{worst['name']} returns {per_euro(worst['loss_ratio_bps'])} of claims per €1 of premium.</h1>
  <p class="lead">The book looks fine at {pct(book['loss_ratio_bps'])}. That average hides {worst['name']}. {worst['name']} is the least frequent line, {per_hundred(worst['frequency_bps'])} claims per 100 policies, and the only one above 100%. Motor is more than twice as frequent and still at {pct(next(row['loss_ratio_bps'] for row in rows if row['name'] == 'Motor'))}.</p>
  <section class="grid">
    {''.join(cards)}
  </section>
  <h2 class="section">Without claims at or above {euro(conn.execute("SELECT value_eur FROM assumption WHERE name = 'large_claim_eur'").fetchone()[0])}</h2>
  <p class="lead">{worst['name']} falls from {pct(worst['loss_ratio_bps'])} to {pct(worst['loss_ratio_ex_large_bps'])}. The average severity of {euro(worst['severity_eur'])} describes neither the {small_n} claims of {euro(small_paid)} nor the {len(large)} claims of {euro(large[0]['paid_eur'])}.</p>
  <ul>
    {large_rows}
  </ul>
  <h2 class="section">Scorecard</h2>
  <table>
    <thead>
      <tr>
        <th>Product</th><th>Policies</th><th>Earned premium</th><th>Claims</th>
        <th>Per 100</th><th>Severity</th><th>Paid</th><th>Loss ratio</th><th>Ex-large</th>
      </tr>
    </thead>
    <tbody>
      {''.join(body)}
    </tbody>
  </table>
  <footer>
    Loss ratio is claims paid divided by earned premium. Frequency is claims divided by policies. Severity is paid divided by claim count. The portfolio ratio is the premium-weighted average of the three product ratios, and that check is zero in sql/03_portfolio.sql. Tables are dim_product, fact_exposure, and fact_claim. The €10,000 cut lives in the assumption table.
  </footer>
</main>
</body>
</html>
"""
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(page, encoding="utf-8")
    print(
        f"book={book['loss_ratio_bps']} worst={worst['name']} "
        f"{worst['loss_ratio_bps']} ex={worst['loss_ratio_ex_large_bps']} "
        f"large={len(large)} unexplained={book['unexplained_eur']}"
    )
    print(REPORT_PATH)


if __name__ == "__main__":
    connection = build()
    try:
        render(connection)
    finally:
        connection.close()
