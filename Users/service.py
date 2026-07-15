import random
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from datetime import datetime, timedelta, timezone
from DB.db import SessionLocal
from fastapi import APIRouter, HTTPException, Depends
from utils.security import hash_password, create_access_token, create_refresh_token, verify_password
from sqlalchemy.orm import Session
from common.logger import log
import bcrypt
from Users.models import AuthUser
from utils.mailjet_service import send_onboarding_email, send_otp_email 
from utils.common_function import format_date_ddmmyyyy, generate_otp
from typing import Optional,Any

router = APIRouter()

def initialize_users_table():
    db = SessionLocal()
    try:
        check_user_sql = text("SELECT COUNT(*) FROM users")
        result = db.execute(check_user_sql)
        count = result.scalar()

        if count == 0:
            default_name = "Super Admin"
            default_email = "admin@yopmail.com"
            default_password = hash_password("admin123")

            insert_sql = text("""
                INSERT INTO users (name, email, password, role_id, is_verified) 
                VALUES (:name, :email, :password, :role_id, :is_verified)
            """)
            db.execute(insert_sql, {
                "name": default_name,
                "email": default_email, 
                "password": default_password,
                "role_id": "1",
                "is_verified": 1
            })
            db.commit()
            print("Default admin user created successfully.")
        else:
            print("Users table already has data. Skipping insert.")

    except ProgrammingError as e:
        print("SQL Error:", e)
    finally:
        db.close()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/login")
async def login(user: AuthUser, db: Session = Depends(get_db)):
    try:
        log(["API", "POST /login"])

        result = db.execute(
            text("SELECT * FROM users WHERE email = :email"), 
            {"email": user.email}
        )
        row = result.fetchone()

        if not row:
            log("Invalid email or password")
            raise HTTPException(status_code=401, detail="Invalid email or password")

        column_names = [desc[0] for desc in result.cursor.description]
        
        user_data = dict(zip(column_names, row))
        
        stored_password_hash = user_data.get("password")
        stored_salt = user_data.get("salt")

        if not user_data.get("is_verified"):
            log(f"Account not verified: {user.email}")
            raise HTTPException(
                status_code=401, 
                detail="Account not verified. Please verify your email first."
            )

        try:
            from utils.security import rsa_decrypt_password
            decrypted_password = rsa_decrypt_password(user.password)
            log(f"Password decrypted successfully for {user.email}")
        except Exception as decrypt_error:
            log(f"Failed to decrypt password: {str(decrypt_error)}")
            raise HTTPException(status_code=400, detail="Invalid encrypted password format")

        password_valid = False
        if stored_salt:
            from utils.security import verify_password_with_salt
            password_valid = verify_password_with_salt(decrypted_password, stored_salt, stored_password_hash)
        else:
            from utils.security import verify_password
            password_valid = verify_password(decrypted_password, stored_password_hash)

        if not password_valid:
            log("Invalid email or password")
            raise HTTPException(status_code=401, detail="Invalid email or password")

        access_token, expires_at, issued_at = create_access_token(data={"sub": user.email})
        refresh_token = create_refresh_token(data={"sub": user.email})

        user_details = {
            "id": row[0],  
            "name": row[1],  
            "email": row[2],  
            "email_verified_at": "2025-06-26T04:40:36.000000Z",
            "user_role": 2,
            "update_password": 1,
            "status": 1,
            "created_at": row[11] if len(row) > 11 else "2025-06-26T04:06:25.000000Z",  
            "updated_at": row[12] if len(row) > 12 else "2025-06-30T06:15:15.000000Z",  
            "deleted_at": "null",
            "ts_ref_id": "null",
            "ts_access_code": "null",
            "user_role_details": {
                "id": 2,
                "key": "condo-admin",
                "role_name": "Condo admin"
            },
            "access_details": {
                "id": 339,
                "user_id": 372,
                "onboarded_by": "null",
                "property_id": 107,
                "residency_type_id": "null",
                "department_id": "null",
                "role_id": "null",
                "building_id": "null",
                "level_id": "null",
                "unit_id": "null",
                "join_date": "2025-06-26",
                "leaving_date": "null",
                "access_start": "2025-06-26 04:06:25",
                "access_end": "null",
                "offboard_by_id": "null",
                "status_id": 1,
                "created_at": "2025-06-26T04:06:25.000000Z",
                "updated_at": "2025-06-26T04:06:25.000000Z",
                "department_details": "null"
            }
        }

        property_status = {
            "id": "107",
            "title": "East Coast Business Park",
            "slug": "east-coast-business-park",
            "type": {
                "id": "1",
                "name": "Residential"
            },
            "project_developer": "null",
            "completion_year": "2026",
            "tenure_year": 3,
            "total_units": "100",
            "name": "Daniel March",
            "email": "wongdanie@yopmail.com",
            "phone": "45646546",
            "country_code": "+65",
            "address": "12 Bukit Timah Road",
            "country": "Singapore",
            "city": "Kallang",
            "zipcode": "234324",
            "description": "Best Place to live",
            "property_logo": "storage/property_logo/1750914856.jpg",
            "cover_image": "storage/cover_image/1750914856.jpg",
            "status": "inactive",
            "completed_step": 6,
            "company_id": 7,
            "created_by": 1,
            "created_at": "2025-06-26T04:06:24.000000Z",
            "updated_at": "2025-06-30T06:17:42.000000Z",
            "deleted_at": None
        }

        return {
            "success": True,
            "message": "Login successful",
            "data": {
                "token": {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "token_type": "bearer",
                    "expires_in": 31536000,
                    "issued_at": issued_at,            
                    "expires_at": expires_at,        
                    "is_token_valid": issued_at < expires_at
                },
                "user_details": user_details,
                "property_status": property_status
            }
        }

    except HTTPException as e:
        raise e
    except Exception as e:
        log(f"[API Exception] Login failed: {e}")
        import traceback
        log(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


def create_user_service(
    name: str,
    email: str,
    phone: str,
    password: str,
    company_id: str,
    role_id: str,
    is_verified: bool,
    otp: str,
    otp_expiry: str,
    created_by: str,
    sub_user_role: str,
    is_user_active: str,
    on_board_date: str,
    off_board_date: str,
    db: Session
):
    try:
        if email:
            existing = db.execute(
                text("SELECT id FROM users WHERE email = :email"),
                {"email": email}
            ).fetchone()
            
            if existing:
                raise Exception("User with this email already exists")
        
        hashed_password = None
        if password:
            salt = bcrypt.gensalt()
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
        
        is_verified_int = 1 if is_verified else 0
        
        db.execute(text("""
            INSERT INTO users (
                name, email, phone, password, company_id, role_id,
                is_verified, otp, otp_expiry, created_by, sub_user_role,
                is_user_active, on_board_date, off_board_date, created_at, updated_at
            ) VALUES (
                :name, :email, :phone, :password, :company_id, :role_id,
                :is_verified, :otp, :otp_expiry, :created_by, :sub_user_role,
                :is_user_active, :on_board_date, :off_board_date, NOW(), NOW()
            )
        """), {
            "name": name,
            "email": email,
            "phone": phone,
            "password": hashed_password,
            "company_id": company_id,
            "role_id": role_id,
            "is_verified": is_verified_int,
            "otp": otp,
            "otp_expiry": otp_expiry,
            "created_by": created_by,
            "sub_user_role": sub_user_role,
            "is_user_active": is_user_active,
            "on_board_date": on_board_date,
            "off_board_date": off_board_date
        })
        
        db.commit()
        
        if email:
            result = db.execute(
                text("SELECT * FROM users WHERE email = :email"),
                {"email": email}
            ).mappings().first()
        else:
            result = db.execute(
                text("SELECT * FROM users ORDER BY id DESC LIMIT 1")
            ).mappings().first()
        
        if result:
            result = dict(result)
            result.pop("password", None)
            result.pop("otp", None)
        
        try:
            building_name = "PSTS Access Control" 
            send_onboarding_email(
                email, name, building_name,
                on_board_date=format_date_ddmmyyyy(on_board_date) if on_board_date else None,
                off_board_date=format_date_ddmmyyyy(off_board_date) if off_board_date else None
            )
            log(f"Onboarding email sent successfully to {email}")
        except Exception as email_error:
            log(f"Failed to send onboarding email to {email}: {str(email_error)}")
        
        return result
        
    except Exception as e:
        db.rollback()
        raise Exception(str(e))

def parse_date(date_str):
    """Helper function to parse date strings"""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except:
        return None

def send_otp_service(email: str, db: Session):
    """
    Service to send OTP with all validations
    """
    try:
        log(f"Looking up email: {email}")
        
        user_result = db.execute(
            text("""
                SELECT id, name, email, is_verified, on_board_date, off_board_date,
                       company_id
                FROM users 
                WHERE email = :email
            """),
            {"email": email}
        ).mappings().first()
        
        if not user_result:
            log(f"Email not found in database: {email}")
            log(f"Available emails in DB: admin@yopmail.com, afraz.psts@gmail.com")
            raise HTTPException(
                status_code=404,
                detail="Email does not exist in our records. Please check the email or sign up first."
            )
        
        user = dict(user_result)
        log(f"User found: ID={user.get('id')}, Name={user.get('name')}, Verified={user.get('is_verified')}")
        
        current_date = datetime.now().date()
        
        if user.get("is_verified") == 1:
            log(f"Account already verified: {email}")
            raise HTTPException(
                status_code=400,
                detail="Account already verified. Please login."
            )
        
        if user.get("off_board_date") and user["off_board_date"] != "NULL" and user["off_board_date"] is not None:
            off_board_date_obj = parse_date(user["off_board_date"])
            if off_board_date_obj and current_date > off_board_date_obj.date():
                formatted_offboard_date = off_board_date_obj.strftime("%d-%m-%Y")
                log(f"Access expired for {email} on {formatted_offboard_date}")
                raise HTTPException(
                    status_code=403,
                    detail=f"Your access has expired (off-board date: {formatted_offboard_date}). Please contact administrator."
                )
        
        if user.get("on_board_date") and user["on_board_date"] != "NULL" and user["on_board_date"] is not None:
            on_board_date_obj = parse_date(user["on_board_date"])
            if on_board_date_obj and current_date < on_board_date_obj.date():
                formatted_onboard_date = on_board_date_obj.strftime("%d-%m-%Y")
                log(f"Access not started for {email}, starts on {formatted_onboard_date}")
                raise HTTPException(
                    status_code=403,
                    detail=f"Your access is scheduled to start on {formatted_onboard_date}. Please try signing up after that date."
                )
        
        otp = generate_otp()
        otp_expiry = (datetime.now() + timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")
        
        log(f"Generated OTP: {otp} for {email}, expires at {otp_expiry}")
        
        db.execute(
            text("""
                UPDATE users 
                SET otp = :otp, otp_expiry = :otp_expiry, updated_at = NOW()
                WHERE email = :email
            """),
            {
                "otp": otp,
                "otp_expiry": otp_expiry,
                "email": email
            }
        )
        db.commit()
        log(f"OTP updated in database for {email}")
        
        try:
            user_name = user.get("name", "User")
            email_sent = send_otp_email(email, user_name, otp, resend=False)
            if email_sent:
                log(f"OTP email sent successfully to {email}")
            else:
                log(f"Failed to send OTP email to {email} - email service returned None")
        except Exception as email_error:
            log(f"Failed to send OTP email to {email}: {str(email_error)}")
        
        return {
            "success": True,
            "email": email,
            "message": "OTP sent successfully",
            "expiry_minutes": 15
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        db.rollback()
        log(f"Error in send_otp_service: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    
def verify_user_otp(db: Session, email: str, otp: str):
    """
    Verify OTP for user without marking as verified.
    Only validates OTP and clears it after successful verification.
    """
    try:
        log(f"Verifying OTP for email: {email}")
        table = "users"
        
        record = db.execute(
            text(f"""
                SELECT id, name, email, password, is_verified, otp, otp_expiry
                FROM {table} 
                WHERE email = :email
            """),
            {"email": email}
        ).mappings().first()
        
        if not record:
            log(f"Account not found for email: {email}")
            raise HTTPException(
                status_code=404,
                detail="Account not found for this email. Please sign up first."
            )
        
        record = dict(record)
        log(f"User found: ID={record['id']}, Verified={record['is_verified']}")
        
        if record.get("otp") is None or record.get("otp_expiry") is None:
            log(f"No OTP found for email: {email}. Please request a new OTP.")
            raise HTTPException(
                status_code=400,
                detail="No valid OTP found. Please request a new OTP using the /sending_otp endpoint."
            )
        
        if record.get("password") and record["password"] is not None:
            log(f"Account already has password set: {email}")
            raise HTTPException(
                status_code=400,
                detail="Account already has password set. Please sign in."
            )
        
        current_time = datetime.now()
        otp_expiry_value = record.get("otp_expiry")
        
        log(f"Current time: {current_time}")
        log(f"OTP expiry from DB: {otp_expiry_value}")
        
        try:
            if isinstance(otp_expiry_value, str):
                otp_expiry = datetime.strptime(otp_expiry_value, "%Y-%m-%d %H:%M:%S")
            elif isinstance(otp_expiry_value, datetime):
                otp_expiry = otp_expiry_value
            else:
                log(f"Invalid OTP expiry type: {type(otp_expiry_value)}")
                raise HTTPException(
                    status_code=400,
                    detail="Invalid OTP format. Please request a new OTP."
                )
            
            log(f"Parsed OTP expiry: {otp_expiry}")
            
            if current_time > otp_expiry:
                log(f"OTP expired for {email}. Expiry: {otp_expiry}, Current: {current_time}")
                
                db.execute(
                    text(f"""
                        UPDATE {table}
                        SET otp = NULL, otp_expiry = NULL, updated_at = NOW()
                        WHERE id = :id
                    """),
                    {"id": record["id"]}
                )
                db.commit()
                
                raise HTTPException(
                    status_code=400,
                    detail="OTP has expired. Please request a new OTP."
                )
                
        except ValueError as ve:
            log(f"Error parsing OTP expiry: {str(ve)}")
            raise HTTPException(
                status_code=400,
                detail="Invalid OTP expiry format. Please request a new OTP."
            )
        
        if str(record["otp"]) != str(otp):
            log(f"Invalid OTP for {email}. Provided: {otp}, Expected: {record['otp']}")
            raise HTTPException(
                status_code=400,
                detail="Invalid OTP. Please check and try again."
            )
        
        db.execute(
            text(f"""
                UPDATE {table}
                SET otp = NULL, 
                    otp_expiry = NULL, 
                    updated_at = NOW()
                WHERE id = :id
            """),
            {"id": record["id"]}
        )
        db.commit()
        
        log(f"OTP verified successfully for {email}. User ID: {record['id']}. OTP cleared. User can now set password.")
        
        return {
            "success": True,
            "status": 200,
            "message": "OTP verified successfully. You can now set your password.",
            "data": {
                "table": table,
                "id": record["id"],
                "email": email,
                "name": record.get("name"),
                "is_verified": 0,  
                "next_step": "set_password"
            }
        }

    except HTTPException as he:
        db.rollback()
        raise he
    except Exception as e:
        db.rollback()
        log(f"Unexpected error in OTP verification for {email}: {str(e)}")
        import traceback
        log(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"OTP verification failed: {str(e)}")
    

def set_user_password(db: Session, email: str, password: str):
    """
    Set password for user after OTP verification.
    Also marks the user as verified.
    Checks if OTP was verified (otp should be NULL).
    """
    try:
        log(f"Setting password for email: {email}")
        table = "users"
        
        record = db.execute(
            text(f"""
                SELECT id, name, email, password, is_verified, otp, salt
                FROM {table} 
                WHERE email = :email
            """),
            {"email": email}
        ).mappings().first()
        
        if not record:
            log(f"Account not found for email: {email}")
            raise HTTPException(
                status_code=404,
                detail="Account not found for this email. Please sign up first."
            )
        
        record = dict(record)
        log(f"User found: ID={record['id']}, Current verified status: {record['is_verified']}")
        
        if record.get("password") and record["password"] is not None:
            log(f"Password already set for email: {email}")
            raise HTTPException(
                status_code=400,
                detail="Password already set. Please login or use forgot password."
            )
        
        if record.get("otp") is not None:
            log(f"OTP not verified yet for email: {email}. OTP still present: {record['otp']}")
            raise HTTPException(
                status_code=400,
                detail="OTP not verified yet. Please verify OTP first."
            )
        
        from utils.security import hash_password_with_salt, generate_salt
        
        salt = generate_salt()
        
        hashed_password = hash_password_with_salt(password, salt)
        
        db.execute(
            text(f"""
                UPDATE {table} 
                SET password = :password, 
                    salt = :salt,
                    is_verified = 1, 
                    updated_at = NOW() 
                WHERE email = :email
            """),
            {
                "password": hashed_password, 
                "salt": salt,
                "email": email
            }
        )
        db.commit()
        
        log(f"Password set successfully for email: {email}. User ID: {record['id']}")
        
        updated_user = db.execute(
            text(f"""
                SELECT id, name, email, is_verified, company_id, role_id,
                       sub_user_role, is_user_active, on_board_date, off_board_date
                FROM {table}
                WHERE id = :id
            """),
            {"id": record["id"]}
        ).mappings().first()
        
        return {
            "success": True,
            "status": 200,
            "message": "Password set successfully. You can now login.",
            "data": {
                "id": record["id"],
                "email": email,
                "name": record.get("name"),
                "is_verified": 1,
                "next_step": "login"
            }
        }
        
    except HTTPException as he:
        db.rollback()
        raise he
    except Exception as e:
        db.rollback()
        log(f"Unexpected error in set_password for {email}: {str(e)}")
        import traceback
        log(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Password setup failed: {str(e)}")

def get_user_by_id_service(user_id: int, db: Session):
    try:
        result = db.execute(
            text("SELECT * FROM users WHERE id = :user_id"),
            {"user_id": user_id}
        ).mappings().first()
        
        if result:
            result = dict(result)
            result.pop("password", None)
            result.pop("otp", None)
        
        return result
        
    except Exception as e:
        raise Exception(str(e))

def get_user_by_email_service(email: str, db: Session):
    try:
        result = db.execute(
            text("SELECT * FROM users WHERE email = :email"),
            {"email": email}
        ).mappings().first()
        
        if result:
            result = dict(result)
            result.pop("password", None)
            result.pop("otp", None)
        
        return result
        
    except Exception as e:
        raise Exception(str(e))

def update_user_service(user_id: int, update_data: dict, db: Session):
    try:
        update_fields = []
        params = {"user_id": user_id}
        
        updatable_fields = [
            "name", "email", "phone", "company_id", "role_id",
            "sub_user_role", "is_user_active", "on_board_date", "off_board_date",
            "is_verified",
        ]
        
        if "password" in update_data and update_data["password"]:
            salt = bcrypt.gensalt()
            hashed_password = bcrypt.hashpw(update_data["password"].encode('utf-8'), salt).decode('utf-8')
            update_fields.append("password = :password")
            params["password"] = hashed_password
        
        if "email" in update_data and update_data["email"]:
            existing = db.execute(
                text("SELECT id FROM users WHERE email = :email AND id != :user_id"),
                {"email": update_data["email"], "user_id": user_id}
            ).fetchone()
            
            if existing:
                raise Exception("Email already exists for another user")
        
        for field in updatable_fields:
            if field in update_data:
                val = update_data[field]
                if field == "is_verified" and val is not None:
                    if isinstance(val, bool):
                        val = 1 if val else 0
                    elif isinstance(val, str) and val.lower() in ("true", "false"):
                        val = 1 if val.lower() == "true" else 0
                update_fields.append(f"{field} = :{field}")
                params[field] = val
        
        if not update_fields:
            return get_user_by_id_service(user_id, db)
        
        update_fields.append("updated_at = NOW()")
        
        update_query = f"""
            UPDATE users 
            SET {', '.join(update_fields)}
            WHERE id = :user_id
        """
        
        db.execute(text(update_query), params)
        db.commit()
        
        result = get_user_by_id_service(user_id, db)
        
        return result
        
    except Exception as e:
        db.rollback()
        raise Exception(str(e))

def delete_user_service(user_id: int, db: Session):
    try:
        db.execute(
            text("""
                UPDATE users 
                SET is_user_active = 'false', updated_at = NOW() 
                WHERE id = :user_id
            """),
            {"user_id": user_id}
        )
        
        db.commit()
        
        return {"id": user_id, "deleted": True}
        
    except Exception as e:
        db.rollback()
        raise Exception(str(e))

def list_users_service(
    db: Session,
    user_id: Optional[int] = None,
    searchdata: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    company_id: Optional[str] = None,
    role_id: Optional[str] = None,
    is_user_active: Optional[str] = None,
    is_verified: Optional[int] = None,
    page: int = 1,
    per_page: int = 10,
    exclude_super_admin: bool = True  
):
    """
    Service function to list users with filters and pagination
    If user_id is provided, returns only that specific user
    Includes role information from roles table and menu permissions
    """
    try:
        base_query = """
            SELECT u.*, 
                   r.title as role_name,
                   creator.name as created_by_name
            FROM users u
            LEFT JOIN roles r ON CAST(u.role_id AS UNSIGNED) = r.id
            LEFT JOIN users creator ON u.created_by = creator.id
            WHERE 1=1
        """
        
        count_query = """
            SELECT COUNT(DISTINCT u.id) as total
            FROM users u
            LEFT JOIN roles r ON CAST(u.role_id AS UNSIGNED) = r.id
            WHERE 1=1
        """
        
        params = {}
        
        # Filter by specific user ID if provided
        if user_id is not None:
            base_query += " AND u.id = :user_id"
            count_query += " AND u.id = :user_id"
            params["user_id"] = user_id
        
        # Exclude Super Admin (role_id = 1) if flag is True and not filtering by specific user
        if exclude_super_admin and user_id is None:
            base_query += " AND u.role_id != 1"
            count_query += " AND u.role_id != 1"
        
        if is_user_active == "null" or is_user_active == "None":
            is_user_active = None
        
        if searchdata:
            search_condition = """
                AND (
                    u.name LIKE :search 
                    OR u.email LIKE :search 
                    OR u.phone LIKE :search
                    OR u.sub_user_role LIKE :search
                    OR u.company_id LIKE :search
                    OR u.role_id LIKE :search
                    OR r.title LIKE :search
                    OR CAST(u.id AS CHAR) LIKE :search
                )
            """
            base_query += search_condition
            count_query += search_condition
            params["search"] = f"%{searchdata}%"
        
        if from_date:
            base_query += " AND DATE(u.created_at) >= :from_date"
            count_query += " AND DATE(u.created_at) >= :from_date"
            params["from_date"] = from_date
            
        if to_date:
            base_query += " AND DATE(u.created_at) <= :to_date"
            count_query += " AND DATE(u.created_at) <= :to_date"
            params["to_date"] = to_date
        
        if company_id:
            base_query += " AND u.company_id = :company_id"
            count_query += " AND u.company_id = :company_id"
            params["company_id"] = company_id
            
        if role_id:
            base_query += " AND u.role_id = :role_id"
            count_query += " AND u.role_id = :role_id"
            params["role_id"] = role_id
            
        if is_user_active is not None:
            base_query += " AND u.is_user_active = :is_user_active"
            count_query += " AND u.is_user_active = :is_user_active"
            params["is_user_active"] = is_user_active
            
        if is_verified is not None:
            base_query += " AND u.is_verified = :is_verified"
            count_query += " AND u.is_verified = :is_verified"
            params["is_verified"] = is_verified
        
        count_result = db.execute(text(count_query), params).first()
        total_count = count_result[0] if count_result else 0
        
        # If specific user_id is provided and no user found, return empty result
        if user_id is not None and total_count == 0:
            return {
                "users": [],
                "total": 0,
                "page": page,
                "per_page": per_page,
                "total_pages": 0
            }
        
        offset = (page - 1) * per_page
        base_query += " ORDER BY u.id DESC LIMIT :limit OFFSET :offset"
        params["limit"] = per_page
        params["offset"] = offset
        
        result = db.execute(text(base_query), params).mappings().all()
        
        users_list = []
        for user in result:
            user_dict = dict(user)
            user_dict.pop("password", None)
            user_dict.pop("otp", None)
            user_dict.pop("salt", None)
            
            # Convert is_user_active from string to boolean
            if "is_user_active" in user_dict:
                if isinstance(user_dict["is_user_active"], str):
                    user_dict["is_user_active"] = user_dict["is_user_active"].lower() == "true"
                elif isinstance(user_dict["is_user_active"], int):
                    user_dict["is_user_active"] = bool(user_dict["is_user_active"])
            
            if "is_verified" in user_dict:
                if isinstance(user_dict["is_verified"], int):
                    user_dict["is_verified"] = bool(user_dict["is_verified"])
            
            if user_dict.get("role_name") is None and user_dict.get("role_id"):
                role_result = db.execute(
                    text("SELECT title FROM roles WHERE id = :role_id"),
                    {"role_id": int(user_dict["role_id"]) if user_dict["role_id"].isdigit() else 0}
                ).first()
                if role_result:
                    user_dict["role_name"] = role_result[0]
            
            # Get user's menu permissions based on role
            user_menu_permissions = get_user_menu_permissions_by_role(
                db, 
                user_dict.get("role_id"), 
                user_dict.get("id")
            )
            user_dict["menu_permissions"] = user_menu_permissions
            
            users_list.append(user_dict)
        
        total_pages = (total_count + per_page - 1) // per_page if per_page > 0 else 0
        
        return {
            "users": users_list,
            "total": total_count,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages
        }
        
    except Exception as e:
        log(f"Error in list_users_service: {str(e)}")
        import traceback
        log(f"Traceback: {traceback.format_exc()}")
        raise Exception(f"Error in list_users_service: {str(e)}")


def get_user_menu_permissions_by_role(db: Session, role_id: Any, user_id: int = None):
    """
    Get menu permissions for a user based on their role
    First get all menus from menu_list, then check role_menu_permission for enable status
    """
    try:
        if isinstance(role_id, str):
            role_id = int(role_id) if role_id.isdigit() else 0
        
        if role_id == 1:
            return {
                "menu_tree": [],
                "total_menus": 0,
                "enabled_menus": 0,
                "role_id": role_id,
                "is_super_admin": True,
                "message": "Super Admin has access to all menus"
            }
        
        all_menus_query = text("""
            SELECT 
                ml.id as menu_id,
                ml.name as menu_name,
                ml.key as menu_key,
                ml.parent_menu_id,
                ml.allowed_user_role,
                ml.sort_order,
                0 as is_enabled
            FROM menu_list ml
            ORDER BY ml.sort_order ASC, ml.id ASC
        """)
        
        all_menus_result = db.execute(all_menus_query).mappings().all()
        
        role_permissions_query = text("""
            SELECT 
                menu_id,
                enabled
            FROM role_menu_permission 
            WHERE role_id = :role_id
        """)
        
        role_permissions = db.execute(role_permissions_query, {"role_id": role_id}).mappings().all()
        
        enabled_menus_dict = {}
        for perm in role_permissions:
            enabled_menus_dict[perm['menu_id']] = perm['enabled']
        
        menu_list = []
        for menu in all_menus_result:
            menu_id = menu['menu_id']
            is_enabled = enabled_menus_dict.get(menu_id, 0)  
            
            menu_list.append({
                "menu_id": menu_id,
                "menu_name": menu['menu_name'],
                "menu_key": menu['menu_key'].strip() if menu['menu_key'] else "",
                "parent_menu_id": menu['parent_menu_id'],
                "allowed_user_role": menu['allowed_user_role'],
                "is_enabled": bool(is_enabled),
                "sort_order": menu.get('sort_order', 0)
            })
        
        menu_dict = {}
        for menu in menu_list:
            menu_dict[menu['menu_id']] = menu
        
        menu_tree = []
        processed_menus = set()
        
        for menu_id, menu_data in menu_dict.items():
            if menu_data['parent_menu_id'] is None or menu_data['parent_menu_id'] == 0:
                parent_menu = {
                    "menu_id": menu_data['menu_id'],
                    "menu_name": menu_data['menu_name'],
                    "menu_key": menu_data['menu_key'],
                    "is_enabled": menu_data['is_enabled'],
                    "sub_menus": []
                }
                
                for sub_id, sub_data in menu_dict.items():
                    if sub_data['parent_menu_id'] == menu_id:
                        parent_menu['sub_menus'].append({
                            "menu_id": sub_data['menu_id'],
                            "menu_name": sub_data['menu_name'],
                            "menu_key": sub_data['menu_key'],
                            "parent_menu_id": sub_data['parent_menu_id'],
                            "is_enabled": sub_data['is_enabled']
                        })
                        processed_menus.add(sub_id)
                
                menu_tree.append(parent_menu)
                processed_menus.add(menu_id)
        
        for menu_id, menu_data in menu_dict.items():
            if menu_id not in processed_menus:
                menu_tree.append({
                    "menu_id": menu_data['menu_id'],
                    "menu_name": menu_data['menu_name'],
                    "menu_key": menu_data['menu_key'],
                    "is_enabled": menu_data['is_enabled'],
                    "sub_menus": []
                })
        
        total_menus = len(menu_list)
        enabled_menus = sum(1 for m in menu_list if m['is_enabled'])
        
        return {
            "menu_tree": menu_tree,
            "total_menus": total_menus,
            "enabled_menus": enabled_menus,
            "role_id": role_id,
            "is_super_admin": False
        }
        
    except Exception as e:
        print(f"Error getting user menu permissions: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return {
            "menu_tree": [],
            "total_menus": 0,
            "enabled_menus": 0,
            "role_id": role_id,
            "is_super_admin": False,
            "error": str(e)
        }

def update_user_status_service(user_id: int, is_user_active: str, db: Session):
    """
    Service function to update user active status
    """
    try:
        # Check if user exists
        existing = db.execute(
            text("SELECT id, name, email, is_user_active FROM users WHERE id = :id"),
            {"id": user_id}
        ).mappings().first()
        
        if not existing:
            return None
        
        existing_dict = dict(existing)
        
        # Update the user status
        db.execute(
            text("""
                UPDATE users 
                SET is_user_active = :is_user_active, 
                    updated_at = NOW()
                WHERE id = :id
            """),
            {
                "id": user_id,
                "is_user_active": is_user_active
            }
        )
        db.commit()
        
        # Get the updated user
        updated_user = db.execute(
            text("""
                SELECT u.id, u.name, u.email, u.phone, u.company_id, u.role_id,
                       u.is_verified, u.is_user_active, u.sub_user_role,
                       u.on_board_date, u.off_board_date, u.created_at, u.updated_at,
                       r.title as role_name,
                       creator.name as created_by_name
                FROM users u
                LEFT JOIN roles r ON CAST(u.role_id AS UNSIGNED) = r.id
                LEFT JOIN users creator ON u.created_by = creator.id
                WHERE u.id = :id
            """),
            {"id": user_id}
        ).mappings().first()
        
        if updated_user:
            user_dict = dict(updated_user)
            user_dict.pop("password", None)
            user_dict.pop("otp", None)
            
            # Convert boolean fields
            if "is_user_active" in user_dict:
                if isinstance(user_dict["is_user_active"], str):
                    user_dict["is_user_active"] = user_dict["is_user_active"].lower() == "true"
                elif isinstance(user_dict["is_user_active"], int):
                    user_dict["is_user_active"] = bool(user_dict["is_user_active"])
            
            if "is_verified" in user_dict:
                if isinstance(user_dict["is_verified"], int):
                    user_dict["is_verified"] = bool(user_dict["is_verified"])
            
            log(f"User {user_id} status updated to: {is_user_active}")
            return user_dict
        
        return None
        
    except Exception as e:
        db.rollback()
        error_msg = str(e)
        log(f"Error in update_user_status_service: {error_msg}")
        import traceback
        log(f"Traceback: {traceback.format_exc()}")
        raise Exception(f"Failed to update user status: {error_msg}")