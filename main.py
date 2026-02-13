from flask import *
from dotenv import load_dotenv
import os
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
import re
from bson.objectid import ObjectId
from datetime import datetime

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

    return render_template("dashboard.html")

@app.route("/orders", methods=["GET", "POST"])
def orders():

    # ================= CREATE ORDER =================
    if request.method == "POST" and request.form.get("action") == "create":

        cart_raw = request.form.get("cart_data")

        if not cart_raw:
            flash("Cart is empty!")
            return redirect("/orders")

        cart_data = json.loads(cart_raw)

        items = []
        total_amount = 0

        for product_id, item in cart_data.items():
            price = float(item.get("price", 0))
            qty = int(item.get("qty", 0))

            items.append({
                "product_id": product_id,
                "name": item.get("name"),
                "price": price,
                "qty": qty
            })

            total_amount += price * qty

        order_data = {
            "customer_name": request.form.get("customer_name"),
            "items": items,
            "total_amount": total_amount,
            "status": "Pending",
            "created_at": datetime.utcnow()
        }

        db.orders.insert_one(order_data)
        flash("Order Created Successfully!")
        return redirect("/orders")


    # ================= COMPLETE ORDER =================
    if request.method == "POST" and request.form.get("action") == "complete":

        order_id = request.form.get("order_id")
        if not order_id:
            return redirect("/orders")

        db.orders.update_one(
            {"_id": ObjectId(order_id)},
            {"$set": {
                "status": "Completed",
                "payment_method": request.form.get("payment_method"),
                "completed_at": datetime.utcnow()
            }}
        )

        return redirect("/orders")


    # ================= EDIT ORDER =================
    if request.method == "POST" and request.form.get("action") == "edit_order":

        order_id = request.form.get("order_id")
        cart_raw = request.form.get("cart_data")

        if not order_id or not cart_raw:
            flash("Invalid update request!")
            return redirect("/orders")

        cart_data = json.loads(cart_raw)

        items = []
        total_amount = 0

        for product_id, item in cart_data.items():
            price = float(item.get("price", 0))
            qty = int(item.get("qty", 0))

            items.append({
                "product_id": product_id,
                "name": item.get("name"),
                "price": price,
                "qty": qty
            })

            total_amount += price * qty

        db.orders.update_one(
            {"_id": ObjectId(order_id)},
            {"$set": {
                "customer_name": request.form.get("customer_name"),
                "items": items,
                "total_amount": total_amount,
                "updated_at": datetime.utcnow()
            }}
        )

        flash("Order Updated Successfully!")
        return redirect("/orders")


    # ================= CANCEL ORDER =================
    if request.method == "POST" and request.form.get("action") == "cancel":

        order_id = request.form.get("order_id")
        if not order_id:
            return redirect("/orders")

        db.orders.update_one(
            {"_id": ObjectId(order_id)},
            {"$set": {"status": "Cancelled"}}
        )

        return redirect("/orders")


    # ================= REFUND ORDER =================
    if request.method == "POST" and request.form.get("action") == "refund":

        order_id = request.form.get("order_id")
        if not order_id:
            return redirect("/orders")

        db.orders.update_one(
            {"_id": ObjectId(order_id)},
            {"$set": {
                "status": "Refunded",
                "refunded_at": datetime.utcnow()
            }}
        )

        flash("Order Refunded Successfully!")
        return redirect("/orders")


    # ================= REORDER (FIXED VERSION) =================
    # ================= REORDER (REACTIVATE VERSION) =================
    if request.method == "POST" and request.form.get("action") == "reorder":

        order_id = request.form.get("order_id")
        if not order_id:
            return redirect("/orders")

        db.orders.update_one(
            {"_id": ObjectId(order_id)},
            {"$set": {
                "status": "Pending",
                "created_at": datetime.utcnow(),
                "completed_at": None,
                "payment_method": None
            }}
        )

        flash("Order Re-Activated Successfully!")
        return redirect("/orders")



    # ================= GET DATA =================
    products = list(db.products.find())
    orders = list(db.orders.find().sort("created_at", -1))

    pending_count = db.orders.count_documents({"status": "Pending"})
    completed_count = db.orders.count_documents({"status": "Completed"})
    cancelled_count = db.orders.count_documents({"status": "Cancelled"})

    return render_template(
        "orders.html",
        products=products,
        orders=orders,
        pending_count=pending_count,
        completed_count=completed_count,
        cancelled_count=cancelled_count
    )



@app.route("/products", methods=["GET", "POST"])
def products():
    if request.method == "POST":

        action = request.form.get("action")
        if action == "create":
            db.products.insert_one({
                "name": request.form.get("name"),
                "description": request.form.get("description"),
                "category": request.form.get("category"),
                "price": float(request.form.get("price"))
            })

        # DELETE PRODUCT
        if action == "delete":
            db.products.delete_one({
                "_id": ObjectId(request.form.get("product_id"))
            })

        # ADD CATEGORY
        if action == "add_category":
            db.categories.insert_one({
                "name": request.form.get("category_name")
            })

        if action == "edit":
            db.products.update_one(
                {"_id": ObjectId(request.form.get("product_id"))},
                {"$set": {
                    "name": request.form.get("name"),
                    "description": request.form.get("description"),
                    "category": request.form.get("category"),
                    "price": float(request.form.get("price"))
                }}
            )


        return redirect("/products")
        

    products = list(db.products.find())
    categories = list(db.categories.find())

    return render_template("products.html",
                           products=products,
                           categories=categories)

if __name__ == "__main__":
    app.run(debug=True)