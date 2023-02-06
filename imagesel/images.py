import os

from flask import (
    Blueprint, g, session, make_response
)
import boto3
import click

from imagesel.db import execute_query

bp = Blueprint('images', __name__, url_prefix='/images')


# Before all requests run blueprint
@bp.before_app_request
def load_logged_in_user():
    """If a user id is stored in the session, load the user object from."""
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


# Create new S3 connection
def create_s3():
    return boto3.client(
        "s3",
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
    )


# Get existing S3 connection (or create new one)
def get_s3():
    """Get S3 connection from global variable or create new one."""
    if 's3' not in g:
        g.s3 = create_s3()

    return g.s3


# Close S3 connection
def close_s3(error):
    """Close S3 connection."""
    if hasattr(g, 's3'):
        g.s3.close()


# Define init_app
def init_app(app):
    """Register database functions with the Flask app. This is called by the application factory."""
    app.teardown_appcontext(close_s3)
    app.cli.add_command(clear_db_command)


# Get image object from S3
def get_object(image_name, s3=None):
    """Get image object from S3."""
    if s3 is None:
        s3 = get_s3()
    obj = s3.get_object(Bucket=os.environ["AWS_BUCKET_NAME"], Key=image_name)

    return obj


# Upload image to S3
def upload_file(image, filename):
    """Upload image to S3."""
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
    """Delete file from S3."""
    s3 = get_s3()
    try:
        s3.delete_object(Bucket=os.environ["AWS_BUCKET_NAME"], Key=filename)
    except Exception:
        print(f"Amazon S3: File {filename} not found")


# Delete all images from S3
def delete_all_files():
    """Delete all images from S3."""""
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
    """Rename file in S3."""
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
    """Get image data from S3 and return it as a response."""
    # Get image object from S3
    img = get_object(filename)
    resp = make_response(img['Body'].read())
    resp.cache_control.max_age = 3600
    return resp
