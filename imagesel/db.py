import os, random, string
from shutil import rmtree

import click
from flask import current_app, g
import psycopg2
import psycopg2.extras

from werkzeug.security import generate_password_hash


def get_db():
    if 'db' not in g:
        
        # Check if DATABASE_URL is set
        if 'DATABASE_URL' not in os.environ:
            g.db = psycopg2.connect(user="mladen",
                                password="password",
                                host="localhost",
                                port="5432",
                                database="testdb")
        else:
            DATABASE_URL = os.environ['DATABASE_URL']
            g.db = psycopg2.connect(DATABASE_URL, sslmode='require')

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
def add_worker(username):
    db = get_db()
    cur = db.cursor()

    # Generate access token for user in format: XXXX-XXXX
    acc_token = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4)) + '-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))

    cur.execute(
        'INSERT INTO workers (username, token)'
        ' VALUES (%s, %s)',
        (username, acc_token)
    )

    db.commit()
    cur.close()
    close_db()

    return acc_token

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


def log_action(action_text, worker_id=-1):
    """Insert action_text into logs database and delete rows older then 7 days."""

    # Insert action_text into logs table
    execute_query(
        'INSERT INTO logs (textmsg, worker_id)'
        ' VALUES (%s, %s)',
        (action_text, worker_id),
        fetch=False
    )

    # Delete rows older then 7 days
    execute_query(
        f'DELETE FROM logs WHERE created < NOW() - INTERVAL \'{current_app.config["LOG_DELETE_PERIOD"]} days\'',
        fetch=False
    )

def refresh_bans():
    # Delete rows older then 2 days from banned table
    execute_query(
        f'DELETE FROM banned WHERE created < NOW() - INTERVAL \'{current_app.config["BAN_DELETE_PERIOD"]} days\'',
        fetch=False
    )
