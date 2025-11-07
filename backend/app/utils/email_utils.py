import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from ..config.settings import settings

logger = logging.getLogger(__name__)

def send_course_share_notification(recipient_email: str, course_name: str, sharer_email: str):
    """
    Send email notification when a course is shared
    
    Args:
        recipient_email: Email of the user receiving the shared course
        course_name: Name of the course being shared
        sharer_email: Email of the user sharing the course
    """
    try:
        # Get email configuration from settings
        smtp_server = settings.SMTP_HOST or "smtp.gmail.com"
        smtp_port = settings.SMTP_PORT or 587
        sender_email = settings.SMTP_FROM_EMAIL
        sender_password = settings.SMTP_PASSWORD
        use_tls = settings.SMTP_USE_TLS
        
        if not sender_email or not sender_password:
            logger.warning("Email credentials not configured. Please set SMTP_FROM_EMAIL and SMTP_PASSWORD in your .env file. Skipping email notification.")
            return False
        
        if not smtp_server:
            logger.warning("SMTP server not configured. Please set SMTP_HOST in your .env file. Skipping email notification.")
            return False
        
        # Create message
        message = MIMEMultipart("alternative")
        message["Subject"] = f"Course Shared: {course_name}"
        message["From"] = sender_email
        message["To"] = recipient_email
        
        # Create HTML email body
        html = f"""
        <html>
          <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
              <h2 style="color: #2563eb;">Course Shared With You! 🎓</h2>
              <p>Hello!</p>
              <p><strong>{sharer_email}</strong> has shared a course with you on Course Copilot.</p>
              <div style="background-color: #f5f8ff; padding: 15px; border-radius: 8px; margin: 20px 0;">
                <p style="margin: 0;"><strong>Course Name:</strong> {course_name}</p>
              </div>
              <p>You now have full access to this course, including all assets, evaluations and resources.</p>
              <p>
                <a href="https://course-copilot.atriauniversity.ai/login" 
                   style="background-color: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block; margin-top: 10px;">Log in to Course Copilot</a>
              </p>
            </div>
          </body>
        </html>
        """
        
        # Create plain text version
        text = f"""
        Course Shared With You!
        
        Hello!
        
        {sharer_email} has shared a course with you on Course Copilot.
        
        Course Name: {course_name}
        
        You now have full access to this course, including all assets and evaluations.
        
        Log in to Course Copilot to view the course.
        
        This is an automated notification from Course Copilot.
        """
        
        # Attach both versions
        part1 = MIMEText(text, "plain")
        part2 = MIMEText(html, "html")
        message.attach(part1)
        message.attach(part2)
        
        # Send email
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            if use_tls:
                server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, recipient_email, message.as_string())
        
        logger.info(f"Course share notification sent successfully to {recipient_email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send email notification: {str(e)}")
        return False

