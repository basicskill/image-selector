import functools, sys

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for, abort, current_app
)
from werkzeug.security import check_password_hash

from imagesel.db import execute_query, add_user
from imagesel.auth import login_required, admin_required
import base64

# Create admin blueprint
bp = Blueprint('worker', __name__, url_prefix='/worker')

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

# Define worker page
@bp.route('/selection_choice', methods=('GET', 'POST'))
@login_required
def selection_choice():
    # If user is not in selection choice status, redirect to testing page
    if g.user["selected_class"] != "non":
        return redirect(url_for('worker.testing'))

    
    error = None
    if request.method == 'POST':
        choice = request.form['choice']
        if error is None:
            # Update user's inprogress to true and selected_class to choice
            execute_query(
                "UPDATE tokens SET selected_class = %s, inprogress = TRUE WHERE id = %s",
                (choice, g.user["id"]),
                fetch=False
            )

            return redirect(url_for('worker.testing'))

        flash(error)

    return render_template("worker/selection_choice.html")

@bp.route('/testing', methods=('GET', 'POST'))
@login_required
def testing():
    # If user is not in testing status, redirect to selection choice page
    if not g.user.get("inprogress"):
        return redirect(url_for('worker.selection_choice'))

    if "selected_image_ids" not in session:
        # Query 4 random images from database where classification is equal to user's selected class
        # and processing is equal to processed
        session["selected_image_ids"] = [row["id"] for row in execute_query(
            "SELECT id FROM images WHERE classification = %s AND processing = 'processed' ORDER BY RANDOM() LIMIT 4",
            (g.user["selected_class"],)
        )]

        # Query 2 random images from database where processing is equal to unprocessed
        session["selected_image_ids"] += [row["id"] for row in execute_query(
            "SELECT id FROM images WHERE processing = 'unprocessed' ORDER BY RANDOM() LIMIT 2",
            ()
        )]

        session["session_classes"] = [True] * 4 + [False] * 2

        # TODO: Shuffle selected images and classes in random order


    # Query images from database with id from session selected_image_ids
    selected_images = []
    for image_id in session["selected_image_ids"]:
        image = execute_query(
            "SELECT * FROM images WHERE id = %s", (image_id,)
        )[0]
        selected_images.append(image)

    return render_template("worker/testing.html", selected_images=selected_images)


# Show selected image
@bp.route('/<filename>/img')
@login_required
def img(filename):
    # Query image from database
    image = execute_query(
        "SELECT * FROM images WHERE filename = %s",
        (filename,)
    )[0]
    image["base64"] = base64.b64encode(image["blob"].tobytes()).decode()

    return render_template("worker/img.html", image=image)

# Submit selected image
@bp.route('/submit', methods=('POST',))
@login_required
def submit():
    # Get selected image id from request
    selected_image_id = request.form.keys()

    # Check if user selected anything
    if not selected_image_id:
        flash("Select at least one image")
        return redirect(url_for('worker.testing'))

    # Count number of selected images with classification of session selected class
    selected_count = execute_query(
        "SELECT COUNT(*) FROM images WHERE id IN %s AND classification = %s AND processing = 'processed'",
        (tuple(selected_image_id), g.user["selected_class"])
    )[0]["count"]

    # Check if selected count is enough to pass to next stage
    # Threshold is read from config file
    if selected_count >= current_app.config["NUM_CORRECT"]:
        # Change selected images which are unprocessed to holding
        # and change their class count to 1
        execute_query(
            f"UPDATE images SET processing = 'holding', {g.user['selected_class'].lower()}_count = 1 WHERE id IN %s AND processing = 'unprocessed'",
            (tuple(selected_image_id),),
            fetch=False
        )
        # Set user labeling to true
        execute_query(
            "UPDATE tokens SET labeling = TRUE WHERE id = %s",
            (g.user["id"],),
            fetch=False
        )

        # Clear slected image ids from session
        session.pop("selected_image_ids", None)

        return redirect(url_for('worker.labeling'))

    # Else show feedback page and delete token from database
    else:
        execute_query(
            "DELETE FROM tokens WHERE id = %s",
            (g.user["id"],),
            fetch=False
        )

        # Delete session
        session.clear()

        return render_template("worker/feedback.html")


    return redirect(url_for('worker.testing'))

# Define labeling page
@bp.route('/labeling', methods=('GET', 'POST'))
@login_required
def labeling():
    print(g.user.get("labeling"))
    if not g.user.get("labeling"):
        return redirect(url_for('worker.selection_choice'))
    
    # Choose 6 random images from database where processing is not equal to processed
    session["selected_image_ids"] = [row["id"] for row in execute_query(
        "SELECT * FROM images WHERE processing != 'processed' ORDER BY RANDOM() LIMIT 4",
        ()
    )]

    # Query images from database with id from session selected_image_ids and apply base64 encoding
    selected_images = []
    for image_id in session["selected_image_ids"]:
        image = execute_query(
            "SELECT * FROM images WHERE id = %s", (image_id,)
        )[0]
        selected_images.append(image)
    
    return render_template("worker/labeling.html", selected_images=selected_images)


# Submit selected images for labeling
@bp.route('/labeling_submit', methods=('POST',))
@login_required
def labeling_submit():
    """Update counts of selected images and change their processing to holding or processed."""

    # Get selected image id from request
    selected_image_id = request.form.keys()

    # Set processing of all selected images to holding
    execute_query(
        "UPDATE images SET processing = 'holding' WHERE id IN %s",
        (tuple(selected_image_id),),
        fetch=False
    )

    # Update counts of selected images
    for image_id in selected_image_id:
        execute_query(
            f"UPDATE images SET {g.user['selected_class'].lower()}_count = {g.user['selected_class'].lower()}_count + 1 WHERE id = %s",
            (image_id,),
            fetch=False
        )

        # If count is bigger then threshold, change processing to processed
        if execute_query(
            f"SELECT {g.user['selected_class'].lower()}_count FROM images WHERE id = %s",
            (image_id,)
        )[0][f"{g.user['selected_class'].lower()}_count"] >= current_app.config["NUM_CORRECT"]:
            execute_query(
                "UPDATE images SET processing = 'processed' WHERE id = %s",
                (image_id,),
                fetch=False
            )
        
    # Clear session
    session.clear()

    # Delete user from database
    execute_query(
        "DELETE FROM tokens WHERE id = %s",
        (g.user["id"],),
        fetch=False
    )

    # Redirect to feedback page
    return render_template("worker/feedback.html")

