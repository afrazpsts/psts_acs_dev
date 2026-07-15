import datetime
import os
import sys
import pytz
import logging

# Configure standard logging as fallback
logging.basicConfig(level=logging.INFO)
standard_logger = logging.getLogger("vms_logger")

SG_TIMEZONE = pytz.timezone("Asia/Singapore")

if getattr(sys, 'frozen', False):
    base_dir = os.path.dirname(sys.executable)
else:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

log_file_path = os.path.join(base_dir, 'server_logs.txt')

def log(message):
    standard_logger.info(message) 
    try:
        with open(log_file_path, "a+", encoding="utf-8") as log_file:
            timestamp = datetime.datetime.now(SG_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")
            log_file.write(f"{message} ------------ {timestamp}\n")
            log_file.flush()
            try:
                os.fsync(log_file.fileno())
            except:
                pass
    except Exception as e:
        standard_logger.error(f"Failed to write log to file: {e}")
        print(f"Failed to write log: {e}")
