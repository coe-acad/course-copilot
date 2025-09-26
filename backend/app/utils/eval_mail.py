# This file contains the logic for sending emails to the user about evlaution completion
from ..services.mongo import get_evaluation_by_evaluation_id, get_email_by_user_id
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.config.settings import settings

def send_email(email: str, subject: str, body: str):
    """Send an email via SMTP using settings from environment variables.
    If SMTP is not configured, logs to console.
    """
    if not settings.SMTP_HOST or not settings.SMTP_USERNAME or not settings.SMTP_PASSWORD or not settings.SMTP_FROM_EMAIL:
        print(f"Email sent to: {email}\nSubject: {subject}\n\n{body}")
        return

    message = MIMEMultipart()
    message["From"] = settings.SMTP_FROM_EMAIL
    message["To"] = email
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain"))

    try:
        if settings.SMTP_USE_SSL:
            with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                server.sendmail(settings.SMTP_FROM_EMAIL, [email], message.as_string())
        else:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                server.ehlo()
                if settings.SMTP_USE_TLS:
                    server.starttls()
                    server.ehlo()
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                server.sendmail(settings.SMTP_FROM_EMAIL, [email], message.as_string())
    except Exception as e:
        print(f"[EMAIL-ERROR] Failed to send email to {email}: {str(e)}")

def send_eval_completion_email(evaluation_id: str, user_id: str):
    evaluation = get_evaluation_by_evaluation_id(evaluation_id)
    user_email = get_email_by_user_id(user_id)
    if not user_email:
        print(f"[EMAIL-WARN] No email found for user_id={user_id}; skipping email.")
        return
    subject = "Evaluation Completed"
    body = f"""
Dear User,

Your evaluation (ID: {evaluation_id}) has been successfully completed.  
You can view the results on the evaluation card of the course.  

Regards,  
ACAD
"""
    send_email(user_email, subject, body)