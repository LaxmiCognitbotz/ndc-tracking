import datetime
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

def setup_logging():
    """Configure server logging to write to a rotating file outside the server directory."""
    
    # Define log folder
    base_dir = Path(__file__).resolve().parent.parent.parent
    log_dir = base_dir / "logs"
    log_dir.mkdir(exist_ok=True)
    
    log_file = log_dir / "server_logs.log"
    
    # Write a clean startup banner to the log file
    import os
    if not os.environ.get("SERVER_BANNER_PRINTED"):
        now_str = datetime.datetime.now().strftime("%d-%m-%y %H:%M:%S")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"\n========================\nServer started at - {now_str}\n========================\n")
        os.environ["SERVER_BANNER_PRINTED"] = "1"
    
    # Create file handler with log rotation (max 10MB per file)
    file_handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5, encoding="utf-8")
    
    # Date format: DD-MM-YY HH:MM:SS
    file_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%d-%m-%y %H:%M:%S")
    file_handler.setFormatter(file_formatter)

    # Set root logger to ONLY use the file handler
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Clear default terminal handlers to keep terminal clean
    for h in list(root_logger.handlers):
        root_logger.removeHandler(h)
    
    if not any(isinstance(h, RotatingFileHandler) for h in root_logger.handlers):
        root_logger.addHandler(file_handler)

    # Attach file handler to Uvicorn loggers so their startup info gets logged to the file too
    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        u_logger = logging.getLogger(logger_name)
        if not any(isinstance(h, RotatingFileHandler) for h in u_logger.handlers):
            u_logger.addHandler(file_handler)

    # Silence Uvicorn's noisy file-watcher spam
    logging.getLogger("watchfiles.main").setLevel(logging.WARNING)
