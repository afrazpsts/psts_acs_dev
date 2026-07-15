# invoice_master/callback_router.py
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import Optional
from common.logger import log as write_to_server_log
from DB.db import get_db
from .payment_service import update_payment_status_service

router = APIRouter(tags=["Payment Callback"])

@router.get("/payment-callback")
async def payment_callback(
    request: Request,
    status: Optional[str] = Query(None, description="Payment status"),
    reference: Optional[str] = Query(None, description="Reference number or Payment Request ID"),
    payment_request_id: Optional[str] = Query(None, description="Payment request ID"),
    db: Session = Depends(get_db)
):
    """
    Handle payment redirect from HitPay
    """
    try:
        write_to_server_log(f"=== PAYMENT CALLBACK RECEIVED ===")
        write_to_server_log(f"Full URL: {request.url}")
        write_to_server_log(f"Status param: {status}")
        write_to_server_log(f"Reference param: {reference}")
        write_to_server_log(f"Payment_request_id param: {payment_request_id}")
        
      
        if not payment_request_id and reference:
            payment_request_id = reference
            write_to_server_log(f"Using reference as payment_request_id: {payment_request_id}")
        
        if payment_request_id:
            write_to_server_log(f"Looking up payment by payment_request_id: {payment_request_id}")
            payment = db.execute(
                text("SELECT id, invoice_id, status, payment_request_id, reference_number FROM invoice_payments WHERE payment_request_id = :pid"),
                {"pid": payment_request_id}
            ).mappings().first()
            
            if payment:
                write_to_server_log(f"Found payment: ID={payment['id']}, payment_request_id={payment['payment_request_id']}, reference_number={payment['reference_number']}, status={payment['status']}")
            else:
                write_to_server_log(f"No payment found with payment_request_id: {payment_request_id}")
                # List all payments for debugging
                all_payments = db.execute(
                    text("SELECT id, payment_request_id, reference_number, status FROM invoice_payments ORDER BY id DESC LIMIT 5")
                ).mappings().all()
                write_to_server_log(f"Recent payments in DB: {[dict(p) for p in all_payments]}")
        
        if status and payment_request_id:
            write_to_server_log(f"Updating payment status - ID: {payment_request_id}, Status: {status}")
            result = update_payment_status_service(payment_request_id, status.lower(), db, None)
            write_to_server_log(f"Update result: {result}")
            
            if result.get('invoice_updated'):
                write_to_server_log(" Invoice successfully updated to PAID")
            else:
                write_to_server_log(" Invoice was not updated to PAID")
        else:
            write_to_server_log(f"Missing required data - status: {status}, payment_request_id: {payment_request_id}")
        
        html_content = get_payment_callback_html(status, reference, payment_request_id)
        return HTMLResponse(content=html_content, status_code=200)
        
    except Exception as e:
        write_to_server_log(f"Error in payment_callback: {str(e)}")
        import traceback
        write_to_server_log(f"Traceback: {traceback.format_exc()}")
        return HTMLResponse(content=get_error_html(status, payment_request_id), status_code=200)


def get_payment_callback_html(status, reference, payment_request_id):
    """Generate lightweight professional HTML response for payment callback"""
    
    if status == 'completed':
        icon = '✓'
        title = 'Payment Successful'
        message = 'Your payment has been processed successfully.'
        color = '#10b981'
    elif status == 'failed':
        icon = '✗'
        title = 'Payment Failed'
        message = 'Your payment could not be processed.'
        color = '#ef4444'
    elif status == 'cancelled':
        icon = '✗'
        title = 'Payment Cancelled'
        message = 'You have cancelled the payment process.'
        color = '#f59e0b'
    elif status == 'pending':
        icon = '⋯'
        title = 'Payment Processing'
        message = 'Your payment is being processed.'
        color = '#6366f1'
    else:
        icon = '?'
        title = 'Payment Update'
        message = 'Payment status has been updated.'
        color = '#6b7280'
    
    button_text = 'Return to App'
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title}</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                background: #f5f5f5;
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }}
            
            .container {{
                max-width: 400px;
                width: 100%;
                background: white;
                border-radius: 16px;
                padding: 40px 24px;
                text-align: center;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            }}
            
            .icon {{
                font-size: 64px;
                margin-bottom: 24px;
            }}
            
            h1 {{
                font-size: 24px;
                font-weight: 600;
                color: #1f2937;
                margin-bottom: 12px;
            }}
            
            .message {{
                font-size: 15px;
                color: #6b7280;
                line-height: 1.4;
                margin-bottom: 32px;
            }}
            
            .details {{
                background: #f9fafb;
                border-radius: 12px;
                padding: 16px;
                margin-bottom: 32px;
                text-align: left;
                font-size: 13px;
            }}
            
            .detail-row {{
                display: flex;
                justify-content: space-between;
                padding: 6px 0;
            }}
            
            .detail-label {{
                color: #6b7280;
            }}
            
            .detail-value {{
                color: #1f2937;
                font-weight: 500;
                font-family: monospace;
                font-size: 12px;
            }}
            
            button {{
                background: {color};
                color: white;
                border: none;
                padding: 12px 24px;
                font-size: 16px;
                font-weight: 600;
                border-radius: 8px;
                cursor: pointer;
                width: 100%;
                transition: opacity 0.2s;
            }}
            
            button:hover {{
                opacity: 0.9;
            }}
            
            button:active {{
                transform: scale(0.98);
            }}
            
            .divider {{
                height: 1px;
                background: #e5e7eb;
                margin: 8px 0;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="icon">{icon}</div>
            <h1>{title}</h1>
            <p class="message">{message}</p>
            
            <div class="details">
                <div class="detail-row">
                    <span class="detail-label">Transaction ID</span>
                    <span class="detail-value">{payment_request_id[:12] if payment_request_id else 'N/A'}</span>
                </div>
                <div class="divider"></div>
                <div class="detail-row">
                    <span class="detail-label">Status</span>
                    <span class="detail-value" style="color: {color};">{status.upper() if status else 'UNKNOWN'}</span>
                </div>
            </div>
            
            <button onclick="handleAction()">{button_text}</button>
        </div>
        
        <script>
            const status = "{status}";
            const paymentRequestId = "{payment_request_id}";
            
            function handleAction() {{
                if (window.ReactNativeWebView) {{
                    window.ReactNativeWebView.postMessage(JSON.stringify({{
                        type: 'CLOSE_WEBVIEW',
                        status: status,
                        paymentRequestId: paymentRequestId
                    }}));
                }} else {{
                    window.close();
                }}
            }}
            
            // Send initial status to app
            if (window.ReactNativeWebView) {{
                let messageType = 'PAYMENT_STATUS';
                if (status === 'completed') messageType = 'PAYMENT_SUCCESS';
                else if (status === 'failed' || status === 'cancelled') messageType = 'PAYMENT_FAILED';
                else if (status === 'pending') messageType = 'PAYMENT_PENDING';
                
                window.ReactNativeWebView.postMessage(JSON.stringify({{
                    type: messageType,
                    status: status,
                    paymentRequestId: paymentRequestId
                }}));
            }}
            
            // Auto close after 3 seconds for successful payments
            if (status === 'completed') {{
                setTimeout(() => {{
                    handleAction();
                }}, 3000);
            }}
        </script>
    </body>
    </html>
    """


def get_error_html(status, payment_request_id):
    """Generate simple error HTML"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Payment Update</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                background: #f5f5f5;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
                padding: 20px;
            }}
            .container {{
                background: white;
                border-radius: 16px;
                padding: 40px 24px;
                text-align: center;
                max-width: 350px;
                width: 100%;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            }}
            .icon {{
                font-size: 56px;
                margin-bottom: 20px;
            }}
            h2 {{
                font-size: 22px;
                color: #1f2937;
                margin-bottom: 12px;
            }}
            p {{
                color: #6b7280;
                margin-bottom: 24px;
                font-size: 14px;
            }}
            button {{
                background: #667eea;
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 8px;
                font-size: 15px;
                font-weight: 600;
                cursor: pointer;
                width: 100%;
            }}
            button:hover {{
                opacity: 0.9;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="icon">⚠️</div>
            <h2>Payment Update</h2>
            <p>Status: {status if status else 'Processing'}<br>
            ID: {payment_request_id[:12] if payment_request_id else 'N/A'}</p>
            <button onclick="closeWindow()">Return to App</button>
        </div>
        <script>
            function closeWindow() {{
                if (window.ReactNativeWebView) {{
                    window.ReactNativeWebView.postMessage(JSON.stringify({{
                        type: 'CLOSE_WEBVIEW',
                        status: '{status}',
                        paymentRequestId: '{payment_request_id}'
                    }}));
                }} else {{
                    window.close();
                }}
            }}
            
            if (window.ReactNativeWebView) {{
                window.ReactNativeWebView.postMessage(JSON.stringify({{
                    type: 'PAYMENT_PROCESSED',
                    status: '{status}',
                    paymentRequestId: '{payment_request_id}'
                }}));
            }}
        </script>
    </body>
    </html>
    """