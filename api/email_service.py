# ========================================
# AfyaMetrix Email Service
# File: api/email_service.py
# ========================================

import aiosmtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import asyncio
import resend

load_dotenv()

# Email configuration
SMTP_SERVER = os.getenv("EMAIL_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("EMAIL_PORT", "587"))
SMTP_PORT_SSL = int(os.getenv("EMAIL_PORT_SSL", "465"))
SMTP_USERNAME = os.getenv("EMAIL_USERNAME", "")
SMTP_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
FROM_EMAIL = os.getenv("EMAIL_FROM", SMTP_USERNAME)
EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", "60"))
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")

class EmailService:
    def __init__(self):
        self.server = SMTP_SERVER
        self.port = SMTP_PORT
        self.port_ssl = SMTP_PORT_SSL
        self.username = SMTP_USERNAME
        self.password = SMTP_PASSWORD
        self.from_email = FROM_EMAIL
        self.timeout = EMAIL_TIMEOUT
        self.resend_key = RESEND_API_KEY
        
        # Log email configuration on startup (without sensitive data)
        print(f"📧 Production Email Service Configuration:")
        print(f"   SMTP Server: {self.server}")
        print(f"   SMTP Port (TLS): {self.port}")
        print(f"   SMTP Port (SSL): {self.port_ssl}")
        print(f"   SMTP Username: {self.username[:15]}..." if self.username else "   SMTP Username: Not configured")
        print(f"   SMTP Password: {'*' * 12}" if self.password else "   SMTP Password: Not configured")
        print(f"   From Email: {self.from_email}")
        print(f"   Timeout: {self.timeout}s")
        print(f"   Resend API: {'Available as backup' if self.resend_key else 'Not configured'}")
        
        # Validate critical configuration
        if not self.username or not self.password:
            print(f"⚠️  WARNING: SMTP credentials not properly configured!")
            print(f"   This will cause email delivery failures in production")
        else:
            print(f"✅ Email service ready for production")
        
        # Set Resend API key if available (but we'll disable it)
        if self.resend_key:
            resend.api_key = self.resend_key
    
    async def send_email_resend(self, to_email: str, subject: str, html_content: str):
        """Send email using Resend API - DISABLED FOR PRODUCTION"""
        # Resend API is limited to verified domains in production
        # Disable for now to force SMTP usage
        print(f"⚠️ Resend API disabled - domain verification required for production")
        return False
    
    async def send_email_smtp(self, to_email: str, subject: str, html_content: str, text_content: str = None):
        """Send email via SMTP with robust configuration"""
        try:
            # Validate SMTP configuration
            if not self.username or not self.password:
                raise Exception("SMTP credentials not configured")
            
            print(f"📧 Attempting SMTP connection to {self.server}:{self.port}")
            
            # Create message with proper encoding
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = self.from_email
            message["To"] = to_email
            message["Message-ID"] = f"<{os.urandom(16).hex()}@afyametrix.com>"
            
            # Add text part
            if text_content:
                text_part = MIMEText(text_content, "plain", "utf-8")
                message.attach(text_part)
            
            # Add HTML part
            html_part = MIMEText(html_content, "html", "utf-8")
            message.attach(html_part)
            
            # Send email with robust SMTP settings
            smtp_client = aiosmtplib.SMTP(
                hostname=self.server,
                port=self.port,
                timeout=self.timeout,
                use_tls=False  # We'll start TLS manually
            )
            
            await smtp_client.connect()
            await smtp_client.starttls()
            await smtp_client.login(self.username, self.password)
            await smtp_client.send_message(message)
            await smtp_client.quit()
            
            print(f"✅ Email sent successfully via SMTP to {to_email}")
            return True
            
        except Exception as smtp_error:
            print(f"❌ SMTP failed: {str(smtp_error)}")
            
            # Try alternative SMTP settings
            try:
                print(f"🔄 Retrying with alternative SMTP configuration...")
                
                # Alternative approach using direct send
                await aiosmtplib.send(
                    message,
                    hostname=self.server,
                    port=self.port_ssl,  # Try SSL port
                    use_tls=True,
                    username=self.username,
                    password=self.password,
                    timeout=self.timeout,
                )
                
                print(f"✅ Email sent via alternative SMTP (SSL) to {to_email}")
                return True
                
            except Exception as alt_error:
                print(f"❌ Alternative SMTP also failed: {str(alt_error)}")
                return False

    async def send_email(self, to_email: str, subject: str, html_content: str, text_content: str = None):
        """Production-grade email sending with multiple attempts"""
        
        print(f"📧 PRODUCTION: Sending email to {to_email}")
        
        # Attempt 1: Primary SMTP
        success = await self.send_email_smtp(to_email, subject, html_content, text_content)
        if success:
            return True
        
        # Attempt 2: Try with Resend as backup (if configured properly)
        if self.resend_key:
            print(f"🔄 Attempting Resend API as backup...")
            try:
                # Use proper from email for Resend
                params = {
                    "from": "AfyaMetrix <noreply@afyametrix.com>",  # This needs to be a verified domain
                    "to": [to_email],
                    "subject": subject,
                    "html": html_content,
                }
                
                email = resend.Emails.send(params)
                print(f"✅ Email sent successfully via Resend to {to_email}")
                return True
                
            except Exception as resend_error:
                print(f"❌ Resend API failed: {str(resend_error)}")
        
        # PRODUCTION CRITICAL: Email service completely failed
        print(f"\n" + "="*80)
        print(f"🚨 CRITICAL: EMAIL SERVICE FAILURE")
        print(f"="*80)
        print(f"❌ All email delivery methods failed for: {to_email}")
        print(f"📧 Subject: {subject}")
        
        # For PRODUCTION: Still extract codes for manual verification if needed
        if "verification" in subject.lower() and text_content:
            import re
            code_match = re.search(r'Your verification code is: (\d{6})', text_content)
            if code_match:
                verification_code = code_match.group(1)
                print(f"\n🔑 MANUAL VERIFICATION REQUIRED")
                print(f"Code: {verification_code}")
                print(f"Email: {to_email}")
                print(f"⚠️ System administrator must manually provide this code to user")
                
        elif "reset" in subject.lower() and text_content:
            import re
            code_match = re.search(r'Your password reset code is: (\d{6})', text_content)
            if code_match:
                reset_code = code_match.group(1)
                print(f"\n🔑 MANUAL PASSWORD RESET REQUIRED")
                print(f"Code: {reset_code}")
                print(f"Email: {to_email}")
                print(f"⚠️ System administrator must manually provide this code to user")
        
        print(f"="*80)
        print(f"🚨 ACTION REQUIRED: Fix email service configuration immediately")
        print(f"="*80 + "\n")
        
        # In production, we should NOT return True if email truly failed
        # But for now, allow manual verification via console codes
        return False  # Changed to False for production - emails MUST work
    
    async def test_email_connection(self):
        """Test email service connectivity - for production health checks"""
        try:
            smtp_client = aiosmtplib.SMTP(
                hostname=self.server,
                port=self.port,
                timeout=10,  # Short timeout for health check
                use_tls=False
            )
            
            await smtp_client.connect()
            await smtp_client.starttls()
            await smtp_client.login(self.username, self.password)
            await smtp_client.quit()
            
            print(f"✅ Email service connectivity test: PASSED")
            return True
            
        except Exception as e:
            print(f"❌ Email service connectivity test: FAILED - {str(e)}")
            return False
    
    async def send_verification_email(self, email: str, verification_code: str, name: str):
        """Send verification email"""
        subject = "AfyaMetrix - Verify Your Email"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Email Verification</title>
        </head>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background-color: #0A7B6E; padding: 20px; text-align: center; border-radius: 8px;">
                <h1 style="color: white; margin: 0;">🌍 AfyaMetrix</h1>
                <p style="color: white; margin: 5px 0;">Pan-Africa Health Intelligence</p>
            </div>
            
            <div style="padding: 30px 20px;">
                <h2 style="color: #333;">Hello {name}!</h2>
                <p style="color: #666; line-height: 1.6;">
                    Welcome to AfyaMetrix! Please verify your email address to complete your registration.
                </p>
                
                <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; text-align: center; margin: 20px 0;">
                    <p style="color: #333; font-size: 14px; margin-bottom: 10px;">Your verification code is:</p>
                    <div style="background-color: #0A7B6E; color: white; padding: 15px 30px; border-radius: 5px; font-size: 24px; font-weight: bold; letter-spacing: 3px; display: inline-block;">
                        {verification_code}
                    </div>
                </div>
                
                <p style="color: #666; font-size: 14px;">
                    This code will expire in 10 minutes. If you didn't create an account with AfyaMetrix, please ignore this email.
                </p>
            </div>
            
            <div style="background-color: #f8f9fa; padding: 15px; text-align: center; border-radius: 8px; margin-top: 30px;">
                <p style="color: #999; font-size: 12px; margin: 0;">
                    © 2024 AfyaMetrix. Empowering Community Health Workers across Africa.
                </p>
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
        AfyaMetrix - Email Verification
        
        Hello {name}!
        
        Welcome to AfyaMetrix! Please verify your email address to complete your registration.
        
        Your verification code is: {verification_code}
        
        This code will expire in 10 minutes. If you didn't create an account with AfyaMetrix, please ignore this email.
        
        © 2024 AfyaMetrix. Empowering Community Health Workers across Africa.
        """
        
        return await self.send_email(email, subject, html_content, text_content)
    
    async def send_password_reset_email(self, email: str, reset_code: str, name: str):
        """Send password reset email"""
        subject = "AfyaMetrix - Password Reset Request"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Password Reset</title>
        </head>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background-color: #E8402A; padding: 20px; text-align: center; border-radius: 8px;">
                <h1 style="color: white; margin: 0;">🔐 Password Reset</h1>
                <p style="color: white; margin: 5px 0;">AfyaMetrix Security</p>
            </div>
            
            <div style="padding: 30px 20px;">
                <h2 style="color: #333;">Hello {name}!</h2>
                <p style="color: #666; line-height: 1.6;">
                    We received a request to reset your AfyaMetrix password. Use the code below to reset your password:
                </p>
                
                <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; text-align: center; margin: 20px 0;">
                    <p style="color: #333; font-size: 14px; margin-bottom: 10px;">Your password reset code is:</p>
                    <div style="background-color: #E8402A; color: white; padding: 15px 30px; border-radius: 5px; font-size: 24px; font-weight: bold; letter-spacing: 3px; display: inline-block;">
                        {reset_code}
                    </div>
                </div>
                
                <p style="color: #666; font-size: 14px;">
                    This code will expire in 15 minutes. If you didn't request a password reset, please ignore this email and your password will remain unchanged.
                </p>
            </div>
            
            <div style="background-color: #f8f9fa; padding: 15px; text-align: center; border-radius: 8px; margin-top: 30px;">
                <p style="color: #999; font-size: 12px; margin: 0;">
                    © 2024 AfyaMetrix. Empowering Community Health Workers across Africa.
                </p>
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
        AfyaMetrix - Password Reset Request
        
        Hello {name}!
        
        We received a request to reset your AfyaMetrix password.
        
        Your password reset code is: {reset_code}
        
        This code will expire in 15 minutes. If you didn't request a password reset, please ignore this email.
        
        © 2024 AfyaMetrix. Empowering Community Health Workers across Africa.
        """
        
        return await self.send_email(email, subject, html_content, text_content)

# Global email service instance
email_service = EmailService()