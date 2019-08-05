import os

from flask import Flask, render_template, request, flash, redirect, session, g
from flask_debugtoolbar import DebugToolbarExtension
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_

from forms import UserAddForm, LoginForm, MessageForm, UserUpdateForm, DirectMessageForm
from models import db, connect_db, User, Message, LikedMessage, DirectMessage

CURR_USER_KEY = "curr_user"

app = Flask(__name__)

# Get DB_URI from environ variable (useful for production/testing) or,
# if not set there, use development local db.
app.config['SQLALCHEMY_DATABASE_URI'] = (
    os.environ.get('DATABASE_URL', 'postgres:///warbler'))

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ECHO'] = False
app.config['DEBUG_TB_INTERCEPT_REDIRECTS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', "it's a secret")
toolbar = DebugToolbarExtension(app)

connect_db(app)


##############################################################################
# User signup/login/logout


@app.before_request
def add_user_to_g():
    """If we're logged in, add curr user to Flask global."""

    if CURR_USER_KEY in session:
        g.user = User.query.get(session[CURR_USER_KEY])

    else:
        g.user = None


def do_login(user):
    """Log in user."""

    session[CURR_USER_KEY] = user.id


def do_logout():
    """Logout user."""

    if CURR_USER_KEY in session:
        del session[CURR_USER_KEY]


@app.route('/signup', methods=["GET", "POST"])
def signup():
    """Handle user signup.

    Create new user and add to DB. Redirect to home page.

    If form not valid, present form.

    If the there already is a user with that username: flash message
    and re-present form.
    """

    form = UserAddForm()

    if form.validate_on_submit():
        try:
            user = User.signup(
                username=form.username.data,
                password=form.password.data,
                email=form.email.data,
                image_url=form.image_url.data or User.image_url.default.arg,
            )
            db.session.commit()

        except IntegrityError as e:
            flash("Username already taken", 'danger')
            return render_template('users/signup.html', form=form)

        do_login(user)

        return redirect("/")

    else:
        return render_template('users/signup.html', form=form)


@app.route('/login', methods=["GET", "POST"])
def login():
    """Handle user login."""

    form = LoginForm()

    if form.validate_on_submit():
        user = User.authenticate(form.username.data,
                                 form.password.data)

        if user:
            do_login(user)
            flash(f"Hello, {user.username}! success")
            return redirect("/")

        flash("Invalid credentials.", 'danger')

    return render_template('users/login.html', form=form)


@app.route('/logout')
def logout():
    """Handle logout of user."""

    # remove user from session
    do_logout()

    # redirect to login page
    flash("You successfully logged out.")
    return redirect("/login")


##############################################################################
# General user routes:

@app.route('/users')
def list_users():
    """Page with listing of users.

    Can take a 'q' param in querystring to search by that username.
    """

    search = request.args.get('q')

    if not search:
        users = User.query.all()
    else:
        users = User.query.filter(User.username.like(f"%{search}%")).all()

    return render_template('users/index.html', users=users)


@app.route('/users/<int:user_id>')
def users_show(user_id):
    """Show user profile."""

    user = User.query.get_or_404(user_id)

    if user.private and g.user:
        messages = user.show_private_account_messages(g.user)
        # if g.user:
        #     if user in g.user.following:
        #         messages = user.show_messages()
        #     else:
        #         messages = []

    else:
        messages = user.show_messages()
    # snagging messages in order from the database;
    # user.messages won't be in order by default

    # If the current user is on their page,
    # they can see their direct messages
    # else they cant see the messages
    if g.user.id == user_id:
        # Get all the direct messages
        direct_messages = DirectMessage.query.all()
        # import pdb; pdb.set_trace()
        # Have fix message.user_to / message.user_from
        # to use to filter direct_messages
    else:
        direct_messages = []

    return render_template('users/show.html', user=user, messages=messages, direct_messages=direct_messages, user_id=user_id)


@app.route('/users/<int:user_id>/following')
def show_following(user_id):
    """Show list of people this user is following."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    user = User.query.get_or_404(user_id)
    return render_template('users/following.html', user=user)


@app.route('/users/<int:user_id>/followers')
def users_followers(user_id):
    """Show list of followers of this user."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    user = User.query.get_or_404(user_id)
    return render_template('users/followers.html', user=user)


@app.route('/users/follow/<int:follow_id>', methods=['POST'])
def add_follow(follow_id):
    """Add a follow for the currently-logged-in user."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    followee = User.query.get_or_404(follow_id)
    g.user.following.append(followee)
    db.session.commit()

    return redirect(f"/users/{g.user.id}/following")


@app.route('/users/stop-following/<int:follow_id>', methods=['POST'])
def stop_following(follow_id):
    """Have currently-logged-in-user stop following this user."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    followee = User.query.get(follow_id)
    g.user.following.remove(followee)
    db.session.commit()

    return redirect(f"/users/{g.user.id}/following")


@app.route('/users/profile', methods=["GET", "POST"])
def profile():
    """Update profile for current user."""

    user = User.query.filter_by(username=g.user.username).first()

    form = UserUpdateForm(obj=user)

    if form.validate_on_submit():
        password = form.password.data

        authenticated = user.authenticate(g.user.username, password)

        if authenticated:
            user.username = form.username.data
            user.email = form.email.data
            user.image_url = form.image_url.data
            user.header_image_url = form.header_image_url.data
            user.bio = form.bio.data
            user.private = form.private.data
            db.session.commit()

            return redirect(f"/users/{g.user.id}")

        else:
            flash("Not authenticated")
            return redirect('/')

    return render_template("users/edit.html", form=form)


@app.route('/users/delete', methods=["POST"])
def delete_user():
    """Delete user."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    do_logout()

    db.session.delete(g.user)
    db.session.commit()

    return redirect("/signup")


@app.route('/users/<int:user_id>/likes')
def like_count(user_id):
    user = User.query.get_or_404(user_id)
    return render_template('users/likes.html', user=user)


##############################################################################
# Messages routes:

@app.route('/messages/new', methods=["GET", "POST"])
def messages_add():
    """Add a message:

    Show form if GET. If valid, update message and redirect to user page.
    """

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    form = MessageForm()

    if form.validate_on_submit():
        msg = Message(text=form.text.data)
        g.user.messages.append(msg)
        db.session.commit()

        return redirect(f"/users/{g.user.id}")

    return render_template('messages/new.html', form=form)


@app.route('/messages/<int:message_id>', methods=["GET"])
def messages_show(message_id):
    """Show a message."""

    msg = Message.query.get(message_id)
    return render_template('messages/show.html', message=msg)


@app.route('/messages/<int:message_id>/delete', methods=["POST"])
def messages_destroy(message_id):
    """Delete a message."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    msg = Message.query.get(message_id)
    db.session.delete(msg)
    db.session.commit()

    return redirect(f"/users/{g.user.id}")


@app.route('/messages/<int:msg_id>/like/add', methods=["POST"])
def add_like(msg_id):
    """ If user clicks button check if message exists in liked message table. if a exists, remove from db. Else add to db"""

    message_exists = LikedMessage.query.filter_by(
        message_id=msg_id, user_id=g.user.id).first()

    if message_exists:
        db.session.delete(message_exists)

    else:
        new_messsage = LikedMessage(message_id=msg_id, user_id=g.user.id)
        db.session.add(new_messsage)

    db.session.commit()
    return redirect('/')

##############################################################################
# Homepage and error pages


@app.route('/')
def homepage():
    """Show homepage:

    - anon users: no messages
    - logged in: 100 most recent messages of followees
    """

    if g.user:

        # grabs all users' ids the user is following
        user_following = [user.id for user in g.user.following]

        # grabs all messages for user and user following
        messages = (Message
                    .query
                    .filter(or_(Message.user_id.in_(user_following), Message.user_id == g.user.id))
                    .order_by(Message.timestamp.desc())
                    .limit(100)
                    .all())

        return render_template('home.html', messages=messages)

    else:
        return render_template('home-anon.html')


##############################################################################
# Turn off all caching in Flask
#   (useful for dev; in production, this kind of stuff is typically
#   handled elsewhere)
#
# https://stackoverflow.com/questions/34066804/disabling-caching-in-flask

@app.after_request
def add_header(req):
    """Add non-caching headers on every request."""

    req.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    req.headers["Pragma"] = "no-cache"
    req.headers["Expires"] = "0"
    req.headers['Cache-Control'] = 'public, max-age=0'
    return req


@app.route('/messages/direct-message/new/<int:message_to_user_id>', methods=["GET", "POST"])
def direct_messsage(message_to_user_id):
    form = DirectMessageForm()
    if form.validate_on_submit():
        msg_text = request.form.get("message")
        new_direct_msg = DirectMessage(
            text=form.text.data,
            user_from_id=g.user.id,
            user_to_id=message_to_user_id
        )
        db.session.add(new_direct_msg)
        db.session.commit()
        return redirect(f"/users/{g.user.id}")
    else:
        return render_template('/messages/new_direct_message.html', form=form)
