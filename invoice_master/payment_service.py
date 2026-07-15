import hashlib
import hmac
import json
import requests
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session
from common.logger import log as write_to_server_log
from utils.hitpay_config import HitPayConfig


def generate_hitpay_signature(data: Dict[str, Any], salt: str) -> str:
    """Generate HMAC-SHA256 signature for HitPay API"""
    sorted_data = dict(sorted(data.items()))
    json_string = json.dumps(sorted_data, separators=(',', ':'))
    signature = hmac.new(
        salt.encode('utf-8'),
        json_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return signature


def create_hitpay_payment_request(
    amount: float,
    purpose: str,
    customer_name: str,
    customer_email: str,
    redirect_url: str,
    webhook_url: str,
    reference_number: str
) -> Dict[str, Any]:
    """Create a payment request with HitPay"""
    try:
        api_url = f"{HitPayConfig.get_api_url()}/payment-requests"
        
    
        if not HitPayConfig.get_api_key():
            raise Exception("HitPay API key is not configured")
        
        payload = {
            "amount": str(round(amount, 2)),  
            "purpose": purpose[:255], 
            "customer_name": customer_name[:100], 
            "customer_email": customer_email[:100],
            "redirect_url": redirect_url,
            "webhook_url": webhook_url,
            "reference_number": reference_number[:50],  
            "currency": "SGD"
        }
        
        payload = {k: v for k, v in payload.items() if v is not None}
        
        headers = {
            "X-BUSINESS-API-KEY": HitPayConfig.get_api_key(),
            "Content-Type": "application/json"
        }
        
        write_to_server_log(f"Creating HitPay payment request")
        write_to_server_log(f"URL: {api_url}")
        write_to_server_log(f"Payload: {json.dumps(payload, indent=2)}")
        write_to_server_log(f"API Key: {HitPayConfig.get_api_key()[:10]}...")
        
        response = requests.post(api_url, json=payload, headers=headers, timeout=30)
        
        write_to_server_log(f"Response Status Code: {response.status_code}")
        
        if response.status_code != 200 and response.status_code != 201:
            try:
                error_data = response.json()
                write_to_server_log(f"Error Response: {json.dumps(error_data, indent=2)}")
                
                if 'errors' in error_data:
                    error_messages = []
                    for field, errors in error_data['errors'].items():
                        error_messages.append(f"{field}: {', '.join(errors)}")
                    raise Exception(f"Validation errors: {'; '.join(error_messages)}")
                elif 'message' in error_data:
                    raise Exception(f"HitPay API Error: {error_data['message']}")
                else:
                    raise Exception(f"HitPay API Error: {json.dumps(error_data)}")
            except json.JSONDecodeError:
                raise Exception(f"HitPay API Error (Status {response.status_code}): {response.text}")
        
        result = response.json()
        write_to_server_log(f"HitPay success response: {json.dumps(result, indent=2)}")
        
        return result
        
    except requests.exceptions.RequestException as e:
        write_to_server_log(f"Request error creating HitPay payment: {str(e)}")
        if hasattr(e, 'response') and e.response:
            write_to_server_log(f"Response status: {e.response.status_code}")
            write_to_server_log(f"Response text: {e.response.text}")
        raise Exception(f"Failed to create payment request: {str(e)}")
    except Exception as e:
        write_to_server_log(f"Error creating HitPay payment: {str(e)}")
        raise


def verify_hitpay_webhook_signature(payload: bytes, signature: str) -> bool:
    """Verify HitPay webhook signature"""
    try:
        expected_signature = hmac.new(
            HitPayConfig.get_salt().encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected_signature, signature)
    except Exception as e:
        write_to_server_log(f"Error verifying webhook signature: {str(e)}")
        return False


def create_invoice_payment_service(
    invoice_id: int,
    db: Session,
    customer_name: str,
    customer_email: str,
    redirect_url: str,
    webhook_url: str
) -> Dict[str, Any]:
    """Create payment for an invoice"""
    try:
        invoice_query = """
            SELECT id, invoice_number, total_amount, resident_id, status, payment_status
            FROM invoice_master 
            WHERE id = :invoice_id
        """
        
        invoice = db.execute(text(invoice_query), {"invoice_id": invoice_id}).mappings().first()
        
        if not invoice:
            raise Exception("Invoice not found")
        
        if invoice['status'].upper() == 'PAID':
            raise Exception("Invoice is already paid")
        
        resident_query = """
            SELECT first_name, last_name, email, phone
            FROM user_personal_details 
            WHERE id = :resident_id
        """
        
        resident = db.execute(text(resident_query), {"resident_id": invoice['resident_id']}).mappings().first()
        
        if not resident:
            raise Exception("Resident not found")
        
        # Generate unique reference number
        reference_number = f"INV{invoice_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        hitpay_response = create_hitpay_payment_request(
            amount=float(invoice['total_amount']),
            purpose=f"Payment for Invoice {invoice['invoice_number']}",
            customer_name=customer_name or f"{resident['first_name']} {resident['last_name']}",
            customer_email=customer_email or resident['email'],
            redirect_url=redirect_url,
            webhook_url=webhook_url,
            reference_number=reference_number
        )
        
        # Store payment record
        payment_insert_query = """
            INSERT INTO invoice_payments (
                invoice_id, payment_request_id, reference_number, amount, 
                payment_url, status, hitpay_response, created_at, updated_at
            ) VALUES (
                :invoice_id, :payment_request_id, :reference_number, :amount,
                :payment_url, :status, :hitpay_response, NOW(), NOW()
            )
        """
        
        db.execute(
            text(payment_insert_query),
            {
                "invoice_id": invoice_id,
                "payment_request_id": hitpay_response.get('id'),
                "reference_number": reference_number,
                "amount": invoice['total_amount'],
                "payment_url": hitpay_response.get('url'),
                "status": "pending",
                "hitpay_response": json.dumps(hitpay_response)
            }
        )
        db.commit()
        
        payment_record = db.execute(
            text("SELECT id FROM invoice_payments WHERE payment_request_id = :pid"),
            {"pid": hitpay_response.get('id')}
        ).first()
        
        return {
            "id": hitpay_response.get('id'),
            "invoice": dict(invoice),
            "hitpay_response": hitpay_response,
            "invoice_payment": {
                "payment_url": hitpay_response.get('url'),
                "hitpay_id": hitpay_response.get('id'),
                "reference_number": reference_number,
                "payment_record_id": payment_record[0] if payment_record else None
            }
        }
        
    except Exception as e:
        db.rollback()
        write_to_server_log(f"Error in create_invoice_payment_service: {str(e)}")
        import traceback
        write_to_server_log(f"Traceback: {traceback.format_exc()}")
        raise Exception(f"Failed to create payment: {str(e)}")


def update_payment_status_service(
    payment_request_id: str,
    status: str,
    db: Session,
    reference: Optional[str] = None
) -> Dict[str, Any]:
    """Update payment status and invoice status"""
    try:
        write_to_server_log(f"=== START update_payment_status_service ===")
        write_to_server_log(f"payment_request_id: {payment_request_id}")
        write_to_server_log(f"status: {status}")
        write_to_server_log(f"reference: {reference}")
        
        payment_query = """
            SELECT id, invoice_id, status, payment_request_id, reference_number 
            FROM invoice_payments 
            WHERE payment_request_id = :payment_request_id
        """
        
        payment = db.execute(
            text(payment_query), 
            {"payment_request_id": payment_request_id}
        ).mappings().first()
        
        write_to_server_log(f"Payment found by payment_request_id: {payment}")
        
        if not payment and reference:
            payment_query = """
                SELECT id, invoice_id, status, payment_request_id, reference_number 
                FROM invoice_payments 
                WHERE reference_number = :reference
            """
            payment = db.execute(
                text(payment_query), 
                {"reference": reference}
            ).mappings().first()
            write_to_server_log(f"Payment found by reference: {payment}")
        
        if not payment:
            error_msg = f"Payment record not found for ID: {payment_request_id} or reference: {reference}"
            write_to_server_log(f"ERROR: {error_msg}")
            raise Exception(error_msg)
        
        write_to_server_log(f"Found payment: ID={payment['id']}, Current Status={payment['status']}, Invoice ID={payment['invoice_id']}")
        
        update_payment_query = """
            UPDATE invoice_payments 
            SET status = :status, updated_at = NOW()
            WHERE id = :payment_id
        """
        
        result = db.execute(
            text(update_payment_query),
            {
                "status": status,
                "payment_id": payment['id']
            }
        )
        
        write_to_server_log(f"Payment update affected rows: {result.rowcount}")
        
        invoice_updated = False
        if status.lower() == 'completed':
            write_to_server_log(f"Updating invoice {payment['invoice_id']} to PAID")
            update_invoice_query = """
                UPDATE invoice_master 
                SET status = 'PAID', 
                    payment_status = 'PAID', 
                    paid_at = NOW(),
                    updated_at = NOW()
                WHERE id = :invoice_id
                AND (status != 'PAID' OR status IS NULL)
            """
            
            invoice_result = db.execute(
                text(update_invoice_query),
                {"invoice_id": payment['invoice_id']}
            )
            invoice_updated = invoice_result.rowcount > 0
            write_to_server_log(f"Invoice update affected rows: {invoice_result.rowcount}")
            write_to_server_log(f"Invoice updated: {invoice_updated}")
        
        db.commit()
        write_to_server_log(f"Transaction committed successfully")
        
        updated_payment = db.execute(
            text("SELECT id, status, updated_at FROM invoice_payments WHERE id = :payment_id"),
            {"payment_id": payment['id']}
        ).mappings().first()
        write_to_server_log(f"Updated payment status: {updated_payment['status'] if updated_payment else 'Not found'}")
        
        invoice_query = """
            SELECT id, invoice_number, status, payment_status, paid_at
            FROM invoice_master 
            WHERE id = :invoice_id
        """
        
        invoice = db.execute(
            text(invoice_query),
            {"invoice_id": payment['invoice_id']}
        ).mappings().first()
        
        write_to_server_log(f"Final invoice status: {invoice['status'] if invoice else 'Not found'}")
        write_to_server_log(f"=== END update_payment_status_service ===")
        
        return {
            "payment": dict(payment),
            "updated_payment": dict(updated_payment) if updated_payment else None,
            "invoice": dict(invoice) if invoice else None,
            "status": status,
            "invoice_updated": invoice_updated
        }
        
    except Exception as e:
        db.rollback()
        write_to_server_log(f"Error in update_payment_status_service: {str(e)}")
        import traceback
        write_to_server_log(f"Traceback: {traceback.format_exc()}")
        raise Exception(f"Failed to update payment status: {str(e)}")


def get_payment_status_service(
    invoice_id: int,
    db: Session
) -> Dict[str, Any]:
    """Get payment status for an invoice"""
    try:
        payment_query = """
            SELECT id, payment_request_id, reference_number, amount, 
                   status, payment_url, hitpay_response, created_at
            FROM invoice_payments 
            WHERE invoice_id = :invoice_id
            ORDER BY id DESC
            LIMIT 1
        """
        
        payment = db.execute(
            text(payment_query),
            {"invoice_id": invoice_id}
        ).mappings().first()
        
        if not payment:
            return {"status": "not_found", "message": "No payment found for this invoice"}
        
        if payment['hitpay_response'] and isinstance(payment['hitpay_response'], str):
            try:
                payment['hitpay_response'] = json.loads(payment['hitpay_response'])
            except:
                pass
        
        return dict(payment)
        
    except Exception as e:
        write_to_server_log(f"Error in get_payment_status_service: {str(e)}")
        raise Exception(f"Failed to get payment status: {str(e)}")


def handle_hitpay_webhook_service(
    payload: dict,
    signature: str,
    db: Session
) -> Dict[str, Any]:
    """Handle HitPay webhook callback"""
    try:
        data = payload.get('data', {})
        payment_request_id = data.get('id')
        status = data.get('status')
        
        if not payment_request_id or not status:
            write_to_server_log(f"Invalid webhook payload: {payload}")
            raise Exception("Invalid webhook payload")
        
        write_to_server_log(f"Processing webhook for payment {payment_request_id} with status {status}")
        
        result = update_payment_status_service(payment_request_id, status, db)
        
        return result
        
    except Exception as e:
        write_to_server_log(f"Error in handle_hitpay_webhook_service: {str(e)}")
        raise Exception(f"Failed to process webhook: {str(e)}")