from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

from app.config import app_settings

middlewares = [
    Middleware(
        CORSMiddleware,
        allow_origins=app_settings.ALLOWED_ORIGINS,
        allow_credentials=app_settings.ALLOW_CREDENTIALS,
        allow_methods=app_settings.ALLOW_METHODS,
        allow_headers=app_settings.ALLOW_HEADERS,
    )
]
