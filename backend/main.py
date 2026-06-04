"""Main FastAPI application entry point.

The app and all routes are assembled in :mod:`eg1835.api.app`; this module is
the ASGI entry point referenced by ``uvicorn main:app``.
"""

from eg1835.api.app import create_app

app = create_app()
