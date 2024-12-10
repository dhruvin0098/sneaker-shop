from flask import Flask, render_template, request, redirect, url_for, session, flash
from pymongo import MongoClient
from bson import ObjectId
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import os
from dotenv import load_dotenv
from werkzeug.utils import secure_filename


# Load environment variables
load_dotenv()

# Flask App Initialization
app = Flask(__name__)
app.secret_key = "secret_key"  # Replace with a secure key in production

# Bcrypt for Password Hashing
bcrypt = Bcrypt(app)

# Flask-Login Setup
login_manager = LoginManager(app)
login_manager.login_view = "login"

# MongoDB Connection
mongodb_username = os.getenv('MONGODB_USERNAME')
mongodb_password = os.getenv('MONGODB_PASSWORD')

mongodb_client = MongoClient(
    f"mongodb+srv://{mongodb_username}:{mongodb_password}@cluster0.9jy65.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
)
try:
    db = mongodb_client.admin
    db.command('ping')
    print("MongoDB connected successfully!")
except Exception as e:
    print(f"Error connecting to MongoDB: {e}")

# MongoDB Collections
db = mongodb_client["sneaker_shop"]
products_collection = db["sneaker_shop_P"]
inquiries_collection = db["inquiries"]
users_collection = db["users"]
cart_collection = db["cart"]
orders_collection = db["orders"]

# -----------------------------------------------
# User Management
# -----------------------------------------------
class User(UserMixin):
    def __init__(self, user_id, username, name=None, email=None, mobile=None):
        self.id = user_id
        self.username = username
        self.name = name
        self.email = email
        self.mobile = mobile


@login_manager.user_loader
def load_user(user_id):
    user = users_collection.find_one({"_id": ObjectId(user_id)})
    if user:
        return User(
            str(user["_id"]),
            user["username"],
            name=user.get("name", ""),
            email=user.get("email", ""),
            mobile=user.get("mobile", "")
        )
    return None


# -----------------------------------------------
# Admin Routes
# -----------------------------------------------

@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user = users_collection.find_one({"_id": ObjectId(current_user.id)})

    if request.method == "POST":
        # Update user details
        updated_name = request.form.get("name")
        updated_email = request.form.get("email")
        updated_mobile = request.form.get("mobile")

        users_collection.update_one(
            {"_id": ObjectId(current_user.id)},
            {"$set": {"name": updated_name, "email": updated_email, "mobile": updated_mobile}}
        )
        flash("Profile updated successfully!", "success")
        return redirect(url_for("profile"))

    return render_template("profile.html", user=user)



@app.route("/admin-login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == "admin" and password == "admin123":
            session["admin_logged_in"] = True
            return redirect(url_for("admin_dashboard"))
        else:
            return "Invalid credentials. Try again."
    return render_template("admin_login.html")


@app.route("/admin-dashboard", methods=["GET"])
def admin_dashboard():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    # Pagination logic
    page = int(request.args.get("page", 1))
    per_page = 10
    skip = (page - 1) * per_page

    # Fetch paginated data
    all_inquiries = list(inquiries_collection.find().skip(skip).limit(per_page))
    all_orders = list(orders_collection.find().skip(skip).limit(per_page))

    # Calculate statistics
    total_orders = orders_collection.count_documents({})
    total_revenue = sum(order["total_price"] for order in orders_collection.find())
    total_inquiries = inquiries_collection.count_documents({})

    return render_template(
        "admin_dashboard.html",
        inquiries=all_inquiries,
        orders=all_orders,
        total_orders=total_orders,
        total_revenue=total_revenue,
        total_inquiries=total_inquiries,
        page=page,
        per_page=per_page
    )

@app.route("/update-order/<order_id>", methods=["POST"])
def update_order(order_id):
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    new_status = request.form.get("status")
    orders_collection.update_one({"_id": ObjectId(order_id)}, {"$set": {"status": new_status}})
    return redirect(url_for("admin_dashboard"))

@app.route("/admin-logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("admin_login"))

# -----------------------------------------------
# User Authentication
# -----------------------------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = bcrypt.generate_password_hash(request.form.get("password")).decode("utf-8")
        name = request.form.get("name")
        email = request.form.get("email")
        mobile = request.form.get("mobile")

        # Insert user details into MongoDB
        users_collection.insert_one({
            "username": username,
            "password": password,
            "name": name,
            "email": email,
            "mobile": mobile
        })
        return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user = users_collection.find_one({"username": username})
        if user and bcrypt.check_password_hash(user["password"], password):
            login_user(User(str(user["_id"]), user["username"]))
            return redirect(url_for("profile"))
        return "Invalid credentials. Try again."
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

# -----------------------------------------------
# Product Management
# -----------------------------------------------
@app.route("/add-products")
def add_products():
    sample_products = [
        {
            "name": "Air Jordan 11 Retro Low 'Diffused Blue'",
            "price": 1899.99,
            "images": [
                "/static/images/snker_photo/Air Jordan 11 Retro Low 'Diffused Blue'/1AIR+JORDAN+11+RETRO+LOW.png"
            ],
            "description": "A classic Air Jordan 11 Retro Low."
        }
    ]
    products_collection.insert_many(sample_products)
    return "Products added successfully!"

@app.route("/")
def index():
    products = products_collection.find().limit(4)
    return render_template("home.html", products=products)

@app.route("/products")
def products():
    all_products = products_collection.find()
    return render_template("products.html", products=all_products)

@app.route("/product/<product_id>")
def product_details(product_id):
    product = products_collection.find_one({"_id": ObjectId(product_id)})
    return render_template("product_details.html", product=product)

# -----------------------------------------------
# Cart and Order Management
# -----------------------------------------------
@app.route("/add-to-cart/<product_id>")
@login_required
def add_to_cart(product_id):
    product = products_collection.find_one({"_id": ObjectId(product_id)})
    if product:
        cart_item = {
            "user_id": current_user.id,
            "product_id": product_id,
            "product_name": product["name"],
            "price": product["price"],
            "image_path": product["images"][0]
        }
        cart_collection.insert_one(cart_item)
        return redirect(url_for("cart"))
    return "Product not found", 404

@app.route("/cart")
@login_required
def cart():
    user_cart = list(cart_collection.find({"user_id": current_user.id}))
    total_price = sum(item['price'] for item in user_cart)
    return render_template("cart.html", cart_items=user_cart, total_price=total_price)


@app.route("/remove-from-cart/<cart_id>")
@login_required
def remove_from_cart(cart_id):
    try:
        # Check if the cart item exists
        result = cart_collection.delete_one({"_id": ObjectId(cart_id), "user_id": current_user.id})

        # If no document was deleted, show a 404 message
        if result.deleted_count == 0:
            return "Cart item not found or already removed.", 404

        return redirect(url_for("cart"))
    except Exception as e:
        print(f"Error removing item from cart: {e}")
        return "An error occurred while trying to remove the item from your cart.", 500


@app.route("/checkout", methods=["GET"])
@login_required
def checkout():
    product_id = request.args.get("product_id")  # Fetch product_id from query params
    cart_items = []
    total_price = 0

    # If a product ID is passed, fetch that product only
    if product_id:
        product = products_collection.find_one({"_id": ObjectId(product_id)})
        if product:
            cart_items = [{
                "product_name": product["name"],
                "price": product["price"],
                "image_path": product["images"][0]
            }]
            total_price = product["price"]
    else:
        # Default behavior: fetch cart items
        cart_items = list(cart_collection.find({"user_id": current_user.id}))
        total_price = sum(item["price"] for item in cart_items)

    return render_template("checkout.html", cart_items=cart_items, total_price=total_price, product_id=product_id)


@app.route("/confirm-order", methods=["POST"])
@login_required
def confirm_order():
    # Fetch user details from the form
    name = request.form.get("name")
    address = request.form.get("address")
    phone = request.form.get("phone")
    product_id = request.form.get("product_id")  # Product ID if passed

    # Initialize empty order_items list
    order_items = []
    total_price = 0

    try:
        if product_id:  # If product_id exists, handle single product checkout
            try:
                product = products_collection.find_one({"_id": ObjectId(product_id)})
                if not product:
                    flash("Product not found.", "danger")
                    return redirect(url_for("products"))

                order_items.append({
                    "product_name": product["name"],
                    "price": product["price"],
                    "image_path": product["images"][0]
                })
                total_price = product["price"]
            except Exception as e:
                print(f"Error with product_id: {e}")
                flash("Invalid product ID.", "danger")
                return redirect(url_for("products"))
        else:  # Handle cart-based checkout
            user_cart = list(cart_collection.find({"user_id": current_user.id}))
            if not user_cart:
                flash("Your cart is empty. Add items before confirming the order.", "danger")
                return redirect(url_for("cart"))

            for item in user_cart:
                order_items.append({
                    "product_name": item["product_name"],
                    "price": item["price"],
                    "image_path": item["image_path"]
                })
            total_price = sum(item["price"] for item in user_cart)
            cart_collection.delete_many({"user_id": current_user.id})  # Clear the cart after checkout

        # Prepare and insert order data
        order_data = {
            "user_id": current_user.id,
            "name": name,
            "address": address,
            "phone": phone,
            "items": order_items,
            "total_price": total_price,
            "status": "Pending"
        }
        orders_collection.insert_one(order_data)

        # Render order confirmation page
        return render_template(
            "order_confirmation.html",
            name=name,
            address=address,
            phone=phone,
            order_items=order_items,
            total_price=total_price
        )
    except Exception as e:
        print(f"Error in confirm_order: {e}")
        flash("An error occurred while confirming your order.", "danger")
        return redirect(url_for("cart"))


@app.route("/order-history")
@login_required
def order_history():
    user_orders = list(orders_collection.find({"user_id": current_user.id}))
    return render_template("order_history.html", orders=user_orders)


@app.route("/delete-order/<order_id>", methods=["POST"])
def delete_order(order_id):
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    # Delete the order from the database
    orders_collection.delete_one({"_id": ObjectId(order_id)})
    return redirect(url_for("admin_dashboard"))

# -----------------------------------------------
# Run App
# -----------------------------------------------
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
