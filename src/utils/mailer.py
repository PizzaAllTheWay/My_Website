import os, smtplib
from email.message import EmailMessage

def send_email(to: str, subject: str, body: str) -> None:
    """
    Minimal mailer.
    If SMTP_* env vars are set, sends real email.
    Otherwise, just prints the mail to stdout (good for dev/logs).
    """
    host = os.getenv("SMTP_HOST"); user = os.getenv("SMTP_USER")
    pwd  = os.getenv("SMTP_PASS"); port = int(os.getenv("SMTP_PORT", "587"))
    sender = os.getenv("SMTP_FROM", user or "no-reply@example.invalid")

    if not host or not user or not pwd:
        print(f"\n--- EMAIL (DEV) ---\nTo: {to}\nSubj: {subject}\n\n{body}\n--- END ---\n")
        return

    msg = EmailMessage()
    msg["From"] = sender; msg["To"] = to; msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP(host, port) as s:
        s.starttls()
        s.login(user, pwd)
        s.send_message(msg)
