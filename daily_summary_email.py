"""Emails a daily recap of purchases entered today.

Meant to run as a scheduled job (see .github/workflows/daily-summary-email.yml)
independent of the Streamlit app itself — same pattern as rcm_scraper.py.

Required environment variables:
    SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, EMAIL_TO
    EMAIL_FROM (optional, defaults to SMTP_USERNAME)

Usage:
    python daily_summary_email.py
"""
from __future__ import annotations

import datetime
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from zoneinfo import ZoneInfo

from db import Purchase, get_session

CENTRAL = ZoneInfo("America/Chicago")


def build_summary(today: datetime.date) -> tuple[str, str]:
    """Return (plain_text, html) for today's purchases."""
    day_start = datetime.datetime.combine(today, datetime.time())
    day_end = day_start + datetime.timedelta(days=1)

    session = get_session()
    try:
        purchases = (
            session.query(Purchase)
            .filter(Purchase.entry_date >= day_start, Purchase.entry_date < day_end)
            .order_by(Purchase.created_at)
            .all()
        )

        total_bushels = sum(p.bushels or 0 for p in purchases)

        by_group: dict[tuple[str, str], dict] = {}
        for p in purchases:
            key = (p.commodity, p.delivery_window or "—")
            bucket = by_group.setdefault(key, {"bushels": 0.0, "count": 0})
            bucket["bushels"] += p.bushels or 0
            bucket["count"] += 1

        date_str = today.strftime("%B %d, %Y")

        text_lines = [f"RCM Originator Portal — Daily Purchase Recap for {date_str}", ""]
        html_rows = []

        if not purchases:
            text_lines.append("No purchases were entered today.")
            html_rows.append("<tr><td colspan='4'>No purchases were entered today.</td></tr>")
        else:
            text_lines.append(f"Total: {len(purchases)} purchase(s), {total_bushels:,.0f} bushels")
            text_lines.append("")
            text_lines.append("By commodity / delivery window:")
            for (commodity, window), v in sorted(by_group.items()):
                text_lines.append(
                    f"  {commodity} — {window}: {v['bushels']:,.0f} bu ({v['count']} purchase(s))"
                )
                html_rows.append(
                    f"<tr><td>{commodity}</td><td>{window}</td>"
                    f"<td style='text-align:right'>{v['bushels']:,.0f}</td>"
                    f"<td style='text-align:right'>{v['count']}</td></tr>"
                )

            text_lines.append("")
            text_lines.append("All purchases:")
            for p in purchases:
                text_lines.append(
                    f"  {p.originator.company_name} — {p.customer_name} — {p.commodity} "
                    f"{p.bushels:,.0f} bu @ ${p.flat_price:.4f} ({p.delivery_window})"
                )

        plain_text = "\n".join(text_lines)

        html = f"""
        <html><body style="font-family: sans-serif; color: #242424;">
        <h2 style="color:#347A0C;">RCM Originator Portal — Daily Purchase Recap</h2>
        <p><strong>{date_str}</strong></p>
        <p>Total: <strong>{len(purchases)} purchase(s), {total_bushels:,.0f} bushels</strong></p>
        <table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;">
          <tr style="background:#347A0C; color:#fff;">
            <th>Commodity</th><th>Delivery Window</th><th>Total Bushels</th><th>Purchases</th>
          </tr>
          {''.join(html_rows)}
        </table>
        </body></html>
        """
        return plain_text, html
    finally:
        session.close()


def send_email(plain_text: str, html: str, today: datetime.date):
    smtp_host = os.environ["SMTP_HOST"]
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_username = os.environ["SMTP_USERNAME"]
    smtp_password = os.environ["SMTP_PASSWORD"]
    email_from = os.environ.get("EMAIL_FROM", smtp_username)
    email_to = [addr.strip() for addr in os.environ["EMAIL_TO"].split(",") if addr.strip()]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"RCM Originator Portal — Daily Recap for {today.strftime('%m/%d/%Y')}"
    msg["From"] = email_from
    msg["To"] = ", ".join(email_to)
    msg.attach(MIMEText(plain_text, "plain"))
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
        server.starttls()
        server.login(smtp_username, smtp_password)
        server.sendmail(email_from, email_to, msg.as_string())


if __name__ == "__main__":
    # The GitHub Actions schedule fires this twice a day (see
    # daily-summary-email.yml) to land on 3pm Central across both DST states,
    # since Actions cron is UTC-only. Only actually send on the run that's
    # genuinely close to 3pm Central right now; the other is a no-op. A
    # manual "Run workflow" trigger has no such constraint and always sends.
    now_central = datetime.datetime.now(CENTRAL)
    is_scheduled_run = os.environ.get("GITHUB_EVENT_NAME") == "schedule"
    if is_scheduled_run and now_central.hour != 15:
        print(f"Not close to 3pm Central right now ({now_central}); skipping.")
    else:
        today = datetime.date.today()
        plain_text, html = build_summary(today)
        send_email(plain_text, html, today)
        print(f"Daily recap emailed for {today}.")
