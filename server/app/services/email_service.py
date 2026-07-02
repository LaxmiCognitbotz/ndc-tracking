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
        with smtplib.SMTP(smtp_host, smtp_port, timeout=60) as server:
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


async def send_fnf_details_email(email_to: str, record: dict) -> dict:
    """
    Send the F&F details of an employee to a specific email address,
    attaching the F&F document file if available.
    """
    from email.mime.application import MIMEApplication

    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    smtp_from = os.getenv("SMTP_FROM", smtp_user)

    if not smtp_user or not smtp_password:
        msg = "SMTP credentials not configured"
        logger.error(msg)
        return {"success": False, "message": msg}

    # Build simple, professional HTML template
    html_body = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    color: #334155;
    background-color: #f8fafc;
    padding: 30px 15px;
    margin: 0;
  }}
  .container {{
    max-width: 560px;
    margin: 0 auto;
    background: #ffffff;
    border-radius: 8px;
    border-top: 4px solid #0f766e;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -2px rgba(0, 0, 0, 0.05);
    overflow: hidden;
    border-left: 1px solid #e2e8f0;
    border-right: 1px solid #e2e8f0;
    border-bottom: 1px solid #e2e8f0;
  }}
  .content {{
    padding: 32px 24px;
  }}
  h2 {{
    color: #0f766e;
    font-size: 18px;
    font-weight: 600;
    margin-top: 0;
    margin-bottom: 20px;
    border-bottom: 1px solid #e2e8f0;
    padding-bottom: 10px;
  }}
  p {{
    margin: 0 0 16px;
    font-size: 14px;
    line-height: 1.6;
    color: #475569;
  }}
  .details-table {{
    width: 100%;
    border-collapse: collapse;
    margin: 20px 0;
    font-size: 13.5px;
  }}
  .details-table td {{
    padding: 10px 12px;
    border-bottom: 1px solid #f1f5f9;
  }}
  .details-table tr:last-child td {{
    border-bottom: none;
  }}
  .label {{
    font-weight: 600;
    color: #64748b;
    width: 38%;
  }}
  .value {{
    color: #0f172a;
    font-weight: 500;
  }}
  .footer {{
    background-color: #f8fafc;
    padding: 20px 24px;
    border-top: 1px solid #e2e8f0;
    font-size: 12.5px;
    color: #64748b;
    line-height: 1.5;
  }}
  .footer strong {{
    color: #475569;
  }}
</style>
</head>
<body>
<div class="container">
  <div class="content">
    <h2>Full &amp; Final Settlement Details</h2>
    <p>Dear Recipient,</p>
    <p>Please find below the Full &amp; Final (F&amp;F) settlement details for the employee clearance request:</p>
    
    <table class="details-table">
      <tr>
        <td class="label">Employee Name:</td>
        <td class="value">{record.get('employee_name')}</td>
      </tr>
      <tr>
        <td class="label">Person Number:</td>
        <td class="value">{record.get('person_number')}</td>
      </tr>
      <tr>
        <td class="label">Department:</td>
        <td class="value">{record.get('department')}</td>
      </tr>
      <tr>
        <td class="label">Resignation Date:</td>
        <td class="value">{_fmt_date(record.get('resignation_date'))}</td>
      </tr>
      <tr>
        <td class="label">Last Working Date:</td>
        <td class="value">{_fmt_date(record.get('last_working_date'))}</td>
      </tr>
      <tr>
        <td class="label">F&amp;F Status:</td>
        <td class="value">{record.get('fnf_status')}</td>
      </tr>
      <tr>
        <td class="label">Completed Date:</td>
        <td class="value">{_fmt_date(record.get('fnf_completed_date'))}</td>
      </tr>
      <tr>
        <td class="label">Document Count:</td>
        <td class="value">{record.get('fnf_document_count', 0)}</td>
      </tr>
    </table>
  </div>
  <div class="footer">
    Regards,<br>
    <strong>NDC Monitoring System</strong>
  </div>
</div>
</body>
</html>"""

    # Build MIMEMultipart message
    msg = MIMEMultipart("mixed")
    msg["Subject"] = f"F&F Settlement Details – {record.get('employee_name')} ({record.get('person_number')})"
    msg["From"] = smtp_from
    msg["To"] = email_to
    
    # Attach body
    body_part = MIMEText(html_body, "html")
    msg.attach(body_part)

    # Attach F&F document(s) from SharePoint or local folder as fallback
    attached_from_sharepoint = False
    person_number = record.get("person_number")
    
    if person_number:
        from app.services.sharepoint_service import SharePointService
        import httpx
        
        logger.info("Attempting to attach F&F document(s) from SharePoint for person: %s", person_number)
        sharepoint_service = SharePointService()
        async with httpx.AsyncClient() as client:
            try:
                # 1. Resolve site ID
                site_id = await sharepoint_service.get_site_id(client)
                
                # 2. Resolve drive ID and folder path
                drive_id, folder_path = await sharepoint_service.get_drive_details(client, site_id)
                
                # 3. Locate folder and list files
                files, resolved_folder = await sharepoint_service.get_person_folder_files(
                    client, site_id, drive_id, folder_path, person_number
                )
                
                if files:
                    if len(files) == 1:
                        # Single file attachment
                        file_item = files[0]
                        name = file_item.get("name", "document.pdf")
                        download_url = file_item.get("@microsoft.graph.downloadUrl")
                        if download_url:
                            logger.info("Downloading file '%s' from SharePoint for email attachment.", name)
                            res = await client.get(download_url)
                            if res.status_code == 200:
                                attachment = MIMEApplication(res.content)
                                attachment.add_header('Content-Disposition', 'attachment', filename=name)
                                msg.attach(attachment)
                                logger.info("Successfully attached SharePoint file '%s' to email.", name)
                                attached_from_sharepoint = True
                    else:
                        # Multiple files: ZIP them in-memory and attach
                        logger.info("Multiple files (%d) found in SharePoint. Zipping for email attachment...", len(files))
                        import io
                        import zipfile
                        
                        zip_buffer = io.BytesIO()
                        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                            for file_item in files:
                                name = file_item.get("name", "document.pdf")
                                download_url = file_item.get("@microsoft.graph.downloadUrl")
                                if download_url:
                                    logger.info("Downloading '%s' from SharePoint for email ZIP attachment...", name)
                                    res = await client.get(download_url)
                                    if res.status_code == 200:
                                        zip_file.writestr(name, res.content)
                                        
                        zip_buffer.seek(0)
                        zip_data = zip_buffer.read()
                        if zip_data:
                            zip_filename = f"{person_number}_documents.zip"
                            attachment = MIMEApplication(zip_data)
                            attachment.add_header('Content-Disposition', 'attachment', filename=zip_filename)
                            msg.attach(attachment)
                            logger.info("Successfully attached SharePoint ZIP archive '%s' to email.", zip_filename)
                            attached_from_sharepoint = True
                else:
                    logger.info("No SharePoint documents found for person: %s", person_number)
            except Exception as e:
                logger.error("Failed to retrieve SharePoint attachments for email: %s", str(e))

    # Fallback to local uploads folder if nothing was attached from SharePoint
    if not attached_from_sharepoint:
        fnf_doc_name = record.get("fnf_document")
        if fnf_doc_name:
            from database import BASE_DIR
            file_path = BASE_DIR / "uploads" / fnf_doc_name
            if file_path.exists():
                with open(file_path, "rb") as f:
                    attachment = MIMEApplication(f.read())
                attachment.add_header('Content-Disposition', 'attachment', filename=fnf_doc_name)
                msg.attach(attachment)
                logger.info("Attached F&F document from local server fallback: %s", fnf_doc_name)

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=60) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_from, [email_to], msg.as_string())

        logger.info("F&F details email sent to %s for %s", email_to, record.get('employee_name'))
        return {
            "success": True,
            "message": f"Email sent successfully to {email_to}.",
        }
    except Exception as e:
        logger.exception("Failed to send F&F details email: %s", e)
        return {"success": False, "message": f"Failed to send email: {e}"}
