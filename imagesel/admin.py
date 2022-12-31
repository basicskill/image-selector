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
@bp.route('/upload_image', methods=('GET', 'POST'))
@admin_required
def upload_image():

    # if request.method == 'POST':
    if 'file' not in request.files:
        flash('No file part')
    file = request.files['file']
    if file.filename == '':
        flash('No selected file')
    
    if file:
        execute_query("INSERT INTO images (blob, filename) VALUES (%s, %s)", (file.read(), file.filename), fetch=False)
        flash(f'Image "{file.filename}" uploaded successfully')

    return redirect(url_for('admin.dashboard'))