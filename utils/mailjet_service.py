from mailjet_rest import Client
import smtplib
import logging
import qrcode
from io import BytesIO
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from typing import Optional, Dict, Any
import os
from datetime import datetime

MAILJET_API_KEY = "050686a87f18a8453172449b93f4bd08"
MAILJET_API_SECRET = "f1e24876c2ca567094966195c7445d7d"
MAILJET_SENDER_EMAIL = "afraz.psts@gmail.com"

SMTP_SENDER_EMAIL = "ahamedtariq.psts@gmail.com"
SMTP_SENDER_PASSWORD = "thlc aibo zdsa mztx"
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

EMAIL_PROVIDER = "smtp"  # or "smtp"

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class EmailService:
    def __init__(self, provider: str = EMAIL_PROVIDER):
        self.provider = provider
        self.mailjet_client = None
        if provider == "mailjet":
            self.mailjet_client = Client(auth=(MAILJET_API_KEY, MAILJET_API_SECRET), version='v3.1')
    
    def send_email_smtp(self, to_email: str, to_name: str, subject: str, html_content: str) -> Optional[Dict]:
        """Send email using SMTP (Gmail)"""
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = SMTP_SENDER_EMAIL
            msg['To'] = to_email
            
            # Create HTML part
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)
            
            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
            server.starttls()
            server.login(SMTP_SENDER_EMAIL, SMTP_SENDER_PASSWORD)
            
            server.send_message(msg)
            server.quit()
            
            logger.info(f"SMTP email sent successfully to {to_email}")
            return {"status_code": 200, "message": "Email sent successfully"}
            
        except Exception as e:
            logger.error(f"Error sending SMTP email: {str(e)}")
            return None
    
    def send_email_mailjet(self, to_email: str, to_name: str, subject: str, html_content: str, 
                          from_email: str = MAILJET_SENDER_EMAIL, from_name: str = "Resident Services") -> Optional[Any]:
        """Send email using Mailjet"""
        try:
            if not self.mailjet_client:
                raise Exception("Mailjet client not initialized")
            
            data = {
                'Messages': [
                    {
                        "From": {
                            "Email": from_email,
                            "Name": from_name
                        },
                        "To": [
                            {
                                "Email": to_email,
                                "Name": to_name
                            }
                        ],
                        "Subject": subject,
                        "HTMLPart": html_content
                    }
                ]
            }
            
            result = self.mailjet_client.send.create(data=data)
            logger.info(f"Mailjet response status: {result.status_code}")
            return result
            
        except Exception as e:
            logger.error(f"Error sending Mailjet email: {str(e)}")
            return None
    
    def send_email(self, to_email: str, to_name: str, subject: str, html_content: str) -> Optional[Any]:
        """Send email using selected provider"""
        if self.provider == "mailjet":
            return self.send_email_mailjet(to_email, to_name, subject, html_content)
        else:
            return self.send_email_smtp(to_email, to_name, subject, html_content)

email_service = EmailService()

def send_otp_email(email: str, first_name: str, otp: str, resend: bool = False):
    """Send OTP email using configured provider"""
    try:
        logger.info(f"Preparing to send OTP to: {email} with OTP: {otp} (Resend: {resend})")

        subject = "OTP Resend - Verify Your Email" if resend else "Welcome to Your Community - OTP Verification"
        heading = "Here's Your OTP Again!" if resend else "Welcome to Your Community!"
        note = "You requested to resend your OTP." if resend else "Thank you for joining us. To complete your verification, please use the following OTP:"

        html_content = f"""
        <div style="background-color: #f4f6f8; padding: 40px; font-family: Arial, sans-serif; text-align: center; color: #333;">
          <div style="max-width: 500px; margin: auto; background: #ffffff; border-radius: 10px; padding: 40px 30px; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
            <h1 style="color: #1a73e8; font-size: 26px;">{heading}</h1>
            <p style="font-size: 18px; margin: 10px 0;">Hello <strong>{first_name}</strong>,</p>
            <p style="font-size: 16px; margin: 20px 0;">{note}</p>
            <div style="display: inline-block; background-color: #f0f0f0; padding: 15px 30px; border-radius: 8px; font-size: 24px; font-weight: bold; color: #d35400; letter-spacing: 2px;">
              {otp}
            </div>
            <p style="font-size: 14px; margin-top: 20px;">This code is valid for 15 minutes.</p>
            <hr style="margin: 30px 0; border: none; border-top: 1px solid #eee;" />
            <p style="font-size:15px; font-weight:bold; margin-bottom:20px; text-align:center;">
                PSTS Access Control System
            </p>
            <p style="font-size: 14px;">Warm regards,<br/><strong>Resident Services Team</strong></p>
          </div>
          <p style="font-size: 12px; color: #999; margin-top: 20px;">© {first_name}'s Community – All rights reserved.</p>
        </div>
        """

        result = email_service.send_email(email, first_name, subject, html_content)
        
        if result:
            logger.info(f"OTP email sent successfully to {email}")
        else:
            logger.error(f"Failed to send OTP email to {email}")
        
        return result

    except Exception as e:
        logger.error(f"Error sending OTP email: {str(e)}")
        return None

def send_onboarding_email(email: str, first_name: str, building_name: str, on_board_date: str = None, off_board_date: str = None):
    """Send onboarding email using configured provider"""
    try:
        subject = "Welcome to Your Community Portal - Complete Your Profile"

        # Format dates if provided
        date_section = ""
        if on_board_date or off_board_date:
            date_section = """
            <div style="background-color: #f8f9fa; padding: 15px; border-radius: 8px; margin: 20px 0;">
                <h3 style="color: #333; margin-top: 0; margin-bottom: 15px;">Membership Period</h3>
                <table style="width: 100%; border-collapse: collapse;">
            """
            if on_board_date:
                date_section += f"""
                    <tr>
                        <td style="padding: 8px 5px; font-weight: bold; width: 40%;">Onboard Date:</td>
                        <td style="padding: 8px 5px;">{on_board_date}</td>
                    </tr>
                """
            if off_board_date:
                date_section += f"""
                    <tr>
                        <td style="padding: 8px 5px; font-weight: bold;">Offboard Date:</td>
                        <td style="padding: 8px 5px;">{off_board_date}</td>
                    </tr>
                """
            date_section += """
                </table>
            </div>
            """
        
        logo_url = "https://sykon.mjt.lu/img2/sykon/7366a578-81f7-4f8c-80cd-f16195af2130/content"

        html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Welcome Email</title>
</head>
<body style="margin:0; padding:0; background-color:#f4f6f8; font-family: 'Segoe UI', Arial, sans-serif; color:#333;">
  <div style="max-width:600px; margin:30px auto; background-color:#ffffff; border-radius:16px; overflow: hidden; box-shadow:0 8px 24px rgba(0,0,0,0.08);">

    <!-- Logo Section - Fixed centering and sizing -->
    <div style="text-align: center; padding: 40px 24px 20px; background-color: #ffffff;">
        <img src="{logo_url}" alt="Company Logo" style="width: 180px; max-width: 100%; height: auto; display: inline-block; margin: 0 auto;" />
    </div>

    <!-- Content Section -->
    <div style="padding: 0 32px 32px;">
        
        <!-- Welcome Header - Now left-aligned -->
        <div style="margin-bottom: 20px;">
            <p style="font-size: 18px; color: #666; margin: 0 0 5px 0; text-align: left;">Hello <strong style="color: #333;">{first_name}</strong>,</p>
        </div>

        <!-- Welcome Content -->
        <p style="font-size: 16px; line-height: 1.6; margin-bottom: 25px; color: #444; text-align: left;">
            We're excited to have you as a part of our community at <strong style="color: #1a73e8;">{building_name}</strong>. 
            Your account has been successfully created and you're now ready to explore all the features 
            our community portal has to offer.
        </p>

        <!-- Date Information (if provided) -->
        {date_section}

        <!-- Complete Your Profile Section -->
        <div style="text-align: center; margin: 35px 0;">
            <h2 style="color: #333; font-size: 24px; margin-bottom: 15px; font-weight: 600;">Complete Your Profile</h2>
            <p style="font-size: 16px; color: #666; margin-bottom: 25px; line-height: 1.5;">
                To get the most out of your community experience, please take a moment to complete your profile. 
                This helps us personalize your experience and connect you with relevant community features.
            </p>
            
            <!-- Complete Your Profile Button -->
          <a href="http://192.168.1.182:3000/" target="_blank" 
   style="display: inline-block; background-color: #1a73e8; color: #ffffff; text-decoration: none; 
          padding: 12px 32px; border-radius: 40px; font-weight: 600; font-size: 16px; 
          box-shadow: 0 4px 8px rgba(26, 115, 232, 0.2);
          transition: all 0.3s ease; border: 1px solid #1a73e8;">
    Complete Your Profile
</a>
            <p style="font-size: 14px; color: #999; margin-top: 16px;">
                Click the button above to set up your profile and preferences
            </p>
        </div>

        <!-- App Download Section -->
        <div style="margin: 45px 0 25px;">
            <p style="font-size: 18px; font-weight: 600; margin-bottom: 20px; text-align: center; color: #333;">
                Download PSTS Access Control System Mobile App
            </p>
           <table width="100%" cellpadding="0" cellspacing="0" style="text-align: center; border-collapse: collapse;">
    <tr>
        <td align="center" style="padding: 5px; width: 50%;">
            <a href="https://play.google.com/store" target="_blank" 
               style="display: inline-block; background-color: #1a73e8; color: #fff; text-decoration: none; 
                      padding: 10px 16px; border-radius: 6px; font-weight: 500; font-size: 14px; 
                      width: 130px; text-align: center; box-shadow: 0 2px 4px rgba(26,115,232,0.2);">
                 Google Play
            </a>
        </td>
        <td align="center" style="padding: 5px; width: 50%;">
            <a href="https://www.apple.com/app-store/" target="_blank" 
               style="display: inline-block; background-color: #000; color: #fff; text-decoration: none; 
                      padding: 10px 16px; border-radius: 6px; font-weight: 500; font-size: 14px; 
                      width: 130px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.2);">
                 App Store
            </a>
        </td>
    </tr>
</table>
        </div>

        <hr style="margin: 40px 0 20px; border: none; border-top: 2px solid #f0f0f0;">

        <!-- Footer -->
        <p style="font-size: 13px; color: #888; text-align: center; line-height: 1.5;">
            If you didn't create this account, you can safely ignore this email or contact our support team.
        </p>
        
    </div>
  </div>
</body>
</html>
"""

        result = email_service.send_email(email, first_name, subject, html_content)
        
        if result:
            logger.info(f"Onboarding email sent successfully to {email}")
        else:
            logger.error(f"Failed to send onboarding email to {email}")
        
        return result

    except Exception as e:
        logger.error(f"Failed to send onboarding email: {str(e)}")
        return None

def send_qr_email(email: str, name: str, building: str, card_no: str, valid_from: str, valid_to: str, qr_url: str):
    """Send QR email using configured provider"""
    try:
        subject = "Your QR Access Pass"

        html_content = f"""
<div style="background-color:#f5f8fa;padding:40px 20px;font-family:'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;">
    <div style="max-width:600px;margin:auto;background:#ffffff;padding:30px;border-radius:10px;box-shadow:0 4px 12px rgba(0,0,0,0.1);">
        <h1 style="color:#1a73e8;text-align:center;">QR Access Pass</h1>
        <p style="font-size:16px;color:#333;">Hi <strong>{name}</strong>,</p>
        <p style="font-size:15px;color:#555;">You have been granted visitor access to:</p>
        
        <table style="width:100%;margin-top:15px;margin-bottom:15px;">
            <tr>
                <td style="padding:5px 0;font-weight:bold;color:#333;">Building:</td>
                <td style="padding:5px 0;color:#333;">{building}</td>
            </tr>
            <tr>
                <td style="padding:5px 0;font-weight:bold;color:#333;">Valid From:</td>
                <td style="padding:5px 0;color:#333;">{valid_from}</td>
            </tr>
            <tr>
                <td style="padding:5px 0;font-weight:bold;color:#333;">Valid To:</td>
                <td style="padding:5px 0;color:#333;">{valid_to}</td>
            </tr>
        </table>

        <p style="font-size:15px;color:#333;">Please present the QR code below at the entrance for seamless access:</p>
        
        <p style="text-align:center;font-size:15px;color:#333;font-weight:bold;">
            Click the link to view your QR:<br>
            <a href="{qr_url}" style="font-size:14px;color:#1a73e8;">View QR Code</a>
        </p>

        <p style="font-size:13px;color:#888;text-align:center;">
            ⚠️ This QR code is personal and valid only during the mentioned period. Do not share it.
        </p>

        <hr style="border:none;border-top:1px solid #eee;margin:30px 0;" />

        <p style="font-size:14px;color:#555;text-align:center;">
            Thank you for visiting <strong>{building}</strong>.<br/>
            For assistance, contact building security or front desk.
        </p>
    </div>
</div>
"""

        result = email_service.send_email(email, name, subject, html_content)
        
        if result:
            logger.info(f"QR email sent successfully to {email}")
        else:
            logger.error(f"Failed to send QR email to {email}")
        
        return result

    except Exception as e:
        logger.error(f"Failed to send QR email: {str(e)}")
        return None

def generate_qr_base64(data: str) -> str:
    """Generate QR code and return as base64 string"""
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return base64.b64encode(buffer.read()).decode("utf-8")
    except Exception as e:
        logger.error(f"Error generating QR code: {str(e)}")
        return None

def send_otp_email(email: str, first_name: str, otp: str, resend: bool = False):
    """Send OTP email using configured provider with improved template"""
    try:
        logger.info(f"Preparing to send OTP to: {email} with OTP: {otp} (Resend: {resend})")

        subject = "OTP Verification - PSTS Access Control System" if not resend else "Resend OTP - PSTS Access Control System"
        heading = "Email Verification" if not resend else "Resend Verification Code"
        
        logo_url = "https://sykon.mjt.lu/img2/sykon/7366a578-81f7-4f8c-80cd-f16195af2130/content"

        html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OTP Verification</title>
</head>
<body style="margin:0; padding:0; background-color:#f4f6f9; font-family: 'Segoe UI', Roboto, Arial, sans-serif;">
    
    <!-- Main Container - Increased width from 500px to 600px -->
    <div style="max-width: 600px; margin: 30px auto; background: #ffffff; border-radius: 20px; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,0.08);">
        
        <!-- Header with Logo -->
        <div style="text-align: center; padding: 40px 30px 20px; background: linear-gradient(135deg, #f8faff 0%, #ffffff 100%);">
            <img src="{logo_url}" alt="PSTS Access Control" 
                 style="width: 160px; height: auto; display: inline-block; margin: 0 auto;">
        </div>
        
        <!-- Content Area - Adjusted padding for better proportion -->
        <div style="padding: 20px 40px 35px;">
            
            <!-- Greeting -->
            <div style="margin-bottom: 25px;">
                <p style="font-size: 18px; color: #333; margin: 0 0 5px 0;">Hello <strong style="color: #1a73e8;">{first_name}</strong>,</p>
            </div>
            
            <!-- Main Message - Removed OTP container background -->
            <div style="background-color: #f8faff; padding: 20px; border-radius: 16px; margin-bottom: 25px; text-align: center;">
                <p style="font-size: 16px; color: #555; margin: 0 0 15px 0; line-height: 1.6;">
                    {'' if resend else 'Thank you for registering with PSTS Access Control System. Please use the following verification code to complete your registration:'}
                    {'You have requested to resend the verification code. Please use the OTP below:' if resend else ''}
                </p>
                
                <!-- OTP Display - Removed blue background, now just blue text -->
                <div style="margin: 5px auto;">
                    <span style="font-size: 40px; font-weight: 700; letter-spacing: 8px; color: #1a73e8; font-family: 'Courier New', monospace; text-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                        {otp}
                    </span>
                </div>
                
                <!-- Expiry Note - Slightly reduced margin -->
                <p style="font-size: 14px; color: #888; margin: 15px 0 0 0;">
                     This code will expire in <strong style="color: #d32f2f;">15 minutes</strong>
                </p>
            </div>
            
            <!-- Security Tips -->
            <div style="background-color: #fff3e0; padding: 20px; border-radius: 12px; margin-bottom: 25px;">
                <p style="font-size: 14px; color: #e65100; margin: 0 0 10px 0; font-weight: 600;"> Security Tips:</p>
                <ul style="margin: 0; padding-left: 20px; color: #555; font-size: 13px;">
                    <li style="margin-bottom: 5px;">Never share this OTP with anyone</li>
                    <li style="margin-bottom: 5px;">Our team will never ask for this code</li>
                    <li>If you didn't request this, please ignore this email</li>
                </ul>
            </div>
            
            <!-- Need Help Section -->
            <div style="text-align: center; margin: 25px 0 15px;">
                <p style="font-size: 14px; color: #777; margin: 0;">
                    Need help? Contact our support team at 
                    <a href="mailto:support@psts.com" style="color: #1a73e8; text-decoration: none;">support@psts.com</a>
                </p>
            </div>
            
            <!-- Divider -->
            <hr style="border: none; border-top: 1px solid #eef2f6; margin: 25px 0;">
            
            <!-- Footer -->
            <div style="text-align: center;">
                <p style="font-size: 12px; color: #999; margin: 0 0 5px 0;">
                    © {datetime.now().year} PSTS Access Control System. All rights reserved.
                </p>
                <p style="font-size: 11px; color: #aaa; margin: 0;">
                    This is an automated message, please do not reply to this email.
                </p>
            </div>
            
        </div>
    </div>
    
    <!-- Background message for email clients that block images -->
    <div style="display: none;">PSTS Access Control System - OTP Verification Email</div>
</body>
</html>
"""

        result = email_service.send_email(email, first_name, subject, html_content)
        
        if result:
            logger.info(f"OTP email sent successfully to {email}")
        else:
            logger.error(f"Failed to send OTP email to {email}")
        
        return result

    except Exception as e:
        logger.error(f"Error sending OTP email: {str(e)}")
        return None