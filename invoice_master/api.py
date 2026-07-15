from fastapi import APIRouter, Depends, HTTPException, Query, Request,BackgroundTasks
from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
from common.logger import log as write_to_server_log
from fastapi.responses import StreamingResponse
from .pdf_service import build_invoice_from_data
from DB.db import get_db
from activity_logs.service import log_activity
from urllib.parse import parse_qs
from .service import (
    create_invoice_service,
    get_invoice_by_id_service,
    list_invoices_service,
    generate_invoices_excel_response,
    generate_invoices_pdf_response,
    update_invoice_status_service,
    delete_invoice_service,
    get_invoice_by_id_with_payment_service
)

from .payment_service import (
    create_invoice_payment_service,
    get_payment_status_service,
    update_payment_status_service,
    handle_hitpay_webhook_service,
    verify_hitpay_webhook_signature
)
import json

router = APIRouter(prefix="/invoices", tags=["Invoices"])


def _resolve_actor_from_email(db: Session, actor_email: Optional[str]):
    """Resolve actor details from email"""
    actor_id = None
    actor_name = "Unknown"
    actor_company_id = None

    if actor_email:
        actor_info = db.execute(
            text("SELECT id, name, company_id FROM users WHERE LOWER(email) = LOWER(:email)"),
            {"email": actor_email},
        ).fetchone()

        if actor_info:
            actor_id = actor_info[0]
            actor_name = actor_info[1]
            actor_company_id = actor_info[2]
        else:
            if actor_email.lower() == "bmoadmin@yopmail.com":
                actor_id = 7
                actor_name = "BMO Admin"
                actor_company_id = None
            else:
                actor_id = 1
                actor_name = "System Admin"
                actor_company_id = None

    return actor_id, actor_name, actor_company_id


@router.post("/create_invoice")
def create_invoice(
    request: Request,
    payload: dict,
    creator_email: Optional[str] = Query(None, description="Email of the person creating the invoice"),
    db: Session = Depends(get_db),
):
    """Create a new invoice with vehicle items and recurring settings"""
    try:
        ip_address = request.client.host if request and request.client else "Unknown"
        creator_id, creator_name, creator_company_id = _resolve_actor_from_email(db, creator_email)
        
        payload['created_by'] = creator_id if creator_id else 1
        
        required_fields = ['resident_id', 'building_id', 'invoice_date', 'due_date', 'vehicle_items']
        for field in required_fields:
            if field not in payload:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        
        if not payload.get('vehicle_items'):
            raise HTTPException(status_code=400, detail="At least one vehicle item is required")
        
        checked_items = [item for item in payload.get('vehicle_items', []) if item.get('checked') == True]
        if not checked_items:
            raise HTTPException(status_code=400, detail="At least one vehicle item must be selected (checked=true)")
        
        result = create_invoice_service(payload, db)
        
        log_user_id = creator_id if creator_id is not None else 1
        log_activity(
            db=db,
            user_id=log_user_id,
            action="Create",
            module_name="Invoices",
            record_id=result.get('id') if isinstance(result, dict) else None,
            description=f"Invoice created successfully – {result.get('invoice_number')}",
            new_data={
                "payload": payload,
                "result": {"status": 201, "message": "Invoice created successfully", "data": result},
                "creator_info": {
                    "creator_id": creator_id,
                    "creator_email": creator_email,
                    "creator_name": creator_name,
                    "creator_company_id": creator_company_id,
                },
            },
            ip_address=ip_address,
        )
        
        return {
            "message": "Invoice created successfully",
            "data": result,
            "status": 201,
            "creator_info": {
                "id": creator_id,
                "email": creator_email,
                "name": creator_name,
                "company_id": creator_company_id,
            },
        }
        
    except HTTPException as he:
        try:
            log_activity(
                db=db,
                user_id=creator_id if 'creator_id' in locals() else None,
                action="Create Invoice Failed",
                module_name="Invoices",
                description=f"Invoice creation failed: {he.detail}",
                new_data={
                    "payload": payload if 'payload' in locals() else {},
                    "error": he.detail,
                    "creator_info": {
                        "creator_id": creator_id if 'creator_id' in locals() else None,
                        "creator_email": creator_email if 'creator_email' in locals() else None,
                        "creator_name": creator_name if 'creator_name' in locals() else "Unknown",
                    },
                },
                ip_address=ip_address if 'ip_address' in locals() else "Unknown"
            )
        except:
            pass
        raise he
        
    except Exception as e:
        error_message = str(e)
        write_to_server_log(f"Error in create_invoice: {error_message}")
        import traceback
        write_to_server_log(f"Traceback: {traceback.format_exc()}")
        
        try:
            log_activity(
                db=db,
                user_id=creator_id if 'creator_id' in locals() else None,
                action="Create Invoice Failed",
                module_name="Invoices",
                description=f"Error: {error_message}",
                new_data={
                    "payload": payload if 'payload' in locals() else {},
                    "error": error_message,
                    "creator_info": {
                        "creator_id": creator_id if 'creator_id' in locals() else None,
                        "creator_email": creator_email if 'creator_email' in locals() else None,
                        "creator_name": creator_name if 'creator_name' in locals() else "Unknown",
                    },
                },
                ip_address=ip_address if 'ip_address' in locals() else "Unknown"
            )
        except:
            pass
        
        raise HTTPException(status_code=400, detail=error_message)


@router.get("/get_invoice/{invoice_id}")
def get_invoice(
    invoice_id: int, 
    db: Session = Depends(get_db)
):
    """Get invoice details by ID including vehicle items and recurring settings"""
    try:
        result = get_invoice_by_id_service(invoice_id, db)
        if not result:
            raise HTTPException(status_code=404, detail="Invoice not found")
        return {"message": "Invoice retrieved successfully", "data": result, "status": 200}
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    
def parse_int_param(value: Optional[str]) -> Optional[int]:
    """Helper function to parse integer parameters, handling empty strings"""
    if value is None or value == "" or value.strip() == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None

@router.get("/get_invoices")
def get_invoices(
    request: Request,
    invoice_id: Optional[str] = Query(None, description="Filter by specific invoice ID"),
    resident_id: Optional[str] = Query(None, description="Filter by resident ID"),
    building_id: Optional[str] = Query(None, description="Filter by building ID"),
    status: Optional[str] = Query(None, description="Filter by status (draft/sent/paid/overdue/cancelled)"),
    payment_status: Optional[str] = Query(None, description="Filter by payment status (pending/paid/partial/failed)"),
    from_date: Optional[str] = Query(None, description="Filter from this date (YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="Filter to this date (YYYY-MM-DD)"),
    download: bool = Query(False, description="Set to true to download as Excel or PDF"),
    download_type: Optional[str] = Query("excel", description="Download format: 'excel' or 'pdf'"),
    pagination: Optional[bool] = Query(True, description="Enable/disable pagination"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(10, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db)
):
    """
    Get all invoices with pagination and filtering options.
    If invoice_id is provided, returns that specific invoice.
    If resident_id is provided, returns invoices for that resident.
    If both are None/empty, returns overall list.
    """
    try:
        ip_address = request.client.host if request and request.client else "Unknown"
        
        invoice_id_int = parse_int_param(invoice_id)
        resident_id_int = parse_int_param(resident_id)
        building_id_int = parse_int_param(building_id)
        
        write_to_server_log(f"API: Parsed params - invoice_id: {invoice_id_int}, resident_id: {resident_id_int}, building_id: {building_id_int}")
        
        if invoice_id_int is not None:
            write_to_server_log(f"API: Getting specific invoice with ID: {invoice_id_int}")
            
            invoice = get_invoice_by_id_service(invoice_id_int, db)
            
            if not invoice:
                raise HTTPException(status_code=404, detail="Invoice not found")
            
            if invoice.get('status'):
                invoice['status'] = invoice['status'].upper()
            if invoice.get('payment_status'):
                invoice['payment_status'] = invoice['payment_status'].upper()
            
            if download:
                filename_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                export_rows = [invoice]
                if (download_type or "").lower() == "pdf":
                    return generate_invoices_pdf_response(
                        export_rows,
                        f"invoices_{filename_ts}.pdf",
                    )
                return generate_invoices_excel_response(
                    export_rows,
                    f"invoices_{filename_ts}.xlsx",
                )
            else:
                return {
                    "message": "Invoice retrieved successfully",
                    "data": invoice,
                    "status": 200
                }
        
        write_to_server_log(f"API: Getting invoices with filters - resident_id: {resident_id_int}, status: {status}, pagination: {pagination}")
        
        result = list_invoices_service(
            db=db,
            invoice_id=None,
            resident_id=resident_id_int,
            building_id=building_id_int,
            status=status,
            payment_status=payment_status,
            from_date=from_date,
            to_date=to_date,
            pagination=False if download else pagination,
            page=1 if download else (page if pagination else 1),
            per_page=None if download else (per_page if pagination else None)
        )
        
        if isinstance(result, dict) and 'invoices' in result:
            invoices_list = result['invoices']
            total_count = result['total']
            total_pages = result.get('total_pages', 1)
        else:
            invoices_list = []
            total_count = 0
            total_pages = 1
        
        for invoice in invoices_list:
            if invoice.get('status'):
                invoice['status'] = invoice['status'].upper()
            if invoice.get('payment_status'):
                invoice['payment_status'] = invoice['payment_status'].upper()
        
        if download:
            filename_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            if (download_type or "").lower() == "pdf":
                return generate_invoices_pdf_response(
                    invoices_list,
                    f"invoices_{filename_ts}.pdf",
                )
            return generate_invoices_excel_response(
                invoices_list,
                f"invoices_{filename_ts}.xlsx",
            )

        response_data = {
            "message": "Invoices retrieved successfully",
            "data": invoices_list,
            "filters_applied": {
                "invoice_id": invoice_id_int,
                "resident_id": resident_id_int,
                "building_id": building_id_int,
                "status": status,
                "payment_status": payment_status,
                "from_date": from_date,
                "to_date": to_date
            },
            "status": 200
        }
        
        if pagination:
            response_data["pagination_details"] = {
                "page": page,
                "per_page": per_page,
                "total": total_count,
                "last_page": total_pages
            }
        
        return response_data
        
    except HTTPException as he:
        raise he
    except Exception as e:
        error_message = str(e)
        write_to_server_log(f"Error in get_invoices: {error_message}")
        import traceback
        write_to_server_log(f"Traceback: {traceback.format_exc()}")
        
        raise HTTPException(status_code=500, detail=f"Error retrieving invoices: {error_message}")


@router.put("/update_invoice_status/{invoice_id}")
def update_invoice_status(
    request: Request,
    invoice_id: int,
    payload: dict,
    updater_email: Optional[str] = Query(None, description="Email of the person updating the invoice"),
    db: Session = Depends(get_db),
):
    """
    Update invoice status (draft/sent/paid/overdue/cancelled)
    """
    try:
        ip_address = request.client.host if request and request.client else "Unknown"
        updator_id, updator_name, updator_company_id = _resolve_actor_from_email(db, updater_email)
        
        old_invoice = get_invoice_by_id_service(invoice_id, db)
        if not old_invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")
        
        status = payload.get("status")
        if not status:
            raise HTTPException(status_code=400, detail="status field is required")
        
        valid_statuses = ["draft", "sent", "paid", "overdue", "cancelled"]
        if status not in valid_statuses:
            raise HTTPException(status_code=400, detail=f"status must be one of: {', '.join(valid_statuses)}")
        
        result = update_invoice_status_service(invoice_id, status, db)
        
        if not result:
            raise HTTPException(status_code=404, detail="Invoice not found")
        
        log_user_id = updator_id if updator_id is not None else 1
        log_activity(
            db=db,
            user_id=log_user_id,
            action="Update Status",
            module_name="Invoices",
            record_id=invoice_id,
            description=f"Invoice status updated to {status} – {old_invoice.get('invoice_number')}",
            old_data={"invoice": old_invoice, "status": old_invoice.get("status")},
            new_data={
                "payload": {"invoice_id": invoice_id, "status": status},
                "result": {
                    "status": 200,
                    "message": f"Invoice status updated to {status} successfully",
                    "data": result
                },
                "creator_info": {
                    "creator_id": updator_id,
                    "creator_email": updater_email,
                    "creator_name": updator_name,
                    "creator_company_id": updator_company_id,
                },
            },
            ip_address=ip_address,
        )
        
        return {
            "message": f"Invoice status updated to {status} successfully",
            "data": result,
            "status": 200,
            "creator_info": {
                "id": updator_id,
                "email": updater_email,
                "name": updator_name,
                "company_id": updator_company_id,
            },
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        error_message = str(e)
        write_to_server_log(f"Error in update_invoice_status: {error_message}")
        import traceback
        write_to_server_log(f"Traceback: {traceback.format_exc()}")
        
        try:
            log_activity(
                db=db,
                user_id=updator_id if 'updator_id' in locals() else None,
                action="Update Invoice Status Failed",
                module_name="Invoices",
                description=f"Error while updating invoice status: {error_message}",
                new_data={
                    "invoice_id": invoice_id,
                    "payload": payload if 'payload' in locals() else {},
                    "error": error_message,
                },
                ip_address=ip_address if 'ip_address' in locals() else "Unknown"
            )
        except:
            pass
        
        raise HTTPException(status_code=400, detail=error_message)


@router.delete("/delete_invoice/{invoice_id}")
def delete_invoice(
    request: Request,
    invoice_id: int,
    deleter_email: Optional[str] = Query(None, description="Email of the person deleting the invoice"),
    db: Session = Depends(get_db),
):
    """Delete an invoice"""
    try:
        ip_address = request.client.host if request and request.client else "Unknown"
        deleter_id, deleter_name, deleter_company_id = _resolve_actor_from_email(db, deleter_email)
        
        old_invoice = get_invoice_by_id_service(invoice_id, db)
        if not old_invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")
        
        result = delete_invoice_service(invoice_id, db)
        if not result:
            raise HTTPException(status_code=404, detail="Invoice not found")
        
        log_user_id = deleter_id if deleter_id is not None else 1
        log_activity(
            db=db,
            user_id=log_user_id,
            action="Delete",
            module_name="Invoices",
            record_id=invoice_id,
            description=f"Invoice deleted successfully – {old_invoice.get('invoice_number')}",
            old_data={"invoice": old_invoice},
            new_data={
                "payload": {"invoice_id": invoice_id},
                "result": {"status": 200, "message": "Invoice deleted successfully", "data": result},
                "creator_info": {
                    "creator_id": deleter_id,
                    "creator_email": deleter_email,
                    "creator_name": deleter_name,
                    "creator_company_id": deleter_company_id,
                },
            },
            ip_address=ip_address,
        )
        
        return {
            "message": "Invoice deleted successfully",
            "data": result,
            "status": 200,
            "creator_info": {
                "id": deleter_id,
                "email": deleter_email,
                "name": deleter_name,
                "company_id": deleter_company_id,
            },
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        error_message = str(e)
        write_to_server_log(f"Error in delete_invoice: {error_message}")
        raise HTTPException(status_code=400, detail=error_message)
    

@router.get("/payment/{invoice_id}")
def create_payment(
    request: Request,
    invoice_id: int,
    redirect_url: Optional[str] = Query(None, description="Redirect URL after payment"), 
    user_email: Optional[str] = Query(None, description="Email of the user making payment"),
    db: Session = Depends(get_db)
):
    """Create payment request for an invoice"""
    try:
        ip_address = request.client.host if request and request.client else "Unknown"
        user_id, user_name, user_company_id = _resolve_actor_from_email(db, user_email)
        
        # Get customer details
        invoice_query = """
            SELECT im.*, up.first_name, up.last_name, up.email as resident_email
            FROM invoice_master im
            LEFT JOIN user_personal_details up ON im.resident_id = up.id
            WHERE im.id = :invoice_id
        """
        
        invoice_data = db.execute(text(invoice_query), {"invoice_id": invoice_id}).mappings().first()
        
        if not invoice_data:
            raise HTTPException(status_code=404, detail="Invoice not found")
        
        if invoice_data['status'].upper() == 'PAID':
            raise HTTPException(status_code=400, detail="Invoice is already paid")
        
        customer_name = f"{invoice_data['first_name']} {invoice_data['last_name']}"
        customer_email_addr = invoice_data['resident_email']  # Always use resident email from DB
        
        base_url = str(request.base_url).rstrip('/')
        
    
        if not redirect_url or redirect_url == "yourapp://payment/callback":
            redirect_url = f"{base_url}/payment-callback"
        
        webhook_url = "https://ec62-49-206-117-196.ngrok-free.app/invoices/payment-webhook"
        
        write_to_server_log(f"Creating payment with redirect_url: {redirect_url}")
        write_to_server_log(f"Webhook URL: {webhook_url}")
        
        result = create_invoice_payment_service(
            invoice_id=invoice_id,
            db=db,
            customer_name=customer_name,
            customer_email=customer_email_addr,
            redirect_url=redirect_url,
            webhook_url=webhook_url
        )
        
        return {
            "message": "Payment created successfully",
            "data": result,
            "status": 200
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        error_message = str(e)
        write_to_server_log(f"Error in create_payment: {error_message}")
        import traceback
        write_to_server_log(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=error_message)
        


@router.get("/payment-status/{invoice_id}")
def get_payment_status(
    invoice_id: int,
    db: Session = Depends(get_db)
):
    """Get payment status for an invoice"""
    try:
        result = get_payment_status_service(invoice_id, db)
        
        return {
            "message": "Payment status retrieved successfully",
            "data": result,
            "status": 200
        }
        
    except Exception as e:
        error_message = str(e)
        write_to_server_log(f"Error in get_payment_status: {error_message}")
        raise HTTPException(status_code=500, detail=error_message)


@router.get("/update-payment-status")
def update_payment_status(
    request: Request,
    payment_request_id: str = Query(..., description="HitPay payment request ID"),
    status: str = Query(..., description="Payment status (completed/failed/pending/cancelled)"),
    reference: str = Query(..., description="Reference number"),
    db: Session = Depends(get_db)
):
    """Update payment status (called from frontend after payment)"""
    try:
        ip_address = request.client.host if request and request.client else "Unknown"
        
        valid_statuses = ['completed', 'failed', 'pending', 'cancelled']
        if status.lower() not in valid_statuses:
            raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
        
        result = update_payment_status_service(payment_request_id, status.lower(), db, reference)
        
        write_to_server_log(f"Payment status updated - payment_request_id: {payment_request_id}, status: {status}, reference: {reference}, invoice_updated: {result.get('invoice_updated', False)}")
        
        return {
            "message": "Payment status updated successfully",
            "data": result,
            "status": 200
        }
        
    except Exception as e:
        error_message = str(e)
        write_to_server_log(f"Error in update_payment_status: {error_message}")
        import traceback
        write_to_server_log(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=error_message)


@router.post("/payment-webhook")
async def hitpay_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    try:
        raw_body = await request.body()
        print("HITPAY WEBHOOK TRIGGERED ")

        signature = request.headers.get("X-Signature", "")

        print("RAW BODY:", raw_body)
        print("SIGNATURE:", signature)

        payload_str = raw_body.decode("utf-8")

        try:
            data = json.loads(payload_str)
            print("JSON DATA:", data)

            payment_request_id = data.get("id")
            status = data.get("status")
            reference = data.get("reference_number")

        except json.JSONDecodeError:
            data = parse_qs(payload_str)
            print("FORM DATA:", data)

            payment_request_id = data.get("payment_request_id", [None])[0]
            status = data.get("status", [None])[0]
            reference = data.get("reference_number", [None])[0]

        print("payment_request_id:", payment_request_id)
        print("status:", status)
        print("reference:", reference)

        if not payment_request_id or not status:
            raise Exception("Invalid webhook data")

        background_tasks.add_task(
            update_payment_status_service,
            payment_request_id,
            status,
            db,
            reference
        )

        return {"message": "Webhook received"}

    except Exception as e:
        print("Webhook error:", str(e))
        return {"error": str(e)}


@router.get("/get_invoice_with_payment/{invoice_id}")
def get_invoice_with_payment(
    invoice_id: int, 
    db: Session = Depends(get_db)
):
    """Get invoice details including payment information"""
    try:
        from .service import get_invoice_by_id_with_payment_service
        result = get_invoice_by_id_with_payment_service(invoice_id, db)
        if not result:
            raise HTTPException(status_code=404, detail="Invoice not found")
        return {"message": "Invoice retrieved successfully", "data": result, "status": 200}
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/generate-pdf/{invoice_id}")
def generate_invoice_pdf(
    invoice_id: int,
    db: Session = Depends(get_db)
):
    """Generate PDF for invoice by ID"""
    try:
        invoice_data = get_invoice_by_id_with_payment_service(invoice_id, db)
        
        if not invoice_data:
            raise HTTPException(status_code=404, detail="Invoice not found")
        
        pdf_buffer = build_invoice_from_data(invoice_data)
        
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=invoice_{invoice_data.get('invoice_number', invoice_id)}.pdf"
            }
        )
        
    except HTTPException as he:
        raise he
    except Exception as e:
        error_message = str(e)
        write_to_server_log(f"Error generating PDF: {error_message}")
        import traceback
        write_to_server_log(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {error_message}")


# @router.get("/preview-pdf/{invoice_id}")
# def preview_invoice_pdf(
#     invoice_id: int,
#     db: Session = Depends(get_db)
# ):
#     """Preview invoice PDF in browser"""
#     try:
#         invoice_data = get_invoice_by_id_with_payment_service(invoice_id, db)
        
#         if not invoice_data:
#             raise HTTPException(status_code=404, detail="Invoice not found")
        
#         pdf_buffer = build_invoice_from_data(invoice_data)
        
#         # Return PDF for inline preview
#         return StreamingResponse(
#             pdf_buffer,
#             media_type="application/pdf",
#             headers={
#                 "Content-Disposition": f"inline; filename=invoice_{invoice_data.get('invoice_number', invoice_id)}.pdf"
#             }
#         )
        
#     except HTTPException as he:
#         raise he
#     except Exception as e:
#         error_message = str(e)
#         write_to_server_log(f"Error generating PDF preview: {error_message}")
#         raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {error_message}")