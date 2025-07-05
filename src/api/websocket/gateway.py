# pyright: reportOptionalCall=false
from socketio import AsyncServer

from src.helpers.logger import Logger
from src.helpers.model import utc_now

logger = Logger(__name__)


def gateway_events(sio: AsyncServer):
    if sio is not None and hasattr(sio, "on"):

        @sio.on("connect")
        async def on_connect(sid, environ, auth):
            try:
                user_agent = environ.get("HTTP_USER_AGENT", "unknown")
                client_ip = environ.get("REMOTE_ADDR", "unknown")
                client_id = auth.get("client_fingerprint", sid)

                if (
                    "asgi.scope" in environ
                    and "client" in environ["asgi.scope"]
                    and environ["asgi.scope"]["client"]
                ):
                    client_ip = environ["asgi.scope"]["client"][0]
                logger.info(
                    "Client connected: %s | Client IP: %s | User Agent: %s | Client ID: %s",
                    sid,
                    client_ip,
                    user_agent,
                    client_id,
                )
                await sio.save_session(
                    sid,
                    {
                        "client_id": client_id,
                        "user_agent": user_agent,
                        "client_ip": client_ip,
                    },
                )
                await sio.emit(
                    "connection",
                    {
                        "type": "onboarding",
                        "client_id": client_id,
                        "sender": "bot",
                        "message": "Hey there! How can I help you?",
                        "timestamp": utc_now().isoformat(),
                    },
                    room=sid,
                )
                logger.info("Session established for %s", client_id)
                return True

            except (KeyError, AttributeError, TypeError, ValueError) as e:
                logger.error("Connection error for %s: %s", sid, e)
                await sio.disconnect(sid)
                return False

        @sio.on("disconnect")
        async def on_disconnect(sid, reason):
            session = await sio.get_session(sid)
            user_agent = session.get("user_agent", "unknown")
            client_ip = session.get("client_ip", "unknown")
            client_id = session.get("client_id", sid)

            logger.info(
                "Client disconnected: %s | Reason: %s | Client IP: %s | User Agent: %s | Client ID: %s",
                sid,
                reason,
                client_ip,
                user_agent,
                client_id,
            )
