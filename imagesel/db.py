import sqlite3

import click
from flask import current_app, g
import psycopg2
import psycopg2.extras

from werkzeug.security import generate_password_hash

def get_db():
    if 'db' not in g:
        # g.db = sqlite3.connect(
        #     current_app.config['DATABASE'],
        #     detect_types=sqlite3.PARSE_DECLTYPES
        # )
        # g.db.row_factory = sqlite3.Row

        g.db = psycopg2.connect(user="mladen",
                            password="password",
                            host="localhost",
                            port="5432",
                            database="testdb")

    return g.db


def close_db(e=None):
    db = g.pop('db', None)

    if db is not None:
        db.close()

def init_db():
    db = get_db()
    cur = db.cursor()

    with current_app.open_resource('schema.sql') as f:
        cur.execute(f.read().decode('utf8'))
    
    db.commit()
    cur.close()
    close_db()


@click.command('init-db')
def init_db_command():
    """Clear the existing data and create new tables."""
    init_db()
    click.echo('Initialized the POSTGRES database.')


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)

# Add new user to database
def add_user(token, password):
    db = get_db()
    cur = db.cursor()

    hash = generate_password_hash(password)
    cur.execute(
        'INSERT INTO tokens (token, passhash)'
        ' VALUES (%s, %s)',
        (token, hash)
    )

    db.commit()
    cur.close()
    close_db()

def execute_query(query, args=None, fetch=True):
    db = get_db()
    cur = db.cursor(cursor_factory = psycopg2.extras.RealDictCursor)

    cur.execute(query, args)
    rows = []
    if fetch:
        rows = cur.fetchall()
    
    db.commit()
    cur.close()
    close_db()
    return rows
