"""Email service – sends the NDC Delayed Cases reminder email via SMTP."""

import os
import smtplib
import logging
from datetime import date, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


# ── helpers ──────────────────────────────────────────────────────────────────

def _fmt_date(d) -> str:
    """Format a date or date-string as '01-Jun-2026'."""
    if d is None:
        return "—"
    if isinstance(d, (date, datetime)):
        return d.strftime("%d-%b-%Y")
    try:
        return datetime.strptime(str(d), "%Y-%m-%d").strftime("%d-%b-%Y")
    except Exception:
        return str(d)


def _days_delayed(last_working_date) -> int:
    """Return how many calendar days have passed since last_working_date."""
    if last_working_date is None:
        return 0
    if isinstance(last_working_date, (date, datetime)):
        lwd = last_working_date if isinstance(last_working_date, date) else last_working_date.date()
    else:
        try:
            lwd = datetime.strptime(str(last_working_date), "%Y-%m-%d").date()
        except Exception:
            return 0
    diff = (date.today() - lwd).days
    return max(0, diff)


# ── HTML template builder ─────────────────────────────────────────────────────

def _build_html(records: list[dict]) -> str:
    """Build the full HTML email body for the delayed-cases reminder."""

    row_html = ""
    for rec in records:
        days = rec.get("days_delayed", 0)
        row_html += f"""
        <tr>
          <td>{rec.get('person_number', '')}</td>
          <td>{rec.get('employee_name', '')}</td>
          <td>{rec.get('department', '—')}</td>
          <td>{_fmt_date(rec.get('last_working_date'))}</td>
          <td><span class="delay">{days} Days</span></td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
body{{background:#f5f7fb;font-family:Arial,sans-serif;padding:30px;}}
.container{{max-width:1000px;margin:auto;background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.08);}}
.header{{background:#0b3d91;color:white;padding:25px 35px;}}
.header h2{{margin:0;}}
.content{{padding:30px;color:#333;line-height:1.7;}}
.summary{{background:#f4f8ff;padding:14px 18px;border-left:4px solid #0b3d91;margin:20px 0;}}
table{{width:100%;border-collapse:collapse;margin-top:15px;}}
th{{background:#eef3fb;padding:14px;text-align:left;}}
td{{padding:14px;border-bottom:1px solid #ececec;}}
.delay{{background:#ffe5e5;color:#d62828;padding:6px 12px;border-radius:20px;font-weight:600;}}
.note{{background:#fff7e6;padding:16px;margin-top:25px;border-left:4px solid #ffb020;}}
.footer{{padding:25px 30px;background:#fafafa;color:#666;}}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h2>NDC Delayed Cases – Top 10 Report</h2>
  </div>
  <div class="content">
    <p>Hello Team,</p>
    <p>
      Please find below the list of the <b>Top {min(len(records), 10)} delayed cases</b>
      identified as of today ({_fmt_date(date.today())}).
      These records have exceeded the expected completion timeline and require attention for closure.
    </p>
    <table>
      <tr>
        <th>Employee ID</th>
        <th>Name</th>
        <th>Department</th>
        <th>Pending Since</th>
        <th>Days Delayed</th>
      </tr>
      {row_html}
    </table>
    <div class="note">
      Please review the above delayed cases and take the required actions at the earliest
      to avoid further aging and ensure timely closure.
    </div>
    <p>If any of these records have already been processed, kindly ignore this notification.</p>
    <p>Thank you for your support.</p>
  </div>
  <div class="footer">
    Regards,<br>
    <b>Automation Team</b><br>
    NDC Monitoring System
  </div>
</div>
</body>
</html>"""
    return html


# ── main send function ────────────────────────────────────────────────────────

async def send_delayed_reminder(records: list[dict]) -> dict:
    """
    Send the NDC delayed-cases reminder email with the top 10 delayed records.

    Args:
        records: Top-N delayed records (dicts with keys: person_number,
                 employee_name, department, last_working_date, days_delayed).

    Returns:
        {"success": bool, "message": str}
    """
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    smtp_from = os.getenv("SMTP_FROM", smtp_user)
    recipient = os.getenv("EMAIL_RECIPIENT", "")

    if not smtp_user or not smtp_password:
        msg = "SMTP credentials not configured"
        logger.error(msg)
        return {"success": False, "message": msg}

    if not recipient:
        msg = "EMAIL_RECIPIENT not configured"
        logger.error(msg)
        return {"success": False, "message": msg}

    html_body = _build_html(records)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"NDC Delayed Cases Reminder – Top {min(len(records), 10)} Records ({_fmt_date(date.today())})"
    msg["From"] = smtp_from
    msg["To"] = recipient
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_from, [recipient], msg.as_string())

        logger.info("Delayed-cases reminder sent to %s (%d records)", recipient, len(records))
        return {
            "success": True,
            "message": f"Reminder email sent to {recipient} with {len(records)} delayed records.",
        }
    except Exception as e:
        logger.exception("Failed to send reminder email: %s", e)
        return {"success": False, "message": f"Email failed: {e}"}
