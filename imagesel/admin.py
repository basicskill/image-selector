import functools

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for, abort
)
from werkzeug.security import check_password_hash

from imagesel.db import execute_query, add_user
from imagesel.auth import login_required, admin_required

# Create admin blueprint
bp = Blueprint('admin', __name__, url_prefix='/admin')

# Before all requests run blueprint
@bp.before_app_request
def load_logged_in_user():
    user_id = session.get('user_id')

    if user_id is None:
        g.user = None
    else:
        g.user = execute_query(
            "SELECT * FROM tokens WHERE id = %s", (user_id,)
        )[0]

# Route to admin page
@bp.route('/dashboard', methods=('GET', 'POST'))
@admin_required
def dashboard():
    
    # Get all tokens from tokens table
    g.tokens = execute_query(
        "SELECT * FROM tokens WHERE token != 'admin'"
    )

    if request.method == 'POST':
        token = request.form['token']
        error = None
        user = execute_query(
            "SELECT * FROM tokens WHERE token = %s", (token,)
        )

        if len(user) > 0:
            error = 'Token already exists.'

        if error is None:
            add_user(token, "")
            return redirect(url_for('admin.dashboard'))

        flash(error)

    return render_template("dashboard.html")

@bp.route('/<int:id>/delete', methods=('POST',))
@admin_required
def delete(id):
    execute_query('DELETE FROM tokens WHERE id = %s', (id,), fetch=False)

    return redirect(url_for('admin.dashboard'))


# Upload image
@bp.route('/upload_images', methods=('GET', 'POST'))
@admin_required
def upload_images():

    if request.method == 'POST':
        # Get all images from request
        images = request.files.getlist("images")

        # Loop through all images
        for image in images:
            # Check if image is not empty
            if image.filename != '':
                # Check if mimetype is image
                if image.mimetype.startswith('image/'):
                    # Insert image into database
                    execute_query("INSERT INTO images (blob, filename) VALUES (%s, %s)", (image.read(), image.filename), fetch=False)
                    flash(f'Image NOT "{image.filename}" uploaded successfully')
                else:
                    flash(f'File "{image.filename}" is not an image.')

    return redirect(url_for('admin.dashboard'))