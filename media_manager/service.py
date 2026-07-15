from sqlalchemy.orm import Session
from sqlalchemy import text
import os
from typing import Optional, Dict, Any


def _calculate_file_size_mb(file_path: str) -> Optional[float]:
    """
    Calculate file size in MB with fractional value.
    Returns None if file does not exist.
    """
    try:
        size_bytes = os.path.getsize(file_path)
        return size_bytes / (1024 * 1024)
    except (OSError, FileNotFoundError):
        return None


def upsert_media_for_marketing(
    db: Session,
    *,
    marketing_id: int,
    file_path: str,
    folder: str,
) -> Dict[str, Any]:
    """
    Store a single cover image record for a marketing / announcement row
    in the media_manager table.

    Strategy:
    - Remove any existing media_manager rows for this (folder, reference_id)
    - Insert a new row for the current file
    - Return the inserted row as a dict
    """
    if not file_path:
        raise ValueError("file_path is required for upsert_media_for_marketing")

    name = os.path.basename(file_path)
    ext = os.path.splitext(name)[1]
    file_type = ext[1:].lower() if ext.startswith(".") else ext.lower()
    file_size = _calculate_file_size_mb(file_path)

    db_path = file_path

    db.execute(
        text(
            """
            DELETE FROM media_manager
            WHERE folder = :folder AND reference_id = :ref_id
            """
        ),
        {"folder": folder, "ref_id": marketing_id},
    )

    insert_sql = text(
        """
        INSERT INTO media_manager (
            folder,
            name,
            path,
            module_name,
            reference_id,
            file_type,
            file_size,
            created_at,
            updated_at
        ) VALUES (
            :folder,
            :name,
            :path,
            :module_name,
            :reference_id,
            :file_type,
            :file_size,
            NOW(),
            NOW()
        )
        """
    )

    params = {
        "folder": folder,
        "name": name,
        "path": db_path,
        "module_name": name,
        "reference_id": marketing_id,
        "file_type": file_type,
        "file_size": file_size,
    }

    db.execute(insert_sql, params)

    media_id = db.execute(text("SELECT LAST_INSERT_ID() AS id")).scalar()
    row = db.execute(
        text("SELECT * FROM media_manager WHERE id = :id"),
        {"id": media_id},
    ).mappings().first()

    db.commit()

    return dict(row) if row is not None else {
        "id": media_id,
        "folder": folder,
        "name": name,
        "path": db_path,
        "module_name": name,
        "reference_id": marketing_id,
        "file_type": file_type,
        "file_size": file_size,
    }

