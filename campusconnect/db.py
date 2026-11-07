"""Acceso a la base de datos SQLite. Todas las consultas usan parámetros (?)."""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import click
from flask import current_app, g


def ahora() -> str:
    """Fecha y hora UTC en formato ISO."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_db():
    """Conexión de la petición actual (se reutiliza dentro de la misma petición)."""
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_error=None):
    conexion = g.pop("db", None)
    if conexion is not None:
        conexion.close()


def init_db():
    """Crea las tablas si no existen."""
    conexion = get_db()
    conexion.executescript((Path(__file__).parent / "schema.sql").read_text(encoding="utf-8"))
    conexion.commit()


@click.command("init-db")
def init_db_command():
    """Crea las tablas de la base de datos."""
    init_db()
    click.echo("Base de datos inicializada.")


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
