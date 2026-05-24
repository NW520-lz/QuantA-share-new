import asyncio
import smtplib
from email.mime.text import MIMEText

from app.core.config import settings


def _send_email_sync(to_email: str, subject: str, body: str) -> None:
    if not settings.smtp_host or not settings.smtp_from_email:
        raise RuntimeError("SMTP is not configured. Please set SMTP_HOST and SMTP_FROM_EMAIL.")

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from_email
    msg["To"] = to_email

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
        if settings.smtp_use_tls:
            server.starttls()
        if settings.smtp_user:
            server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(msg)


async def send_verification_email(to_email: str, code: str) -> None:
    subject = "QuantA Share 邮箱验证码"
    body = (
        f"您的验证码是：{code}\n"
        "有效期：10 分钟。\n"
        "如果这不是您的操作，请忽略此邮件。"
    )
    await asyncio.to_thread(_send_email_sync, to_email, subject, body)
