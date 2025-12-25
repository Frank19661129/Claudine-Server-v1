"""
Email service using SendGrid.
Part of Infrastructure layer - external service integration.
"""
import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content


class EmailService:
    """Service for sending emails via SendGrid."""

    def __init__(self):
        self.api_key = os.getenv("SENDGRID_API_KEY")
        self.client = SendGridAPIClient(self.api_key) if self.api_key else None

    def send_email(
        self,
        from_email: str,
        to_email: str,
        subject: str,
        html_content: str,
        from_name: str = "PAI"
    ) -> dict:
        """
        Send an email via SendGrid.

        Args:
            from_email: Sender email address
            to_email: Recipient email address
            subject: Email subject
            html_content: HTML content of the email
            from_name: Display name for sender

        Returns:
            Dict with success status and details
        """
        if not self.client:
            # Fallback to fake mode if no API key
            print(f"[FAKE EMAIL - No SendGrid API Key]")
            print(f"From: {from_name} <{from_email}>")
            print(f"To: {to_email}")
            print(f"Subject: {subject}")
            print(f"Content: {html_content[:200]}...")
            return {
                "success": True,
                "fake": True,
                "message": "Email would be sent (no API key configured)"
            }

        try:
            message = Mail(
                from_email=Email(from_email, from_name),
                to_emails=To(to_email),
                subject=subject,
                html_content=Content("text/html", html_content)
            )

            response = self.client.send(message)

            return {
                "success": response.status_code in [200, 201, 202],
                "status_code": response.status_code,
                "message": "Email sent successfully"
            }

        except Exception as e:
            error_body = ""
            if hasattr(e, 'body'):
                error_body = e.body
            print(f"[EMAIL ERROR] Failed to send email: {e}")
            print(f"[EMAIL ERROR] Response body: {error_body}")
            print(f"[EMAIL ERROR] From: {from_email}, To: {to_email}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to send email"
            }

    def send_inbox_verification_email(
        self,
        pai_inbox: str,
        user_email: str,
        verification_url: str
    ) -> dict:
        """
        Send inbox verification email.

        Sends FROM noreply@pai-ai.com TO their personal email.
        Note: We use noreply@ because the inbox subdomain needs domain verification in SendGrid.
        """
        subject = "Bevestig je PAI inbox"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 40px 20px; }}
                .header {{ text-align: center; margin-bottom: 30px; }}
                .logo {{ font-size: 28px; font-weight: 300; color: #1a365d; letter-spacing: 2px; }}
                .content {{ background: #f8f9fa; border-radius: 8px; padding: 30px; margin-bottom: 30px; }}
                .button {{ display: inline-block; background: linear-gradient(135deg, #1a365d, #2d4a7c); color: white; padding: 14px 28px; text-decoration: none; border-radius: 6px; font-weight: 500; }}
                .inbox-address {{ font-family: monospace; background: #e2e8f0; padding: 8px 12px; border-radius: 4px; }}
                .footer {{ text-align: center; font-size: 12px; color: #718096; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="logo">PEPPER</div>
                </div>
                <div class="content">
                    <h2 style="margin-top: 0;">Bevestig je PAI inbox</h2>
                    <p>Dit is een verificatie email vanuit je nieuwe PAI inbox:</p>
                    <p class="inbox-address">{pai_inbox}</p>
                    <p>Klik op onderstaande knop om te bevestigen dat je emails kunt ontvangen vanuit je PAI account.</p>
                    <p style="text-align: center; margin: 30px 0;">
                        <a href="{verification_url}" class="button">Bevestig mijn inbox</a>
                    </p>
                    <p style="font-size: 13px; color: #718096;">
                        Of kopieer deze link naar je browser:<br>
                        <a href="{verification_url}" style="color: #4299e1; word-break: break-all;">{verification_url}</a>
                    </p>
                </div>
                <div class="footer">
                    <p>Deze email is verzonden door PAI AI.<br>
                    Je ontvangt deze email omdat je een PAI account hebt aangemaakt.</p>
                </div>
            </div>
        </body>
        </html>
        """

        return self.send_email(
            from_email="noreply@pai-ai.com",
            to_email=user_email,
            subject=subject,
            html_content=html_content,
            from_name="PAI"
        )

    def send_email_verification_code(
        self,
        to_email: str,
        code: str
    ) -> dict:
        """
        Send email verification code during onboarding.
        """
        subject = "Je PAI verificatiecode"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 40px 20px; }}
                .header {{ text-align: center; margin-bottom: 30px; }}
                .logo {{ font-size: 28px; font-weight: 300; color: #1a365d; letter-spacing: 2px; }}
                .content {{ background: #f8f9fa; border-radius: 8px; padding: 30px; margin-bottom: 30px; }}
                .code {{ font-size: 36px; font-family: monospace; letter-spacing: 8px; text-align: center; background: #1a365d; color: white; padding: 20px; border-radius: 8px; margin: 20px 0; }}
                .footer {{ text-align: center; font-size: 12px; color: #718096; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="logo">PEPPER</div>
                </div>
                <div class="content">
                    <h2 style="margin-top: 0;">Je verificatiecode</h2>
                    <p>Gebruik deze code om je email adres te verifiëren:</p>
                    <div class="code">{code}</div>
                    <p style="font-size: 13px; color: #718096;">
                        Deze code is 15 minuten geldig.
                    </p>
                </div>
                <div class="footer">
                    <p>Deze email is verzonden door PAI AI.<br>
                    Als je dit niet hebt aangevraagd, kun je deze email negeren.</p>
                </div>
            </div>
        </body>
        </html>
        """

        return self.send_email(
            from_email="noreply@pai-ai.com",
            to_email=to_email,
            subject=subject,
            html_content=html_content,
            from_name="PAI"
        )


# Singleton instance
_email_service = None


def get_email_service() -> EmailService:
    """Get the email service singleton."""
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service
