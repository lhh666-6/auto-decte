"""Stable public FastAPI entrypoint.

Implementation currently lives in the DS-attributed module.  This wrapper
keeps deployment commands and third-party integrations independent of author
file naming.
"""

from fastapi import FastAPI

from app.api.main_ds import create_app as _create_app
from app.services.container import Services, build_services
from config.settings import Settings


def create_app(services: Services | None = None) -> FastAPI:
    """Build the API using injected services or the configured local defaults."""
    return _create_app(services or build_services(Settings(), install_seed_templates=True))
