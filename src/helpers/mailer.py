from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import aiosmtplib
from aiosmtplib.response import SMTPResponse


class Mailer:
    def __init__(
        self,
        smtp_server: str,
        port: int,
        username: str,
        password: str,
        sender_email: str,
    ):
        self.smtp_server = smtp_server
        self.port = port
        self.username = username
        self.password = password
        self.sender_email = sender_email

    async def send_email(
        self,
        receiver_email: str,
        subject: str,
        body: str,
        is_html: bool = False,
    ) -> dict[str, Any]:
        msg = MIMEMultipart("alternative")
        part = MIMEText(body, "html" if is_html else "plain")
        msg.attach(part)

        msg["Subject"] = subject
        msg["From"] = self.sender_email
        msg["To"] = receiver_email

        try:
            result: tuple[dict[str, SMTPResponse], str] = await aiosmtplib.send(
                msg,
                hostname=self.smtp_server,
                port=self.port,
                start_tls=True,
                username=self.username,
                password=self.password,
            )
            if result[0] != 250:
                raise Exception(f"Failed to send email: {result[1]}")
            return {
                "status": "success",
                "message": "Email sent successfully",
                "details": result,
            }
        except Exception as e:
            return {
                "status": "error",
                "message": "Failed to send email",
                "details": str(e),
            }
