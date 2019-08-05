# Warbler

Warbler is a full stack Python Twitter clone built with Flask where users can create and edit their profile, make tweets, follow other users, like tweets, comment on tweets and send direct messages.

The front-end is built using Jinja templating engine and features secure login and authentication using flask sessions and bcrypt. 

On the back-end, user data and user profiles are stored in a PostgreSQL database. Individual components of Warbler are tested using the unittest module following Test Driven Development conventions.

![Warbler Gif](https://github.com/kamosah7/warbler/blob/master/images/warbler.gif "Warbler Gif")

**To run this repository locally:**

1. `git clone`
2. `python3 -m venv venv`
3. `source venv/bin/activate`
4. `pip3 install -r requirements.txt`

*Start the backend server*
1. `createdb warbler`
2. `python3 seed.py`
3. `flask run`

Collaborators: https://github.com/oliviah0/