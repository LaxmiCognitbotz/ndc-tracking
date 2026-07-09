import time
import subprocess
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Setup logging relative to the script's directory
current_dir = Path(__file__).parent.resolve()
log_file = current_dir / "daemon_log.txt"

logging.basicConfig(
    filename=str(log_file),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Detect python executable path dynamically from the server virtual environment
python_executable = current_dir.parent / "server" / ".venv" / "Scripts" / "python.exe"
if not python_executable.exists():
    python_executable = sys.executable

script_mail = current_dir / "mail.py"


def run_task():
    logging.info(f"Triggering script: {script_mail.name}...")
    try:
        result = subprocess.run(
            [str(python_executable), str(script_mail), "--job", "both"],
            capture_output=True,
            text=True,
            check=True,
            cwd=str(current_dir)
        )
        logging.info(f"{script_mail.name} executed successfully. Output:\n{result.stdout}")
    except subprocess.CalledProcessError as e:
        logging.error(f"Error executing {script_mail.name}: {e}\nOutput: {e.stdout}\nError Output: {e.stderr}")
    except Exception as e:
        logging.error(f"Unexpected error running {script_mail.name}: {e}")


def main():
    logging.info("Python Daemon started. Waiting to run daily at 10:00 AM...")
    
    while True:
        now = datetime.now()
        # Schedule for 10:00 AM
        target_time = now.replace(hour=10, minute=0, second=0, microsecond=0)
        
        # If it is past 10:00 AM today, schedule for tomorrow
        if now >= target_time:
            target_time += timedelta(days=1)
            
        delay = (target_time - now).total_seconds()
        logging.info(f"Next execution scheduled at {target_time.strftime('%Y-%m-%d %H:%M:%S')} (in {delay:.1f} seconds).")
        
        # Sleep until the target time
        time.sleep(delay)
        
        logging.info("It is 10:00 AM. Running scripts...")
        run_task()
        
        # Sleep for a minute to ensure we do not trigger again in the same minute
        time.sleep(60)


if __name__ == "__main__":
    main()
