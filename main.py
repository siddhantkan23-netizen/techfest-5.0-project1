from flask import *
from dotenv import load_dotenv
import os
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
import re
from bson.objectid import ObjectId
from datetime import datetime, timedelta

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
    if "user_id" not in session:
        return redirect("/login")


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
            "user_id": session["user_id"],
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
    products = list(db.products.find({
    "user_id": session["user_id"]}))
    orders = list(db.orders.find({"user_id": session["user_id"]}).sort("created_at", -1))

    pending_count = db.orders.count_documents({"user_id": session["user_id"],"status": "Pending"})
    completed_count = db.orders.count_documents({"user_id": session["user_id"],"status": "Completed"})
    cancelled_count = db.orders.count_documents({"user_id": session["user_id"],"status": "Cancelled"})

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
    if "user_id" not in session:
        return redirect("/login")
    
    if request.method == "POST":

        action = request.form.get("action")
        if action == "create":
            db.products.insert_one({
                "user_id": session["user_id"],
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
                "user_id": session["user_id"],
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
        

    products = list(db.products.find({
    "user_id": session["user_id"]
}))
    categories = list(db.categories.find({
    "user_id": session["user_id"]
}))

    return render_template("products.html",
                           products=products,
                           categories=categories)

@app.route("/expenses", methods=["GET", "POST"])
def expenses():
    if "user_id" not in session:
        return redirect("/login")
    # ================= ADD EXPENSE =================
    if request.method == "POST" and request.form.get("action") == "create":

        title = request.form.get("title")
        amount = float(request.form.get("amount", 0))
        category = request.form.get("category")
        description = request.form.get("description")

        expense_data = {
            "user_id": session["user_id"],
            "title": title,
            "amount": amount,
            "category": category,
            "description": description,
            "date": datetime.utcnow(),
            "created_at": datetime.utcnow()
        }

        db.expenses.insert_one(expense_data)
        flash("Expense Added Successfully!")
        return redirect("/expenses")

    # ================= DELETE EXPENSE =================
    if request.method == "POST" and request.form.get("action") == "delete":

        expense_id = request.form.get("expense_id")

        db.expenses.delete_one({
            "_id": ObjectId(expense_id)
        })

        flash("Expense Deleted!")
        return redirect("/expenses")
    
    if request.method == "POST" and request.form.get("action") == "edit":
        expense_id = request.form.get("expense_id")

        db.expenses.update_one(
            {"_id": ObjectId(expense_id)},
            {"$set": {
                "title": request.form.get("title"),
                "amount": float(request.form.get("amount")),
                "category": request.form.get("category"),
                "updated_at": datetime.utcnow()
            }}
        )

        flash("Expense Updated Successfully!")
        return redirect("/expenses")

    # ================= GET DATA =================
    expenses = list(db.expenses.find({"user_id": session["user_id"]}).sort("date", -1))

    total_expense = sum(e["amount"] for e in expenses)

    return render_template(
        "expenses.html",
        expenses=expenses,
        total_expense=total_expense
    )

@app.route("/profile", methods=["GET", "POST"])
def profile():
    if "user_id" not in session:
        return redirect("/login")
    user = db.users.find_one({"_id": ObjectId(session["user_id"])})

    if request.method == "POST":

        update_data = {
            "name": request.form.get("name"),
            "email": request.form.get("email"),
            "phone": request.form.get("phone"),
            "shop_name": request.form.get("shop_name"),
            "updated_at": datetime.utcnow()
        }

        # ================= PASSWORD CHANGE =================
        old_password = request.form.get("old_password")
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")

        if old_password and new_password:

            # Check old password
            if not check_password_hash(user["password"], old_password):
                flash("Old password is incorrect!")
                return redirect("/profile")

            if new_password != confirm_password:
                flash("New passwords do not match!")
                return redirect("/profile")

            update_data["password"] = generate_password_hash(new_password)

        db.users.update_one(
            {"_id": user["_id"]},
            {"$set": update_data}
        )

        flash("Profile Updated Successfully!")
        return redirect("/profile")

    return render_template("profile.html", user=user)

@app.route("/employees", methods=["GET", "POST"])
def employees():
    if "user_id" not in session:
        return redirect("/login")
    # ================= ADD POSITION =================
    if request.method == "POST" and request.form.get("action") == "add_position":

        position_name = request.form.get("position_name")

        if position_name:
            db.positions.insert_one({
                "user_id": session["user_id"],
                "name": position_name,
                "created_at": datetime.utcnow()
            })
            flash("Position added successfully!", "success")

        return redirect("/employees")

    # ================= ADD EMPLOYEE =================
    if request.method == "POST" and request.form.get("action") == "create":

        employee_data = {
            "user_id": session["user_id"],
            "name": request.form.get("name"),
            "email": request.form.get("email"),
            "phone": request.form.get("phone"),
            "position": request.form.get("position"),
            "salary": float(request.form.get("salary", 0)),
            "created_at": datetime.utcnow()
        }

        db.employees.insert_one(employee_data)
        flash("Employee added successfully!", "success")
        return redirect("/employees")

    # ================= EDIT EMPLOYEE =================
    if request.method == "POST" and request.form.get("action") == "edit":

        employee_id = request.form.get("employee_id")

        db.employees.update_one(
            {"_id": ObjectId(employee_id)},
            {"$set": {
                "name": request.form.get("name"),
                "email": request.form.get("email"),
                "phone": request.form.get("phone"),
                "position": request.form.get("position"),
                "salary": float(request.form.get("salary", 0)),
                "updated_at": datetime.utcnow()
            }}
        )

        flash("Employee updated successfully!", "success")
        return redirect("/employees")

    # ================= DELETE EMPLOYEE =================
    if request.method == "POST" and request.form.get("action") == "delete":

        employee_id = request.form.get("employee_id")
        db.employees.delete_one({"_id": ObjectId(employee_id)})

        flash("Employee deleted successfully!", "danger")
        return redirect("/employees")

    # ================= GET DATA =================
    employees = list(db.employees.find({
        "user_id": session["user_id"]
    }).sort("created_at", -1))

    positions = list(db.positions.find({
        "user_id": session["user_id"]
    }).sort("name", 1))


    return render_template(
        "employees.html",
        employees=employees,
        positions=positions
    )

@app.route("/attendance", methods=["GET", "POST"])
def attendance():
    if "user_id" not in session:
        return redirect("/login")
    # ================= TODAY RANGE =================
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    # ================= MARK ATTENDANCE =================
    if request.method == "POST" and request.form.get("action") == "mark":

        employee_id = request.form.get("employee_id")
        status = request.form.get("status")

        # Check if already marked today
        existing = db.attendance.find_one({
            "employee_id": str(employee_id),
            "date": {
                "$gte": today_start,
                "$lt": today_end
            }
        })

        if existing:
            db.attendance.update_one(
                {"_id": existing["_id"]},
                {"$set": {"status": status}}
            )
        else:
            db.attendance.insert_one({
                "user_id": session["user_id"],
                "employee_id": str(employee_id),  # force string
                "date": datetime.utcnow(),
                "status": status
            })


        flash("Attendance updated successfully!", "success")
        return redirect("/attendance")

    # ================= GET DATA =================
    employees = list(db.employees.find({
    "user_id": session["user_id"]
}))

    attendance_records = list(db.attendance.find({
        "user_id": session["user_id"],
        "date": {
            "$gte": today_start,
            "$lt": today_end
        }
    }))


    attendance_map = {
        record["employee_id"]: record["status"]
        for record in attendance_records
    }

    return render_template(
        "attendance.html",
        employees=employees,
        attendance_map=attendance_map,
        today=today_start
    )
@app.route("/salary", methods=["GET", "POST"])
def salary():
    if "user_id" not in session:
        return redirect("/login")
    today = datetime.utcnow()
    current_month = today.month
    current_year = today.year

    # ================= MONTH RANGE =================
    month_start = datetime(current_year, current_month, 1)

    if current_month == 12:
        month_end = datetime(current_year + 1, 1, 1)
    else:
        month_end = datetime(current_year, current_month + 1, 1)

    # ================= GIVE SALARY =================
    if request.method == "POST" and request.form.get("action") == "pay":

        employee_id = request.form.get("employee_id")

        db.salary.update_one(
            {
                "user_id": session["user_id"],
                "employee_id": str(employee_id),
                "month": current_month,
                "year": current_year
            },
            {
                "$set": {
                    "status": "Paid",
                    "paid_at": datetime.utcnow()
                }
            },
            upsert=True
        )

        flash("Salary Distributed Successfully!", "success")
        return redirect("/salary")

    # ================= FETCH DATA =================
    employees = list(db.employees.find({
    "user_id": session["user_id"]
}))
    salary_data = []

    for emp in employees:

        emp_id = str(emp["_id"])

        # ===== COUNT PRESENT DAYS THIS MONTH =====
        present_days = db.attendance.count_documents({
            "user_id": session["user_id"],
            "employee_id": emp_id,
            "status": "Present",
            "date": {
                "$gte": month_start,
                "$lt": month_end
            }
        })

        monthly_salary = float(emp.get("salary", 0))
        per_day_salary = monthly_salary / 30 if monthly_salary > 0 else 0

        # ===== DEDUCTION LOGIC =====
        deduction_days = max(0, 30 - present_days)
        deduction_amount = deduction_days * per_day_salary

        final_salary = max(0, monthly_salary - deduction_amount)

        # ===== CHECK SALARY STATUS =====
        salary_record = db.salary.find_one({
            "employee_id": emp_id,
            "month": current_month,
            "year": current_year
        })

        status = salary_record["status"] if salary_record else "Not Paid"

        salary_data.append({
            "employee": emp,
            "present_days": present_days,
            "deduction_days": deduction_days,
            "deduction_amount": round(deduction_amount, 2),
            "final_salary": round(final_salary, 2),
            "status": status
        })

    return render_template(
        "salary.html",
        salary_data=salary_data,
        current_month=current_month,
        current_year=current_year
    )

@app.route("/settings", methods=["GET", "POST"])
def settings():
    if "user_id" not in session:
        return redirect("/login")
    user = db.users.find_one({"_id": ObjectId(session["user_id"])})

    if request.method == "POST":

        features = {
            "orders": True if request.form.get("orders") else False,
            "products": True if request.form.get("products") else False,
            "expenses": True if request.form.get("expenses") else False,
            "employees": True if request.form.get("employees") else False,
            "attendance": True if request.form.get("attendance") else False,
            "salary": True if request.form.get("salary") else False,
        }

        db.users.update_one(
            {"_id": ObjectId(session["user_id"])},
            {"$set": {"features": features}}
        )

        flash("Settings updated successfully!", "success")
        return redirect("/settings")

    return render_template("settings.html", user=user)


if __name__ == "__main__":
    app.run(debug=True)