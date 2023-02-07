from datetime import timedelta
from math import ceil

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for, Response, current_app
)
from werkzeug.security import check_password_hash, generate_password_hash
import zipstream

from imagesel.db import execute_query, add_worker, log_action
from imagesel.auth import admin_required
from imagesel.images import (
    upload_file, rename_file, delete_file, get_object, create_s3
)
# Create admin blueprint
bp = Blueprint('admin', __name__, url_prefix='/admin')


# Before all requests run blueprint
@bp.before_app_request
def load_logged_in_user():
    """If a user id is stored in the session, load the user object from."""
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
        redirect(url_for('auth.login'))


# Route to admin page
@bp.route('/dashboard', methods=('GET', 'POST'))
@admin_required
def dashboard():
    """Admin dashboard page for managing users."""
    # Get all workers from workers table
    g.workers = execute_query(
        "SELECT * FROM workers"
    )

    if request.method == 'POST':
        username = request.form['username'].strip()
        error = None
        user = execute_query(
            "SELECT * FROM workers WHERE username = %s", (username,)
        )

        if len(user) > 0:
            error = 'Token already exists.'

        if error is None:
            # Add token to database
            acc_token = add_worker(username)

            # Log action
            log_action(f"User {username} with access token {acc_token} created")

            return redirect(url_for('admin.dashboard'))

        flash(error)

    return render_template("admin/dashboard.html")


@bp.route('/<int:id>/delete', methods=('POST',))
@admin_required
def delete(id):
    """Delete a user from the database with post request."""
    # Get token from database
    worker = execute_query('SELECT * FROM workers WHERE id = %s', (id,))

    # Delete token from database
    execute_query('DELETE FROM workers WHERE id = %s', (id,), fetch=False)

    # Log action
    log_action(f"User {worker[0]['username']} deleted")

    return redirect(url_for('admin.dashboard'))


# Delete class type from admins page
@bp.route('/<classification>/delete_classification', methods=('POST',))
@admin_required
def delete_classification(classification):
    """Delete a classification type from the database with post request."""
    # Fetch classes from admins table
    img_classes = execute_query('SELECT img_classes FROM admins')[0]['img_classes']

    # Remove class from list
    img_classes.remove(classification)

    # Update admins table
    execute_query('UPDATE admins SET img_classes = %s', (img_classes,), fetch=False)

    # Log action
    log_action(f"Class {classification} deleted")

    return redirect(url_for('admin.image_explorer'))


# Upload image
@bp.route('/upload_images', methods=('GET', 'POST'))
@admin_required
def upload_images():
    """Upload images to S3 bucket and register it in POSTGRES database."""
    if request.method == 'POST':
        # Get all images from request
        images = request.files.getlist("images")
        classification = request.form['classification']
        processing = request.form['processing']

        num_uploaded = 0
        # Loop through all images
        for image in images:
            # Check if image is not empty
            if image.filename != '':
                # Check if mimetype is image
                if image.mimetype.startswith('image/'):

                    # Save image to S3
                    filename = upload_file(image, image.filename)

                    # Save image metadata to database
                    execute_query("INSERT INTO images (filename, processing, classification) VALUES (%s, %s, %s)",
                        (filename, processing, classification),
                        fetch=False
                    )

                    # Log action
                    log_action(f"Image {filename} uploaded as {processing} with class {classification}") 
                    num_uploaded += 1

                else:
                    flash(f'File "{image.filename}" is not an image.')

        # flash(f'{num_uploaded} images uploaded successfully')

    return "ok"


# Image explorer page
@bp.route('/image_explorer', methods=('GET', 'POST'))
@admin_required
def image_explorer():
    """Image explorer page for viewing and managing images."""
    if request.method == 'POST':

        # Get choice field from request
        return redirect(url_for('admin.image_explorer', 
                processing=request.form.get('processing', 'all'),
                classification=request.form.get('classification', 'all'),
                curr_page=request.args.get('page', 1)))

    # Query img_classes field from admins table
    class_names = execute_query(
        "SELECT img_classes FROM admins LIMIT 1"
    )[0]['img_classes']

    unprocessed_classes = {}

    # Count number of unprocessed images
    unprocessed_classes['unprocessed'] = execute_query(
        "SELECT COUNT(*) FROM images WHERE processing = 'unprocessed'"
    )[0]['count']

    # Count number of images in holding
    unprocessed_classes['holding'] = execute_query(
        "SELECT COUNT(*) FROM images WHERE processing = 'holding'"
    )[0]['count']

    # Count number of images in each class
    class_counts = {}

    for class_name in class_names:
        class_counts[class_name] = execute_query(
            "SELECT COUNT(*) FROM images WHERE classification = %s AND processing = 'processed'", 
            (class_name,)
        )[0]['count']

    g.classes = class_counts
    g.unprocessed_classes = unprocessed_classes

    # Get processing and class from url
    processing = request.args.get("processing", 'all')
    classification = request.args.get("classification", 'all')

    # Generate image query if processing is "all" and class is "all"
    if processing == "all" and classification == "all":
        g.images = execute_query(
            "SELECT * FROM images"
        )

    # Generate image query if processing is "all" and class is not "all"
    elif processing == "all":
        g.images = execute_query(
            "SELECT * FROM images WHERE classification = %s", (classification,)
        )

    # Generate image query if processing is not "all" and class is "all"
    elif classification == "all":
        g.images = execute_query(
            "SELECT * FROM images WHERE processing = %s", (processing,)
        )

    # Generate image query if processing is not "all" and class is not "all"
    else:
        g.images = execute_query(
            "SELECT * FROM images WHERE classification = %s AND processing = %s", (classification, processing)
        )

    # Implement page scrolling
    page_size = current_app.config['PAGE_SIZE']
    g.pages = ceil(len(g.images) / page_size)
    curr_page = int(request.args.get('page', '1'))

    if curr_page > g.pages:
        curr_page = g.pages
    if curr_page < 1:
        curr_page = 1

    if g.pages == 0:
        curr_page = 0

    g.images = g.images[(curr_page - 1) * page_size: curr_page * page_size]

    return render_template("admin/image_explorer.html", processing=processing, classification=classification, curr_page=curr_page)


# Method for deleting multiple images
@bp.route('/delete_images', methods=('POST',))
@admin_required
def delete_images():
    """Delete multiple images from S3 bucket and database."""
    img_ids = request.form.keys()

    for img_id in img_ids:
        # Get image from database
        image = execute_query(
            "SELECT * FROM images WHERE id = %s", (img_id,)
        )[0]

        # Delete image from database
        execute_query("DELETE FROM images WHERE id = %s", (img_id,), fetch=False)

        # Delete image file
        delete_file(image['filename'])

        # Log action
        log_action(f"Image {image['filename']} deleted")

    return redirect(url_for('admin.image_explorer'))


# Decorator for adding class
@bp.route('/add_class', methods=('POST',))
@admin_required
def add_class():
    """Add new class to img_classes field in admins table."""
    # Get img_classes field from admins table
    classes = execute_query(
        "SELECT img_classes FROM admins"
    )

    # Get class from request
    new_class = request.form.get('new_class').strip()

    # Check if class is not empty
    if new_class:
        # Check if class already exists
        if new_class in classes[0]['img_classes']:
            flash(f'Class "{new_class}" already exists.')

        else:
            # Add class to img_classes field in admins table
            classes[0]['img_classes'].append(new_class)
            execute_query("UPDATE admins SET img_classes = %s", (classes[0]['img_classes'],), fetch=False)

            # Log action
            log_action(f"Class {new_class} added")

    return redirect(url_for('admin.image_explorer'))


# Edit image page
@bp.route('/<int:id>/edit_image', methods=('GET', 'POST'))
@admin_required
def edit_image(id):
    """Edit image in database and rename image file."""
    # Get image from database
    image = execute_query(
        "SELECT * FROM images WHERE id = %s", (id,)
    )[0]
    if request.method == 'POST':
        # Get form fields from request with get attribute
        classification = request.form.get('classification', image['classification'])
        processing = request.form.get('processing', image['processing'])
        filename = request.form.get('filename', image['filename'])

        # Update image in database
        execute_query("UPDATE images SET classification = %s, processing = %s, filename = %s WHERE id = %s",
            (classification, processing, filename, id), fetch=False)

        # Rename image file
        if filename != image['filename']:
            rename_file(image['filename'], filename)

        # Log action
        log_action(f"Image {image['filename']} edited to {processing} with class {classification}")

        # Redirect to edit image page
        return redirect(url_for('admin.edit_image', id=id))

    return render_template("admin/edit_image.html", image=image)


# Delete image
@bp.route('/<int:id>/delete_image', methods=('POST',))
@admin_required
def delete_image(id):
    """Delete image from S3 bucket and database."""
    # Get image from database
    image = execute_query(
        "SELECT * FROM images WHERE id = %s", (id,)
    )[0]

    # Delete image from database
    execute_query("DELETE FROM images WHERE id = %s", (id,), fetch=False)

    # Delete image file
    delete_file(image['filename'])

    # Log action
    log_action(f"Image {image['filename']} deleted")

    return redirect(url_for('admin.image_explorer'))


# Page to change admin password
@bp.route('/change_password', methods=('GET', 'POST'))
@admin_required
def change_password():
    if request.method == 'POST':
        # Get form fields from request
        old_password = request.form['old_password'].strip()
        new_password = request.form['new_password'].strip()
        confirm_password = request.form['confirm_password'].strip()

        # Get admin from database
        admin = execute_query(
            "SELECT * FROM admins WHERE username = 'admin'"
        )[0]

        # Check if old password is correct
        if not check_password_hash(admin['password'], old_password):
            flash('Incorrect password.')
            return redirect(url_for('admin.change_password'))

        # Check if new password and confirm password are the same
        if new_password != confirm_password:
            flash('New password and confirm password are not the same.')
            return redirect(url_for('admin.change_password'))

        # Update admin password in database
        execute_query("UPDATE admins SET password = %s WHERE username = 'admin'",
            (generate_password_hash(new_password),),
            fetch=False
        )
        flash("Password changed successfully")

        # Log action
        log_action(f"Admin password changed")

    return render_template("admin/change_password.html")


# Page to download database
@bp.route('/download_data', methods=('GET', 'POST'))
@admin_required
def download_data():
    """Download database as zip file from S3."""
    if request.method == 'POST':
        # Create zip file
        z = zipstream.ZipFile(mode='w', compression=zipstream.ZIP_DEFLATED)
        # Query all classes from admin table
        classes = execute_query(
            "SELECT img_classes FROM admins"
        )[0]['img_classes']

        # Get images from database
        for classification in classes:
            images = execute_query(
                "SELECT * FROM images WHERE classification = %s AND processing = 'processed'", (classification,)
            )
            # Create folder for each class
            #z.writestr(f"{classification}/", bytes())

            # Add images to zip file
            for image in images:
                file_name = image['filename']
                def generator():
                    yield get_object(file_name, create_s3())['Body'].read()
                z.write_iter(f"{classification}/{file_name}", generator())

        response = Response(z, mimetype='application/zip')
        response.headers['Content-Disposition'] = 'attachment; filename=processed_images.zip'
        return response

    # Get all logs from database
    logs = execute_query(
        "SELECT * FROM logs"
    )

    logs_content = ""

    for log in reversed(logs):
        logs_content += f"{log['created']} - {log['textmsg']}\n\n"

    return render_template("admin/download_data.html", logs_content=logs_content)


# Define user page page
@bp.route('/user_page/<worker_name>', methods=('GET', 'POST'))
@admin_required
def user_page(worker_name):
    """Display user page with user information and banned classes."""
    # Get user from database
    worker = execute_query(
        "SELECT * FROM workers WHERE username = %s", (worker_name,)
    )[0]

    worker_eligible = {class_name: num_labeled for class_name, num_labeled in zip(worker['eligible_classes'], worker['num_labeled'])}
    label_time = {class_name: f"{int(t//60):02}:{int(t%60):02}" for class_name, t in zip(worker['eligible_classes'], worker['cumulative_time_spent'])}

    # Select all banned classes for worker
    banned_classes = execute_query("SELECT * FROM banned WHERE worker_id = %s", (worker['id'],))

    # Calculate ban expiration date for each class
    for idx in range(len(banned_classes)):
        cls = banned_classes[idx]
        cls['ban_expiration'] = cls['created'] + timedelta(days=current_app.config['BAN_DELETE_PERIOD'])
        banned_classes[idx] = cls

    # Select all logs for worker
    worker_logs = execute_query("SELECT * FROM logs WHERE worker_id = %s", (worker['id'],))

    # Group activities and banned classes and sort by "created"
    # Create log text for activities
    log_txt = ""
    for txt in sorted(worker_logs, key=lambda x: x['created'], reverse=True):
        log_txt += f"{txt['created']} - {txt['textmsg']}\n\n"

    return render_template("admin/user.html", worker=worker, worker_eligible=worker_eligible,
        banned_classes=banned_classes, log_txt=log_txt, label_time=label_time)


# Delete user eligible class
@bp.route('/user_page/<worker_name>/delete_eligible_class/<class_name>', methods=('POST',))
@admin_required
def delete_eligible_class(worker_name, class_name):
    """Delete eligible class for user."""
    # Get user from database
    worker = execute_query(
        "SELECT * FROM workers WHERE username = %s", (worker_name,)
    )[0]

    # Get index of class in eligible
    class_idx = worker['eligible_classes'].index(class_name)
    print(class_idx)

    # Delete class from eligible
    worker['eligible_classes'].pop(class_idx)

    # Delete num_labeled for class
    worker['num_labeled'].pop(class_idx)

    # Delete cumulative_time_spent for class
    worker['cumulative_time_spent'].pop(class_idx)

    # Write to database
    execute_query("UPDATE workers SET eligible_classes = %s, num_labeled = %s WHERE username = %s",
        (worker['eligible_classes'], worker['num_labeled'], worker_name), fetch=False)

    # Log action
    log_action(f"Class {class_name} deleted from eligible classes for worker {worker_name}")

    # Return to user page
    return redirect(url_for('admin.user_page', worker_name=worker_name))


# Delete ban for user in banned table
@bp.route('/user_page/<worker_name>/delete_ban/<class_name>', methods=('POST',))
@admin_required
def delete_ban(worker_name, class_name):
    """Delete ban for user."""
    # Get user from database
    worker = execute_query(
        "SELECT * FROM workers WHERE username = %s", (worker_name,)
    )[0]

    # Get ban from database
    ban = execute_query("SELECT * FROM banned WHERE worker_id = %s AND class = %s", (worker['id'], class_name))[0]

    # Delete ban from database
    execute_query("DELETE FROM banned WHERE id = %s", (ban['id'],), fetch=False)

    # Log action
    log_action(f"Ban for class {class_name} deleted for worker {worker_name}")

    # Return to user page
    return redirect(url_for('admin.user_page', worker_name=worker_name))
