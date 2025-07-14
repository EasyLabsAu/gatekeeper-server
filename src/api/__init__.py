from fastapi import APIRouter
from socketio import AsyncServer

from src.api.rest.consumers import consumer_router
from src.api.rest.contexts import context_router
from src.api.rest.forms import form_router
from src.api.rest.providers import provider_router
from src.api.rest.sessions import session_router
from src.api.websocket.chat import chat_events
from src.api.websocket.gateway import gateway_events


def setup_http_routes(prefix: str):
    router = APIRouter(prefix=prefix)
    router.include_router(provider_router)
    router.include_router(consumer_router)
    router.include_router(session_router)
    router.include_router(form_router)
    router.include_router(context_router)
    return router


def setup_websocket_events(sio: AsyncServer):
    gateway_events(sio)
    chat_events(sio)
