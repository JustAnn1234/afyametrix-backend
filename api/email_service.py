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
SMTP_USERNAME = os.getenv("EMAIL_USERNAME", "")
SMTP_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
FROM_EMAIL = os.getenv("EMAIL_FROM", SMTP_USERNAME)
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")

class EmailService:
    def __init__(self):
        self.server = SMTP_SERVER
        self.port = SMTP_PORT
        self.username = SMTP_USERNAME
        self.password = SMTP_PASSWORD
        self.from_email = FROM_EMAIL
        self.resend_key = RESEND_API_KEY
        
        # Set Resend API key if available
        if self.resend_key:
            resend.api_key = self.resend_key
    
    async def send_email_resend(self, to_email: str, subject: str, html_content: str):
        """Send email using Resend API"""
        try:
            params = {
                "from": "AfyaMetrix <onboarding@resend.dev>",  # Use Resend's default sender
                "to": [to_email],
                "subject": subject,
                "html": html_content,
            }
            
            email = resend.Emails.send(params)
            print(f"✅ Email sent successfully via Resend to {to_email}")
            return True
            
        except Exception as e:
            print(f"❌ Resend email failed to {to_email}: {str(e)}")
            return False
    
    async def send_email(self, to_email: str, subject: str, html_content: str, text_content: str = None):
        """Send email with fallback: Resend API -> SMTP -> Console Log"""
        
        # Try Resend first if API key is available
        if self.resend_key:
            success = await self.send_email_resend(to_email, subject, html_content)
            if success:
                return True
            else:
                # Log the fallback to SMTP
                print(f"⚠️ Resend API failed, falling back to SMTP for {to_email}")
        
        # Fallback to SMTP
        try:
            # Create message
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = self.from_email
            message["To"] = to_email
            
            # Add text part
            if text_content:
                text_part = MIMEText(text_content, "plain")
                message.attach(text_part)
            
            # Add HTML part
            html_part = MIMEText(html_content, "html")
            message.attach(html_part)
            
            # Send email
            await aiosmtplib.send(
                message,
                hostname=self.server,
                port=self.port,
                start_tls=True,
                username=self.username,
                password=self.password,
            )
            
            print(f"✅ Email sent successfully via SMTP to {to_email}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to send email to {to_email}: {str(e)}")
            # In demo mode, just log the code to console
            if "verification" in subject.lower():
                print(f"📧 DEMO MODE: Email content for {to_email}:")
                print(f"Subject: {subject}")
                print(f"Content: {text_content or html_content}")
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