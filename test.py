from flask import Flask, render_template, request, flash
from flask_sqlalchemy import SQLAlchemy
import psycopg2
from psycopg2 import Error
import os
import psycopg2.extras
# app = Flask(__name__)
# app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://mladen:password@localhost/flasksql'
# app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
# app.secret_key = 'secret string'
def get_conn():
    conn = psycopg2.connect(user=os.environ['DB_USERNAME'],
                        password=os.environ['DB_PASSWORD'],
                        host="localhost",
                        port="5432",
                        database="testdb")
    return conn
# db = SQLAlchemy(app)
try:


    # conn = psycopg2.connect(app.config['SQLALCHEMY_DATABASE_URI'])
    conn = get_conn()
    cur = conn.cursor(cursor_factory = psycopg2.extras.RealDictCursor)

    # with open('./imagesel/schema.sql') as f:
    #     # cur.execute(f.read())
    #     # for sql_line in f.read().split(";"):
    #     #     cur.execute(sql_line + ";")
    #     cur.execute(f.read())
    cur.execute("SELECT * FROM tokens;")
    conn.commit()
    
    # cur.execute("SELECT * FROM tokens;")
    while True:
        row = cur.fetchone()
        if row is None:
            break
        print(row)

    # rows = cur.fetchone()
    # print(rows)
    
    
    cur.close()
    conn.close()

except (Exception, Error) as error:
    print("Error while connecting to PostgreSQL", error)