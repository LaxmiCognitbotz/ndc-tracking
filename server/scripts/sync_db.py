import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

def run_sync():
    print("=" * 60)
    print(f"[START] Database Synchronization at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # Resolve the absolute path to the root 'server' directory
    BASE_DIR = Path(__file__).resolve().parent.parent
    os.chdir(BASE_DIR)
    
    # Locate alembic in the virtual environment
    alembic_exe = BASE_DIR / ".venv" / "Scripts" / "alembic.exe"
    if not alembic_exe.exists():
        alembic_exe = "alembic" # fallback if activated
        
    print("\n[1/3] Checking for any pending migrations from GitHub...")
    res_upg_initial = subprocess.run(
        [str(alembic_exe), "upgrade", "head"], 
        capture_output=True, text=True
    )
    if res_upg_initial.returncode != 0:
        print(f"[ERROR] Error applying existing migrations:\n{res_upg_initial.stderr}")
        sys.exit(1)
        
    rev_msg = f"auto_sync_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    print("\n[2/3] Comparing database schema against your SQLAlchemy models...")
    res_gen = subprocess.run(
        [str(alembic_exe), "revision", "--autogenerate", "-m", rev_msg], 
        capture_output=True, text=True
    )
    
    if res_gen.returncode != 0:
        print(f"[ERROR] Error generating migration:\n{res_gen.stderr}")
        sys.exit(1)
        
    output = res_gen.stdout + res_gen.stderr
    print(output.strip())
    
    if "No changes in schema detected" in output:
        print("\n[SUCCESS] Your database is already perfectly in sync with your models!")
        print("=" * 60)
        return
        
    print("\n[3/3] Applying the newly generated schema changes to the database...")
    res_upg_final = subprocess.run(
        [str(alembic_exe), "upgrade", "head"], 
        capture_output=True, text=True
    )
    
    if res_upg_final.returncode != 0:
        print(f"[ERROR] Error applying new migration:\n{res_upg_final.stderr}")
        sys.exit(1)
        
    print(res_upg_final.stdout.strip())
    print("\n[SUCCESS] Database schema synchronized successfully!")
    print("=" * 60)

if __name__ == "__main__":
    run_sync()
