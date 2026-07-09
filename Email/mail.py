import asyncio
import os
import smtplib
import json
import sys
import argparse
from datetime import date, datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from sqlalchemy import select, text

# Add the server directory (c:\NDC2\server) to sys.path so we can import app and database
current_dir = Path(__file__).parent.resolve()
parent_dir = current_dir.parent.resolve()
server_dir = parent_dir / "server"
sys.path.append(str(server_dir))


# Ensure we load environment variables for DB and SMTP
from dotenv import load_dotenv
local_env = current_dir / ".env"
server_env = server_dir / ".env"
parent_env = parent_dir / ".env"

if local_env.exists():
    load_dotenv(dotenv_path=local_env)
elif server_env.exists():
    load_dotenv(dotenv_path=server_env)
else:
    load_dotenv(dotenv_path=parent_env)

import importlib

# Dynamically import to resolve static IDE path analysis errors
database_module = importlib.import_module("database")
async_session = database_module.async_session

ndc_record_module = importlib.import_module("app.models.ndc_record")
NdcRecord = ndc_record_module.NdcRecord

ndc_approval_module = importlib.import_module("app.models.ndc_approval")
NdcApproval = ndc_approval_module.NdcApproval

email_recipient_module = importlib.import_module("app.models.email_recipient")
EmailRecipient = email_recipient_module.EmailRecipient

rm_email_config_module = importlib.import_module("app.models.rm_email_configuration")
RmEmailConfiguration = rm_email_config_module.RmEmailConfiguration


def _fmt_date(d=None):
    if d is None:
        return "—"
    if isinstance(d, (date, datetime)):
        return d.strftime("%d-%b-%Y")
    return str(d)


def send_email(records, recipient, stage_name, manager_name=None, is_tomorrow=False):
    """Format the records as HTML and send via SMTP."""
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    smtp_from = os.getenv("SMTP_FROM", smtp_user)

    if not smtp_user:
        print("Error: SMTP_USER not configured in .env")
        return False

    if not records:
        return False

    row_html = ""
    for rec in records:
        lwd = _fmt_date(rec.last_working_date)
        row_html += f"""
        <tr>
          <td>{rec.person_number}</td>
          <td>{rec.employee_name}</td>
          <td>{rec.department or '—'}</td>
          <td>{lwd}</td>
        </tr>"""

    greeting = f"Dear {manager_name}," if manager_name else "Hello,"
    warning_html = ""
    if manager_name and "Conflict Redirected" in manager_name:
        greeting = "Dear HR Team,"
        clean_name = manager_name.replace(" (Conflict Redirected)", "")
        warning_html = f"""
        <p style="color: #d9534f; font-weight: bold; background-color: #fdf7f7; border: 1px solid #d9534f; padding: 12px; border-radius: 5px; margin-bottom: 15px;">
          Warning: This report has been redirected to HR because there are multiple conflicting email configurations for manager '{clean_name}' in the system.
        </p>
        """

    if is_tomorrow:
        tomorrow_str = _fmt_date(date.today() + timedelta(days=1))
        intro_paragraph = f"""
        <p>The following users are currently pending in the <b>{stage_name}</b> Approval stage.</p>
        <p>These records have their last working date set for tomorrow ({tomorrow_str}):</p>
        """
        subject = f"Pending {stage_name} Approvals Report - Action Required Tomorrow"
    else:
        intro_paragraph = f"<p>The following users are currently pending in the <b>{stage_name}</b> Approval stage.</p>"
        subject = f"Pending {stage_name} Approvals Report - Action Required"

    html_body = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
body {{background:#f5f7fb;font-family:Arial,sans-serif;padding:30px;}}
.container {{max-width:800px;margin:auto;background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.08);}}
.header {{background:#0b3d91;color:white;padding:25px 35px;}}
.header h2 {{margin:0;}}
.content {{padding:30px;color:#333;line-height:1.7;}}
table {{width:100%;border-collapse:collapse;margin-top:15px;}}
th {{background:#eef3fb;padding:14px;text-align:left;}}
td {{padding:14px;border-bottom:1px solid #ececec;}}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h2>Pending {stage_name} Approval Records</h2>
  </div>
  <div class="content">
    <p>{greeting}</p>
    {warning_html}
    {intro_paragraph}
    <table>
      <tr>
        <th>Employee ID</th>
        <th>Name</th>
        <th>Department</th>
        <th>Last Working Date</th>
      </tr>
      {row_html}
    </table>
    <p>Please review these records and take the necessary actions.</p>
  </div>
</div>
</body>
</html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp_from
    msg["To"] = recipient
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.ehlo()
            if "starttls" in server.esmtp_features:
                server.starttls()
                server.ehlo()
            if smtp_password:
                server.login(smtp_user, smtp_password)
            server.sendmail(smtp_from, [recipient], msg.as_string())
        print(f"Successfully sent {stage_name} email with {len(records)} records to {recipient}.")
        return True
    except Exception as e:
        print(f"Failed to send {stage_name} email to {recipient}: {e}")
        return False


def send_duplicate_managers_report(records, recipient):
    """Format the conflicting/duplicate RM records as HTML and send to HR."""
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    smtp_from = os.getenv("SMTP_FROM", smtp_user)

    if not smtp_user:
        print("Error: SMTP_USER not configured in .env")
        return False

    if not records:
        return False

    row_html = ""
    for rm_name, rec in records:
        lwd = _fmt_date(rec.last_working_date)
        row_html += f"""
        <tr>
          <td style="font-weight: bold; color: #d9534f;">{rm_name}</td>
          <td>{rec.person_number}</td>
          <td>{rec.employee_name}</td>
          <td>{rec.department or '—'}</td>
          <td>{lwd}</td>
        </tr>"""

    html_body = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
body {{background:#f5f7fb;font-family:Arial,sans-serif;padding:30px;}}
.container {{max-width:850px;margin:auto;background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.08);}}
.header {{background:#d9534f;color:white;padding:25px 35px;}}
.header h2 {{margin:0;}}
.content {{padding:30px;color:#333;line-height:1.7;}}
table {{width:100%;border-collapse:collapse;margin-top:15px;}}
th {{background:#fdf7f7;padding:14px;text-align:left;border-bottom:2px solid #d9534f;}}
td {{padding:14px;border-bottom:1px solid #ececec;}}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h2>Conflicting RM Configurations - Redirected Approvals Report</h2>
  </div>
  <div class="content">
    <p>Dear HR Team,</p>
    <p style="color: #d9534f; font-weight: bold; background-color: #fdf7f7; border: 1px solid #d9534f; padding: 12px; border-radius: 5px; margin-bottom: 15px;">
      Warning: The following pending RM approvals have been redirected to HR because their Reporting Managers have multiple conflicting email configurations in the system. Please resolve these duplicates in the <b>rm_email_configuration</b> database table.
    </p>
    <table>
      <tr>
        <th>Reporting Manager</th>
        <th>Employee ID</th>
        <th>Name</th>
        <th>Department</th>
        <th>Last Working Date</th>
      </tr>
      {row_html}
    </table>
    <p>Please review these records and take the necessary actions.</p>
  </div>
</div>
</body>
</html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Redirected RM Approvals Report (Conflicting Manager Configurations) - Action Required"
    msg["From"] = smtp_from
    msg["To"] = recipient
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.ehlo()
            if "starttls" in server.esmtp_features:
                server.starttls()
                server.ehlo()
            if smtp_password:
                server.login(smtp_user, smtp_password)
            server.sendmail(smtp_from, [recipient], msg.as_string())
        print(f"Successfully sent consolidated duplicate RM report with {len(records)} records to HR ({recipient}).")
        return True
    except Exception as e:
        print(f"Failed to send consolidated duplicate RM report to HR ({recipient}): {e}")
        return False


async def fetch_all_data():
    from sqlalchemy.orm import defer
    async with async_session() as session:
        # Check if 'approver_name' column exists in database to avoid ProgrammingError on old schemas
        has_approver_name_col = False
        try:
            col_check = await session.execute(text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='ndc_records' AND column_name='approver_name')"
            ))
            has_approver_name_col = col_check.scalar()
        except Exception as e:
            print(f"Warning: Could not check for approver_name column presence: {e}")

        query = select(NdcRecord, NdcApproval).join(NdcApproval, NdcRecord.id == NdcApproval.ndc_record_id)
        if not has_approver_name_col and hasattr(NdcRecord, "approver_name"):
            query = query.options(defer(NdcRecord.approver_name))
            
        result = await session.execute(query)
        rows = result.all()
        
        # Group by record
        records_map = {}
        for rec, app in rows:
            if rec.id not in records_map:
                records_map[rec.id] = {
                    "record": rec,
                    "approvals": {},
                    "db_approvals": []
                }
            records_map[rec.id]["db_approvals"].append(app)
            
            # Use lower case for consistent matching
            stage = app.stage_name.strip().lower()
            status = app.status.strip().lower() if app.status else ""
            
            # Handle GCC HR vs HR carefully
            if "gcc hr" in stage:
                key = "gcc hr"
            elif "hr" in stage:
                key = "hr"
            elif "rm" in stage:
                key = "rm"
            elif "telecom" in stage:
                key = "telecom"
            elif "administration" in stage or "admin" in stage:
                key = "administration"
            elif "it" in stage:
                key = "it"
            elif "safety" in stage:
                key = "safety"
            elif "security" in stage:
                key = "security"
            elif "final abex" in stage:
                key = "final abex"
            elif "abex" in stage:
                key = "abex"
            elif "store" in stage:
                key = "store"
            elif "business specific" in stage:
                key = "business specific"
            elif "legatrix" in stage:
                key = "legatrix"
            else:
                key = stage
                
            records_map[rec.id]["approvals"][key] = status
            
        return records_map


async def run_10am_job():
    """Daily 10:00 AM Email Job to send all pending approval updates."""
    print("Starting consolidated 10:00 AM email job...")
    records_map = await fetch_all_data()
    
    # Fetch department email recipients and RM configs
    dept_email_map = {}
    rm_configs_by_name = {}  # key: rm_name (lower) -> list of emails
    
    async with async_session() as session:
        try:
            dept_res = await session.execute(select(EmailRecipient))
            for rec in dept_res.scalars().all():
                if rec.department and rec.email:
                    dept_email_map[rec.department.strip().lower()] = rec.email.strip()
        except Exception as e:
            print(f"Warning: Could not fetch department email recipients: {e}")
            
        try:
            rm_configs_res = await session.execute(select(RmEmailConfiguration))
            for cfg in rm_configs_res.scalars().all():
                if cfg.rm_name and cfg.email:
                    name_key = cfg.rm_name.strip().lower()
                    email_val = cfg.email.strip()
                    if name_key not in rm_configs_by_name:
                        rm_configs_by_name[name_key] = []
                    rm_configs_by_name[name_key].append(email_val)
        except Exception as e:
            print(f"Warning: Could not fetch RM email configurations: {e}")
            
    rm_groups = {}  # key: (rm_name, rm_email) -> value: list of NdcRecord
    duplicate_rm_records = []  # list of (rm_name, rec)
    
    departments = [
        ("HR", dept_email_map.get("hr")),
        ("Telecom", dept_email_map.get("telecom")),
        ("Administration", dept_email_map.get("administration")),
        ("GCC HR", dept_email_map.get("gcc hr")),
        ("Abex", dept_email_map.get("abex")),
        ("Store", dept_email_map.get("store")),
        ("Safety", dept_email_map.get("safety")),
        ("Final Abex", dept_email_map.get("final abex")),
        ("Business Specific", dept_email_map.get("business specific")),
        ("Legatrix", dept_email_map.get("legatrix")),
    ]
    
    emails_to_send = {dep: [] for dep, _ in departments}
    
    for rec_id, data in records_map.items():
        rec = data["record"]
        approvals = data["approvals"]
        db_approvals = data.get("db_approvals", [])
        
        # 1. Group for RM department separately (only if Pending)
        if approvals.get("rm", "") == "pending":
            rm_name = getattr(rec, "approver_name", None)
            if not rm_name:
                for app in db_approvals:
                    if app.stage_name.strip().lower() == "rm":
                        rm_name = app.approver_name
                        break
            
            if rm_name:
                rm_name = rm_name.strip()
            else:
                rm_name = "Unknown Manager"
                
            has_conflict = False
            rm_email = None
            
            if rm_name and rm_name != "Unknown Manager":
                normalized_rm = rm_name.lower()
                if normalized_rm in rm_configs_by_name:
                    emails = rm_configs_by_name[normalized_rm]
                    if len(emails) > 1:
                        has_conflict = True
                    elif len(emails) == 1:
                        rm_email = emails[0]
            
            default_rm_email = dept_email_map.get("rm")
            
            if has_conflict:
                duplicate_rm_records.append((rm_name, rec))
            else:
                target_email = rm_email or default_rm_email
                if not target_email:
                    print(f"Skipping notification for RM '{rm_name}': no email configuration or default RM email found.")
                    continue
                key = (rm_name, target_email)
                if key not in rm_groups:
                    rm_groups[key] = []
                rm_groups[key].append(rec)
            
        # 2. Build for other departments
        for dept_name, recipient in departments:
            dept_key = dept_name.lower()
            current_status = approvals.get(dept_key, "")
            
            # Specific rule for GCC HR
            if dept_name == "GCC HR":
                req_depts = ["rm", "it", "telecom", "safety", "administration", "security", "hr"]
                all_completed = True
                for req_d in req_depts:
                    if approvals.get(req_d, "") != "completed":
                        all_completed = False
                        break
                
                if current_status == "pending" and all_completed:
                    emails_to_send[dept_name].append(rec)
            else:
                if current_status == "pending":
                    emails_to_send[dept_name].append(rec)
                        
    # Send RM emails in batches
    rm_group_items = list(rm_groups.items())
    total_rm_emails = len(rm_group_items)
    
    success_count = 0
    failure_count = 0
    
    if total_rm_emails > 0:
        BATCH_SIZE = int(os.getenv("EMAIL_BATCH_SIZE", "10"))
        BATCH_DELAY = int(os.getenv("EMAIL_BATCH_DELAY_SECONDS", "30"))
        
        print(f"Starting RM email send. Total unique RMs: {total_rm_emails}. Batch size: {BATCH_SIZE}. Batch delay: {BATCH_DELAY}s.")
        
        for i in range(0, total_rm_emails, BATCH_SIZE):
            batch = rm_group_items[i:i + BATCH_SIZE]
            print(f"Sending RM email batch {i // BATCH_SIZE + 1} (emails {i+1} to {min(i + BATCH_SIZE, total_rm_emails)} of {total_rm_emails})...")
            
            for (rm_name, rm_email), recs in batch:
                try:
                    success = send_email(recs, rm_email, "RM", manager_name=rm_name)
                    if success:
                        success_count += 1
                    else:
                        failure_count += 1
                except Exception as e:
                    print(f"Failed to send email to RM '{rm_name}' ({rm_email}): {e}")
                    failure_count += 1
                await asyncio.sleep(2)
            
            if i + BATCH_SIZE < total_rm_emails:
                print(f"Waiting for {BATCH_DELAY} seconds before next batch...")
                await asyncio.sleep(BATCH_DELAY)
                
        print(f"RM Email Job Completed. Success: {success_count}, Failure: {failure_count}")
    else:
        print("No pending RM records. Skipping RM emails.")
        
    # Send duplicate/conflicting RM records report to HR
    if duplicate_rm_records:
        hr_email = dept_email_map.get("hr")
        if hr_email:
            send_duplicate_managers_report(duplicate_rm_records, hr_email)
        else:
            print("Warning: Conflicting RM records found, but HR email is not configured in database.")
        await asyncio.sleep(2)
        
    # Send other department emails
    for dept_name, recipient in departments:
        if not recipient:
            print(f"Skipping {dept_name} daily notification: recipient email is not configured.")
            continue
            
        records_for_dept = emails_to_send[dept_name]
        if records_for_dept:
            send_email(records_for_dept, recipient, dept_name)
        else:
            print(f"No pending records for {dept_name}. Skipping email.")


async def get_pending_records_for_tomorrow(stage_keyword: str):
    """Fetch NdcRecord instances where the specified stage is pending and last_working_date is tomorrow."""
    target_date = date.today() + timedelta(days=1)
    
    async with async_session() as session:
        query = (
            select(NdcRecord)
            .join(NdcApproval, NdcRecord.id == NdcApproval.ndc_record_id)
            .where(
                NdcApproval.stage_name.ilike(f"%{stage_keyword}%"),
                NdcApproval.status.ilike("PENDING"),
                NdcRecord.last_working_date == target_date
            )
            .distinct()
        )
        result = await session.execute(query)
        records = result.scalars().unique().all()
        
        # Ensure strict uniqueness by person_number
        unique_records = []
        seen_person_numbers = set()
        for r in records:
            if r.person_number not in seen_person_numbers:
                seen_person_numbers.add(r.person_number)
                unique_records.append(r)
                
        return unique_records


async def process_stage_for_tomorrow(keyword: str, recipient: str, stage_name: str):
    if not recipient:
        print(f"Skipping {stage_name} tomorrow notification: recipient email is not configured.")
        return
        
    print(f"Fetching pending {stage_name} records for tomorrow...")
    records = await get_pending_records_for_tomorrow(keyword)
    
    if not records:
        print(f"No pending {stage_name} records found for tomorrow. Email not sent.")
        return
        
    print(f"Found {len(records)} pending {stage_name} records for tomorrow. Sending email to {recipient}...")
    send_email(records, recipient, stage_name, is_tomorrow=True)


async def run_tomorrow_alert_job():
    """Tomorrow Alert Job specifically for IT & Security pending actions."""
    print("Starting Tomorrow Alerts (IT & Security) email job...")
    dept_email_map = {}
    async with async_session() as session:
        try:
            res = await session.execute(select(EmailRecipient))
            for rec in res.scalars().all():
                if rec.department and rec.email:
                    dept_email_map[rec.department.strip().lower()] = rec.email.strip()
        except Exception as e:
            print(f"Warning: Could not fetch department email recipients: {e}")

    # 1. Process IT Approvals for tomorrow
    await process_stage_for_tomorrow(
        keyword="IT", 
        recipient=dept_email_map.get("it"), 
        stage_name="IT"
    )
    
    # 2. Process Security Approvals for tomorrow
    await process_stage_for_tomorrow(
        keyword="Security", 
        recipient=dept_email_map.get("security"), 
        stage_name="Security"
    )


async def main():
    parser = argparse.ArgumentParser(description="NDC Tracking Email Notification CLI")
    parser.add_argument(
        "--job",
        type=str,
        default="both",
        choices=["10am", "tomorrow", "both"],
        help="Specify which email job to run: 10am (daily consolidated reports), tomorrow (IT & Security next-day alerts), or both (runs both sequentially)"
    )
    args = parser.parse_args()
    
    print(f"Executing email script at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}...")
    
    if args.job == "10am":
        await run_10am_job()
    elif args.job == "tomorrow":
        await run_tomorrow_alert_job()
    else:
        # Run both sequentially
        await run_10am_job()
        # Brief pause between tasks to avoid SMTP throttling
        await asyncio.sleep(5)
        await run_tomorrow_alert_job()


if __name__ == "__main__":
    asyncio.run(main())
