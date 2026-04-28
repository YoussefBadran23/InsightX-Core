import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

def send_reset_password_email(email_to: str, token: str):
    """
    Send a password reset email using SMTP.
    """
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        logger.warning("SMTP credentials not configured. Email NOT sent.")
        return

    subject = f"{settings.EMAILS_FROM_NAME} - Password Reset"
    reset_link = f"{settings.FRONTEND_URL}/reset-password?token={token}"
    
    html_content = f"""
    <html>
        <body>
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 8px;">
                <h2 style="color: #1a202c;">Reset Your Password</h2>
                <p style="color: #4a5568; line-height: 1.6;">
                    Hello,<br><br>
                    You requested a password reset for your InsightX account. Click the button below to set a new password. This link will expire in {settings.RESET_TOKEN_EXPIRE_MINUTES} minutes.
                </p>
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{reset_link}" style="background-color: #3182ce; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">
                        Reset Password
                    </a>
                </div>
                <p style="color: #718096; font-size: 14px;">
                    If you didn't request this, you can safely ignore this email.
                </p>
                <hr style="border: 0; border-top: 1px solid #e2e8f0; margin: 20px 0;">
                <p style="color: #a0aec0; font-size: 12px; text-align: center;">
                    &copy; 2026 InsightX. All rights reserved.
                </p>
            </div>
        </body>
    </html>
    """

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = f"{settings.EMAILS_FROM_NAME} <{settings.EMAILS_FROM_EMAIL}>"
    message["To"] = email_to

    # Plain-text version for email clients that don't support HTML
    text_content = f"Reset your password by clicking here: {reset_link}"
    
    message.attach(MIMEText(text_content, "plain"))
    message.attach(MIMEText(html_content, "html"))

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.EMAILS_FROM_EMAIL, email_to, message.as_string())
        logger.info(f"Successfully sent reset email to {email_to}")
    except Exception as e:
        logger.error(f"Error sending email to {email_to}: {e}")
        raise e
