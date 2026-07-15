from fastapi import Request
from sqlalchemy.orm import Session
from sqlalchemy import text
import json
from datetime import datetime, date
from typing import Any

class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle datetime objects"""
    def default(self, obj: Any) -> Any:
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)

def log_activity(
    db: Session,
    user_id: int,
    action: str,
    module_name: str,
    record_id: str = None,
    description: str = "",
    old_data: dict = None,
    new_data: dict = None,
    ip_address: str = None
):
    """
    Simple function to log any activity
    
    Parameters:
    - db: Database session
    - user_id: Who performed the action
    - action: CREATE, UPDATE, DELETE, etc.
    - module_name: Which table was affected
    - record_id: ID of the record
    - description: What happened
    - old_data: Data before change
    - new_data: Data after change
    - ip_address: Client IP address
    """
    
    try:
        serialized_old_data = None
        if old_data:
            serialized_old_data = json.dumps(old_data, cls=DateTimeEncoder)
        
        serialized_new_data = None
        if new_data:
            serialized_new_data = json.dumps(new_data, cls=DateTimeEncoder)
        
        db.execute(
            text("""
                INSERT INTO activity_logs 
                (user_id, action, module_name, record_id, description, old_data, new_data, ip_address, created_at)
                VALUES (:user_id, :action, :module_name, :record_id, :description, :old_data, :new_data, :ip_address, NOW())
            """),
            {
                "user_id": user_id,
                "action": action,
                "module_name": module_name,
                "record_id": str(record_id) if record_id else None,
                "description": description,
                "old_data": serialized_old_data,
                "new_data": serialized_new_data,
                "ip_address": ip_address
            }
        )
        db.commit()
        return True
        
    except Exception as e:
        print(f"Error logging activity: {e}")
        db.rollback()
        return False