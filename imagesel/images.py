import os, base64, json
import time

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for, send_from_directory, current_app, make_response
)
import boto3
import click
from concurrent import futures
from concurrent.futures import ProcessPoolExecutor

from imagesel.db import execute_query, refresh_bans

bp = Blueprint('images', __name__, url_prefix='/images')

# Before all requests run blueprint
@bp.before_app_request
def load_logged_in_user():
    user_id = session.get('user_id')
    is_admin = session.get('is_admin')

    if user_id is None:
        g.user = None

    else:
        if is_admin:
            # Query admins table
            g.user = execute_query(
                "SELECT * FROM admins WHERE id = %s", (user_id,)
            )

        else:
            g.user = execute_query(
                "SELECT * FROM workers WHERE id = %s", (user_id,)
            )

        if len(g.user):
            g.user = g.user[0]


# Get S3 connection
def get_s3():

    if 's3' not in g:
        g.s3 = boto3.client(
            "s3",
            aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        )
    
    return g.s3


# Close S3 connection
def close_s3(error):
    if hasattr(g, 's3'):
        g.s3.close()


# Define init_app
def init_app(app):
    app.teardown_appcontext(close_s3)
    app.cli.add_command(clear_db_command)


# Get image object from S3
def get_object(image_name):
    s3 = get_s3()
    obj = s3.get_object(Bucket=os.environ["AWS_BUCKET_NAME"], Key=image_name)

    return obj


# Upload image to S3
def upload_file(image, filename):
    s3 = get_s3()

    bucket = os.environ["AWS_BUCKET_NAME"]
    file_list = s3.list_objects(Bucket=bucket).get('Contents')
    
    # Check if file already exists
    if file_list is not None:
        file_list = [file['Key'] for file in file_list]

        if filename in file_list:
            idx = 1
            while filename in file_list:
                filename = f"{idx}_{filename}"
                idx += 1

    s3.upload_fileobj(
        image,
        os.environ["AWS_BUCKET_NAME"],
        filename
    )

    return filename

# Delete file from S3
def delete_file(filename):
    s3 = get_s3()
    s3.delete_object(Bucket=os.environ["AWS_BUCKET_NAME"], Key=filename)


# Delete all images from S3
def delete_all_files():
    s3 = get_s3()
    bucket = os.environ["AWS_BUCKET_NAME"]

    file_list = s3.list_objects(Bucket=bucket).get('Contents')

    if file_list is not None:
        for key in s3.list_objects(Bucket=bucket).get('Contents'):
            s3.delete_object(Bucket=bucket, Key=key['Key'])


@click.command('clear-db')
def clear_db_command():
    """Clear the existing data from S3."""
    delete_all_files()
    click.echo('All files deleted from S3 bucket.')


# Rename file in S3
def rename_file(old_filename, new_filename):
    s3 = get_s3()
    s3.copy_object(
        Bucket=os.environ["AWS_BUCKET_NAME"],
        CopySource={
            'Bucket': os.environ["AWS_BUCKET_NAME"],
            'Key': old_filename
        },
        Key=new_filename
    )
    s3.delete_object(Bucket=os.environ["AWS_BUCKET_NAME"], Key=old_filename)


# Add images to route
@bp.route(f'/img_data/<filename>')
def img_data(filename):
    # Get image object from S3
    img = get_object(filename)
    resp = make_response(img['Body'].read())
    resp.cache_control.max_age = 3600
    return resp

# @bp.route('/sign_s3/')
# def sign_s3():
#     print("S3")
#     S3_BUCKET = os.environ.get('AWS_BUCKET_NAME')

#     file_name = request.args.get('file_name')
#     file_type = request.args.get('file_type')

#     s3 = get_s3()

#     presigned_post = s3.generate_presigned_post(
#     Bucket = S3_BUCKET,
#     Key = file_name,
#     Fields = {"acl": "public-read", "Content-Type": file_type},
#         Conditions = [
#             {"acl": "public-read"},
#             {"Content-Type": file_type}
#         ],
#         ExpiresIn = 3600
#     )

#     return json.dumps({
#         'data': presigned_post,
#         'url': 'https://%s.s3.amazonaws.com/%s' % (S3_BUCKET, file_name)
#     })