"""Ponto de entrada WSGI para servidores de producao (ex.: gunicorn wsgi:app)."""
from app import create_app

app = create_app()
