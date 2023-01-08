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
    
    if os.path.isdir(current_app.config['UPLOAD_FOLDER']):
        click.echo('\tRemoving existing images directory.')
        rmtree(current_app.config['UPLOAD_FOLDER'])
        click.echo('\tRemoved existing images directory.')
    
    os.mkdir(current_app.config['UPLOAD_FOLDER'])
    # os.mkdir('./images_db/processed')
    # os.mkdir('./images_db/unprocessed')
    # os.mkdir('./images_db/holding')
    
    click.echo('Created images directory.')


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


def log_action(action_text):
    """Insert action_text into logs database and delete rows older then 7 days."""

    # Insert action_text into logs table
    execute_query(
        'INSERT INTO logs (textmsg)'
        ' VALUES (%s)',
        (action_text,),
        fetch=False
    )

    # Delete rows older then 7 days
    execute_query(
        'DELETE FROM logs WHERE created < NOW() - INTERVAL \'7 days\'',
        fetch=False
    )