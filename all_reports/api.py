from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text, or_
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional, List, Dict, Any
from DB.db import get_db
import traceback
from .service import (
    format_activity_log,
    generate_activity_logs_excel_response,
    generate_activity_logs_pdf_response,
    list_visitors_service,
    generate_visitors_excel_response,
    generate_visitors_pdf_response,
)

import json

router = APIRouter()

@router.get("/activity_logs")
def list_activity_logs(
    searchdata: Optional[str] = Query(None, description="Search in module_name, event_type, description, role, created_by"),
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    from_date: Optional[str] = Query(None, description="Filter from this date (YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="Filter to this date (YYYY-MM-DD)"),
    module: Optional[str] = Query(None, description="Filter by module name"),
    event_type: Optional[str] = Query(None, description="Filter by event type/action"),
    download: bool = Query(False, description="Set to true to download as Excel or PDF"),
    download_type: Optional[str] = Query('excel', description="Download format: 'excel' or 'pdf'"),
    db: Session = Depends(get_db)
):
    try:
        base_query = """
            SELECT * FROM activity_logs
        """
        
        count_query = """
            SELECT COUNT(*) as total_count FROM activity_logs
        """
        
        filters = []
        params = {}
        
        if from_date:
            filters.append("DATE(created_at) >= :from_date")
            params["from_date"] = from_date
            
        if to_date:
            filters.append("DATE(created_at) <= :to_date")
            params["to_date"] = to_date
        
        if module:
            filters.append("module_name = :module")
            params["module"] = module
        
        if event_type:
            filters.append("action = :event_type")
            params["event_type"] = event_type
        
        if searchdata:
            search_filter = """
                (module_name LIKE :search 
                OR action LIKE :search 
                OR description LIKE :search
                OR created_by LIKE :search)
            """
            filters.append(search_filter)
            params["search"] = f"%{searchdata}%"
        
        if filters:
            where_clause = " WHERE " + " AND ".join(filters)
            base_query += where_clause
            count_query += where_clause
        
        base_query += " ORDER BY id DESC"
        
        total_count = db.execute(text(count_query), params).scalar() or 0

        if download:
            result = db.execute(text(base_query), params)
        else:
            offset = (page - 1) * per_page
            paginated_query = base_query + " LIMIT :limit OFFSET :offset"
            params["limit"] = per_page
            params["offset"] = offset
            result = db.execute(text(paginated_query), params)

        raw_results = result.mappings().all()
        
        user_emails = set()
        user_ids = set()
        formatted_results = []
        
        for row in raw_results:
            record = dict(row)
            
            if record.get('new_data') and isinstance(record['new_data'], str):
                try:
                    record['new_data'] = json.loads(record['new_data'])
                except:
                    record['new_data'] = {}
            
            new_data = record.get('new_data', {})
            email = None
            
            if isinstance(new_data, dict):
                if 'creator_info' in new_data:
                    email = new_data['creator_info'].get('creator_email')
                elif 'updator_info' in new_data:
                    email = new_data['updator_info'].get('updator_email')
            
            if email and email != "system@example.com":
                user_emails.add(email)
            if record.get("user_id") is not None:
                user_ids.add(record.get("user_id"))
            
            formatted_results.append({
                'record': record,
                'email': email
            })
        
        user_details = {}
        user_details_by_id = {}
        if user_emails:
            email_list = list(user_emails)
            placeholders = ','.join([':email' + str(i) for i in range(len(email_list))])
            query = f"""
                SELECT u.email, u.name, u.role_id, r.title as role_name
                FROM users u
                LEFT JOIN roles r ON u.role_id = r.id
                WHERE u.email IN ({placeholders})
            """
            
            user_params = {}
            for i, email in enumerate(email_list):
                user_params[f'email{i}'] = email
            
            users_result = db.execute(text(query), user_params).mappings().all()
            for user in users_result:
                user_details[user['email']] = {
                    'name': user['name'],
                    'role_id': user.get('role_id'),
                    'role_name': user.get('role_name')
                }
        
        if user_ids:
            id_list = list(user_ids)
            placeholders = ','.join([':uid' + str(i) for i in range(len(id_list))])
            query_by_id = f"""
                SELECT u.id, u.email, u.name, u.role_id, r.title as role_name
                FROM users u
                LEFT JOIN roles r ON u.role_id = r.id
                WHERE u.id IN ({placeholders})
            """
            id_params = {}
            for i, uid in enumerate(id_list):
                id_params[f'uid{i}'] = uid
            users_by_id_result = db.execute(text(query_by_id), id_params).mappings().all()
            for user in users_by_id_result:
                user_details_by_id[user['id']] = {
                    'email': user.get('email'),
                    'name': user.get('name'),
                    'role_id': user.get('role_id'),
                    'role_name': user.get('role_name')
                }
        
        final_results = []
        for item in formatted_results:
            record = item['record']
            email = item['email']
            
            user_detail = user_details.get(email) if email else None
            
            formatted_log = format_activity_log(record)
            
            # Fallback to lookup by user_id when email is missing/system.
            if not user_detail and record.get("user_id") in user_details_by_id:
                user_detail = user_details_by_id[record.get("user_id")]

            if user_detail:
                if user_detail['name']:
                    formatted_log['created_by'] = user_detail['name']
                if user_detail['role_name']:
                    formatted_log['role'] = user_detail['role_name']
                elif user_detail['role_id']:
                    role_map = {
                        1: "Super Admin",
                        2: "Security",
                        3: "Manager",
                        4: "Conceirge"
                    }
                    formatted_log['role'] = role_map.get(user_detail['role_id'], "Unknown")
                if formatted_log.get('actor_email') in (None, "", "system@example.com"):
                    if user_detail.get('email'):
                        formatted_log['actor_email'] = user_detail.get('email')
            
            if email and email.lower() == "bmoadmin@yopmail.com" and formatted_log['role'] == "Unknown":
                formatted_log['role'] = "BMO ADMIN"
                if formatted_log['created_by'] == "Unknown":
                    formatted_log['created_by'] = "BMO Admin"
            
            final_results.append(formatted_log)

        if download:
            filename_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            if (download_type or "").lower() == "pdf":
                return generate_activity_logs_pdf_response(
                    final_results,
                    f"activity_logs_{filename_ts}.pdf",
                )
            return generate_activity_logs_excel_response(
                final_results,
                f"activity_logs_{filename_ts}.xlsx",
            )
        
        last_page = (total_count + per_page - 1) // per_page if total_count > 0 else 1
        
        return {
            "status": 200,
            "message": "Activity logs retrieved successfully",
            "data": final_results,
            "pagination_details": {
                "page": page,
                "per_page": per_page,
                "total": total_count,
                "last_page": last_page
            }
        }
        
    except Exception as e:
        print(f"Error in list_activity_logs: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to retrieve activity logs: {str(e)}")
    
@router.get("/list_visitors")
def list_visitors(
    id: Optional[int] = Query(None, description="Get a specific visitor record by ID"),
    visitor_id: Optional[str] = Query(None, description="Get visitor by visitor_id"),
    visitor_type: Optional[str] = Query(None, description="Filter by type: 'adoc' or 'invite'"),
    search: Optional[str] = Query(None, description="Search by name, phone, or purpose"),
    building_id: Optional[int] = Query(None, description="Filter by building ID"),
    level_id: Optional[int] = Query(None, description="Filter by level ID"),
    unit_id: Optional[int] = Query(None, description="Filter by unit ID"),
    is_qr_valid: Optional[bool] = Query(None, description="Filter by QR validity (true/false)"),
    start_date: Optional[str] = Query(None, description="Start date filter (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date filter (YYYY-MM-DD)"),
    download: bool = Query(False, description="Set to true to download as Excel or PDF"),
    download_type: Optional[str] = Query('excel', description="Download format: 'excel' or 'pdf'"),
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    try:
        from_dt = datetime.strptime(start_date, "%Y-%m-%d") if start_date else None
        to_dt = datetime.strptime(end_date, "%Y-%m-%d") if end_date else None

        # normalize visitor_type
        if visitor_type and visitor_type.strip().lower() in ["null", "none", "all", ""]:
            visitor_type = None

        final_results, total_count = list_visitors_service(
            db=db,
            id=id,
            visitor_id=visitor_id,
            visitor_type=visitor_type,
            search=search,
            building_id=building_id,
            level_id=level_id,
            unit_id=unit_id,
            is_qr_valid=is_qr_valid,
            start_date=from_dt,
            end_date=to_dt,
            page=page,
            record_count=per_page,
            download=download,
        )

        if download:
            filename_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            if (download_type or "").lower() == "pdf":
                return generate_visitors_pdf_response(
                    final_results,
                    f"visitors_{filename_ts}.pdf",
                )
            return generate_visitors_excel_response(
                final_results,
                f"visitors_{filename_ts}.xlsx",
            )

        last_page = (total_count + per_page - 1) // per_page if total_count else 0

        return {
            "status": 200,
            "message": "Visitors retrieved successfully." if final_results else "No records found.",
            "data": final_results,
            "pagination_details": {
                "page": page,
                "per_page": per_page,
                "total": total_count,
                "last_page": last_page
            },
            "filter_info": {
                "visitor_type": visitor_type,
                "search": search,
                "building_id": building_id,
                "level_id": level_id,
                "unit_id": unit_id,
                "is_qr_valid": is_qr_valid,
                "start_date": start_date,
                "end_date": end_date
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))