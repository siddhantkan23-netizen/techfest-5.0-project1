from flask import *
from dotenv import load_dotenv
import os
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
import re

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")
client = MongoClient(os.getenv("MONGO_URI"))
db = client[os.getenv("DB_NAME")]
users_collection = db["users"]



links = [
    {"index" : "/"},
    {"signup" : "/signup"},
    {"login" : "/login"},
    {"logout" : "/logout"},
    {"dashboard" : "/dashboard"},
]

@app.route("/")
def index():
    return render_template("index.html", links=links)

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        phone = request.form.get("phone")
        shop_name = request.form.get("shop_name")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")
        if password != confirm_password:
            flash("Passwords do not match!")
            return redirect("/signup")

        if users_collection.find_one({"email": email}):
            flash("Email already registered!")
            return redirect("/signup")
        hashed_password = generate_password_hash(password)
        user_data = {
            "name": name,
            "email": email,
            "phone": phone,
            "shop_name": shop_name,
            "password": hashed_password
        }

        users_collection.insert_one(user_data)

        flash("Account created successfully! Please login.")
        return redirect("/login")

    elif request.method == "GET":
        return render_template("signup.html")
    
    else:
        return "Unknown Request Method"

@app.route("/login", methods=["POST", "GET"])
def login():
    if request.method == "POST":
        identifier = request.form.get("identifier")  # email OR phone
        password = request.form.get("password")

        # Search user by email OR phone
        user = users_collection.find_one({
            "$or": [
                {"email": identifier},
                {"phone": identifier}
            ]
        })
        print(user)

        if not user:
            flash("Invalid Credentials!")
            return redirect("/login")

        if not check_password_hash(user["password"], password):
            flash("Invalid Credentials!")
            return redirect("/login")

        # Create session
        session["user_id"] = str(user["_id"])
        session["user_name"] = user["name"]

        flash("Login successful!")
        return redirect("/dashboard")

    elif request.method == "GET":
        return render_template("login.html")

    else:
        return "Unknown Request Method" 

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully!")
    return redirect("/login")

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")

    return f"Welcome {session['user_name']}! This is your dashboard."


if __name__ == "__main__":
    app.run(debug=True)