import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

def send_reset_password_email(email_to: str, token: str):
    """
    Send a password reset email via SMTP.

    Dev-mode fallback: when SMTP_USER or SMTP_PASSWORD is empty (which is
    the default in `.env.example`), we skip the real send and emit the
    reset URL to the backend logs. That way the developer can copy the
    link from `docker compose logs backend` and complete the flow without
    needing real SMTP credentials. In production fill in real SMTP and the
    real email path runs.
    """
    # Frontend URL — fall back to localhost dev port if not set.
    frontend = settings.FRONTEND_URL or "http://localhost:3000"
    reset_link = f"{frontend}/reset-password?token={token}"

    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        # Big-banner log so the dev can spot it in the stream.
        logger.warning(
            "═══════════════════════════════════════════════════════════════\n"
            "  SMTP not configured — printing reset link instead of emailing.\n"
            "  To: %s\n"
            "  Link: %s\n"
            "  (Set SMTP_USER + SMTP_PASSWORD in backend/.env to send real email.)\n"
            "═══════════════════════════════════════════════════════════════",
            email_to, reset_link,
        )
        return

    subject = f"{settings.EMAILS_FROM_NAME} - Password Reset"
    
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
    message["From"] = f"{settings.EMAILS_FROM_NAME} <{settings.SUPPORT_EMAIL}>"
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
