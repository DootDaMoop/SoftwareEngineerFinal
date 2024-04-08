import os
import pathlib
import requests
import json
from flask import Flask, session, abort, redirect, request, render_template
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
from pip._vendor import cachecontrol
import google.auth.transport.requests
from model.User import User
from user_repo.User_management import User_management
#FLASK_DEBUG=true flask run

app = Flask(__name__)

user = User()
user_management = User_management(r"user_repo\users.csv")


with open("client_secrets.json", 'r') as file:
    config = json.load(file)

    client_id = config['web']['client_id']
    project_id = config['web']['project_id']
    auth_uri = config['web']['auth_uri']
    token_uri = config['web']['token_uri']
    auth_provider_x509_cert_url = config['web']['auth_provider_x509_cert_url']
    client_secret = config['web']['client_secret']
    redirect_uris = config['web']['redirect_uris']

app.secret_key = client_secret

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

GOOGLE_CLIENT_ID = client_id
client_secrets_file = os.path.join(pathlib.Path(__file__).parent, "client_secrets.json")

flow = Flow.from_client_secrets_file(
    client_secrets_file=client_secrets_file,
    scopes=["https://www.googleapis.com/auth/userinfo.profile", "https://www.googleapis.com/auth/userinfo.email", "openid"],
    redirect_uri="http://127.0.0.1:5000/callback"
)


def login_is_required(function):
    def wrapper(*args, **kwargs):
        if "google_id" not in session:
            return abort(401)  # Authorization required
        else:
            return function()

    return wrapper


@app.get("/login")
def login():
    authorization_url, state = flow.authorization_url()
    session["state"] = state
    return redirect(authorization_url)


@app.get("/callback")
def callback():
    flow.fetch_token(authorization_response=request.url)

    if not session["state"] == request.args["state"]:
        abort(500)  # State does not match!

    credentials = flow.credentials
    request_session = requests.session()
    cached_session = cachecontrol.CacheControl(request_session)
    token_request = google.auth.transport.requests.Request(session=cached_session)

    id_info = id_token.verify_oauth2_token(
        id_token=credentials._id_token,
        request=token_request,
        audience=GOOGLE_CLIENT_ID
    )
    
    session["first_name"] = id_info.get("given_name")
    session["last_name"] = id_info.get("family_name")
    session["email"] = id_info.get("email")
    session["pfp"] = id_info.get("picture")
    session["google_id"] = id_info.get("sub")
    session["first_and_last"] = id_info.get("name")

    user.update_from_session(session)
    return redirect("/home")

@app.get("/logout")
def logout():
    session.clear()
    return redirect("/")


@app.get("/")
def index():
    return render_template('index.html')


@app.get('/registration')
def registration():
    return render_template('registration.html')

@app.get('/calendar')
def calendar():
    return render_template('calendar.html')


@app.post('/register')
def register():
    email = request.form['email']
    password = request.form['password']
    confirm_password = request.form['confirm_password']
    first_name = request.form['first_name']
    last_name = request.form['last_name']

    if not password == confirm_password:

        return "Passwords do not match. Please try again.", 400
    
    success, message = user_management.register_user(email, password, first_name, last_name)

    if success:
        user.update_from_registration(email, password, first_name, last_name)
        return redirect('/')
    else:
        return message, 400

    

@app.post('/login_manual')
def login_manual():

    user_exists, valid = user_management.validate_user(request.form["email"], request.form["password"])    

    if user_exists:
        session["email"] = request.form["email"]
        session["first_name"] = user_management.get_first_name_from_email(request.form["email"])
        session["last_name"] = user_management.get_last_name_from_email(request.form["email"])
        session["pfp"] = None
        session["google_id"] = None
        session["first_and_last"] = None
        user.update_from_session(session)

        return redirect("/home")
    else:
        return "Invalid email or password. Please try again.", 400




#the page you land after you log in 
@app.get("/home")
@login_is_required
def home():
    return render_template("home.html")


if __name__ == "__main__":
    app.run(debug=True)