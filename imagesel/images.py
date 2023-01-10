import os, base64
import time

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for, send_from_directory, current_app
)
import boto3

from imagesel.db import execute_query, refresh_bans

bp = Blueprint('images', __name__, url_prefix='/images')

# Before all requests run blueprint
@bp.before_app_request
def load_logged_in_user():
    user_id = session.get('user_id')
    is_admin = session.get('is_admin')

    if user_id is None:
        g.user = None

    elif is_admin:
        # Query admins table
        g.user = execute_query(
            "SELECT * FROM admins WHERE id = %s", (user_id,)
        )[0]

    else:
        g.user = execute_query(
            "SELECT * FROM workers WHERE id = %s", (user_id,)
        )[0]


# Get image object from S3
def get_object(image_name):
    s3 = boto3.client(
        "s3",
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
    )
    obj = s3.get_object(Bucket=os.environ["AWS_BUCKET_NAME"], Key=image_name)

    return obj


# Add images to route
@bp.route(f'/img_data/<filename>')
def img_data(filename):
    # Get image object from S3
    img = get_object(filename)
    return img['Body'].read()
