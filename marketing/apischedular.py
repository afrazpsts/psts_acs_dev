from datetime import date
from sqlalchemy import text
from sqlalchemy.orm import Session
from DB.db import SessionLocal

def update_marketing_status():
    db: Session = SessionLocal()
    try:
        today = date.today()

        db.execute(text("""
            UPDATE marketing
            SET status_id = 1, updated_at = NOW()
            WHERE status_id = 3
              AND start_date IS NOT NULL
              AND start_date <= :today
        """), {"today": today})

        db.execute(text("""
            UPDATE marketing
            SET status_id = 5, updated_at = NOW()
            WHERE status_id = 1
              AND end_date IS NOT NULL
              AND end_date < :today
        """), {"today": today})

        db.commit()
        print(f"[{today}] Marketing status updated successfully.")
    except Exception as e:
        db.rollback()
        print("Error in cron job:", str(e))
    finally:
        db.close()
