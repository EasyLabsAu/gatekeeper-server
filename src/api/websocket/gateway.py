# pyright: reportOptionalCall=false

from socketio import AsyncServer

from src.helpers.logger import Logger

logger = Logger(__name__)


def gateway_events(sio: AsyncServer):
    if sio is not None and hasattr(sio, "on"):

        @sio.on("connect")
        async def on_connect(sid, environ):
            user_agent = environ.get("HTTP_USER_AGENT", "unknown")
            client_ip = environ.get("REMOTE_ADDR", "unknown")
            if (
                "asgi.scope" in environ
                and "client" in environ["asgi.scope"]
                and environ["asgi.scope"]["client"]
            ):
                client_ip = environ["asgi.scope"]["client"][0]
            logger.info(
                "Client connected: %s | Client IP: %s | User Agent: %s",
                sid,
                client_ip,
                user_agent,
            )
            await sio.save_session(
                sid, {"user_agent": user_agent, "client_ip": client_ip}
            )

        @sio.on("disconnect")
        async def on_disconnect(sid, reason):
            session = await sio.get_session(sid)
            user_agent = session.get("user_agent", "unknown")
            client_ip = session.get("client_ip", "unknown")
            logger.info(
                "Client disconnected: %s | Reason: %s | Client IP: %s | User Agent: %s",
                sid,
                reason,
                client_ip,
                user_agent,
            )
