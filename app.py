from flask import Flask, render_template, request, redirect, url_for, flash, session
from datetime import datetime
from functools import wraps
from io import BytesIO
import os
import sys
import threading
import time
import webview

from extensions import db, login_manager
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader


# =========================================================
# APPLICATION
# =========================================================

app = Flask(__name__)

# SQLite database configuration
app = Flask(__name__)

# =========================================================
# WINDOWS APP DATABASE LOCATION
# =========================================================

if getattr(sys, "frozen", False):
    # Running as a PyInstaller application
    app_folder = os.path.dirname(sys.executable)
else:
    # Running normally from Python
    app_folder = os.path.dirname(os.path.abspath(__file__))

database_path = os.path.join(
    app_folder,
    "bookshop.db"
)

# =========================================================
# DATABASE PATH
# =========================================================

if getattr(sys, "frozen", False):
    # Running as a packaged Windows application
    app_data_dir = os.path.join(
        os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
        "HORA Bookshop Management System"
    )
else:
    # Running normally from VS Code
    app_data_dir = os.path.join(
        app.root_path,
        "instance"
    )

os.makedirs(app_data_dir, exist_ok=True)

database_path = os.path.join(
    app_data_dir,
    "bookshop.db"
)

app.config["SQLALCHEMY_DATABASE_URI"] = (
    "sqlite:///" + database_path
)

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = "change-this-later"


# =========================================================
# INITIALIZE EXTENSIONS
# =========================================================

db.init_app(app)

login_manager.init_app(app)
login_manager.login_view = "login"


# =========================================================
# IMPORT DATABASE MODELS
# =========================================================

from models.user import User
from models.product import Product
from models.category import Category
from models.sale import Sale
from models.sale_item import SaleItem
from models.stock_movement import StockMovement

# =========================================================
# CREATE DATABASE TABLES
# =========================================================

with app.app_context():
    db.create_all()


# =========================================================
# FLASK LOGIN
# =========================================================

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# =========================================================
# ADMIN ACCESS DECORATOR
# =========================================================

def admin_required(f):

    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):

        if current_user.role != "admin":

            flash(
                "Administrator access required.",
                "error"
            )

            return redirect(
                url_for("dashboard")
            )

        return f(*args, **kwargs)

    return decorated_function


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    return redirect(
        url_for("login")
    )


# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        user = User.query.filter_by(
            username=username
        ).first()

        if user and check_password_hash(
            user.password,
            password
        ):

            login_user(user)

            return redirect(
                url_for("dashboard")
            )

        return "Invalid username or password"

    return render_template(
        "login.html"
    )


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/dashboard")
@login_required
def dashboard():

    # =========================
    # PRODUCT & STOCK SUMMARY
    # =========================

    total_products = Product.query.count()

    total_stock = db.session.query(
        db.func.sum(Product.quantity)
    ).scalar() or 0

    # =========================
    # LOW STOCK
    # =========================

    low_stock_products = Product.query.filter(
        Product.quantity <= Product.minimum_stock
    ).all()

    low_stock_count = len(low_stock_products)

    # =========================
    # TODAY'S SALES
    # =========================

    now = datetime.now()

    start_of_day = datetime(
        now.year,
        now.month,
        now.day
    )

    today_sales = Sale.query.filter(
        Sale.sale_date >= start_of_day
    )

    today_sales_count = today_sales.count()

    today_revenue = db.session.query(
        db.func.sum(Sale.total_amount)
    ).filter(
        Sale.sale_date >= start_of_day
    ).scalar() or 0

    # =========================
    # TODAY'S PROFIT
    # =========================

    today_profit = db.session.query(
        db.func.sum(
            (SaleItem.unit_price - Product.buying_price)
            * SaleItem.quantity
        )
    ).join(
        Product,
        SaleItem.product_id == Product.id
    ).filter(
        SaleItem.sale_id.in_(
            today_sales.with_entities(Sale.id)
        )
    ).scalar() or 0

    # =========================
    # RECENT SALES
    # =========================

    recent_sales = Sale.query.order_by(
        Sale.sale_date.desc()
    ).limit(5).all()

    # =========================
    # TOP SELLING BOOKS
    # =========================

    top_selling_books = db.session.query(
        Product.name,
        db.func.sum(
            SaleItem.quantity
        ).label("quantity_sold")
    ).join(
        SaleItem,
        SaleItem.product_id == Product.id
    ).group_by(
        Product.id,
        Product.name
    ).order_by(
        db.func.sum(
            SaleItem.quantity
        ).desc()
    ).limit(5).all()

    # =========================
    # DEBUG
    # =========================

    print("TOTAL PRODUCTS:", total_products)
    print("TOTAL STOCK:", total_stock)
    print("LOW STOCK:", low_stock_count)
    print("TODAY SALES:", today_sales_count)
    print("TODAY REVENUE:", today_revenue)
    print("TODAY PROFIT:", today_profit)

    return render_template(
        "dashboard.html",
        total_products=total_products,
        total_stock=total_stock,
        low_stock_count=low_stock_count,
        low_stock_products=low_stock_products,
        today_sales_count=today_sales_count,
        today_revenue=today_revenue,
        today_profit=today_profit,
        recent_sales=recent_sales,
        top_selling_books=top_selling_books
    )



# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
@login_required
def logout():

    logout_user()

    return redirect(
        url_for("login")
    )


# =========================================================
# PRODUCTS
# =========================================================

@app.route("/products")
@login_required
def products():

    products = Product.query.all()

    return render_template(
        "products.html",
        products=products
    )


# ---------------------------------------------------------
# ADD PRODUCT
# ---------------------------------------------------------

@app.route(
    "/products/add",
    methods=["GET", "POST"]
)
@admin_required
def add_product():

    if request.method == "POST":

        name = request.form["name"]
        category_id = request.form["category_id"]
        barcode = request.form["barcode"]
        buying_price = request.form["buying_price"]
        selling_price = request.form["selling_price"]
        quantity = request.form["quantity"]
        minimum_stock = request.form["minimum_stock"]

        product = Product(
            name=name,
            category_id=category_id,
            barcode=barcode if barcode else None,
            buying_price=buying_price,
            selling_price=selling_price,
            quantity=quantity,
            minimum_stock=minimum_stock
        )

        db.session.add(product)
        db.session.commit()

        flash(
            "Product added successfully.",
            "success"
        )

        return redirect(
            url_for("products")
        )

    categories = Category.query.all()

    return render_template(
        "add_product.html",
        categories=categories
    )


# ---------------------------------------------------------
# EDIT PRODUCT
# ---------------------------------------------------------

@app.route(
    "/products/edit/<int:product_id>",
    methods=["GET", "POST"]
)
@admin_required
def edit_product(product_id):

    product = Product.query.get_or_404(
        product_id
    )

    if request.method == "POST":

        product.name = request.form["name"]

        product.category_id = request.form[
            "category_id"
        ]

        product.barcode = (
            request.form["barcode"]
            or None
        )

        product.buying_price = request.form[
            "buying_price"
        ]

        product.selling_price = request.form[
            "selling_price"
        ]

        product.quantity = request.form[
            "quantity"
        ]

        product.minimum_stock = request.form[
            "minimum_stock"
        ]

        db.session.commit()

        flash(
            "Product updated successfully.",
            "success"
        )

        return redirect(
            url_for("products")
        )

    return render_template(
        "edit_product.html",
        product=product,
        categories=Category.query.all()
    )



# ---------------------------------------------------------
# DELETE PRODUCT
# ---------------------------------------------------------

@app.route(
    "/products/delete/<int:product_id>",
    methods=["POST"]
)
@admin_required
def delete_product(product_id):

    product = Product.query.get_or_404(
        product_id
    )

    # -----------------------------------------------------
    # CHECK FOR SALES HISTORY
    # -----------------------------------------------------

    sales_count = SaleItem.query.filter_by(
        product_id=product.id
    ).count()

    if sales_count > 0:

        flash(
            f"Cannot delete '{product.name}' because "
            f"it has existing sales records. "
            f"Deleting it would affect your sales history.",
            "error"
        )

        return redirect(
            url_for("products")
        )

    # -----------------------------------------------------
    # CHECK FOR STOCK MOVEMENT HISTORY
    # -----------------------------------------------------

    stock_movement_count = StockMovement.query.filter_by(
        product_id=product.id
    ).count()

    if stock_movement_count > 0:

        flash(
            f"Cannot delete '{product.name}' because "
            f"it has existing stock movement records.",
            "error"
        )

        return redirect(
            url_for("products")
        )

    # -----------------------------------------------------
    # SAFE TO DELETE
    # -----------------------------------------------------

    try:

        product_name = product.name

        db.session.delete(product)

        db.session.commit()

        flash(
            f"Product '{product_name}' deleted successfully.",
            "success"
        )

    except Exception as e:

        db.session.rollback()

        flash(
            f"Could not delete product: {str(e)}",
            "error"
        )

    return redirect(
        url_for("products")
    )



# =========================================================
# STOCK
# =========================================================

@app.route("/stock")
@login_required
def stock():

    products = Product.query.all()

    low_stock_products = [
        product
        for product in products
        if product.quantity <= product.minimum_stock
    ]

    low_stock_count = len(low_stock_products)

    total_stock = sum(
        product.quantity for product in products
    )

    return render_template(
        "stock.html",
        products=products,
        low_stock_products=low_stock_products,
        low_stock_count=low_stock_count,
        total_stock=total_stock
    )

# ---------------------------------------------------------
# STOCK MOVEMENT
# ---------------------------------------------------------

@app.route(
    "/stock/movement/<int:product_id>",
    methods=["GET", "POST"]
)
@admin_required
def stock_movement(product_id):

    product = Product.query.get_or_404(
        product_id
    )

    if request.method == "POST":

        movement_type = request.form[
            "movement_type"
        ]

        quantity = int(
            request.form["quantity"]
        )

        reference = request.form[
            "reference"
        ]

        if quantity <= 0:

            flash(
                "Quantity must be greater than zero.",
                "error"
            )

            return redirect(
                url_for(
                    "stock_movement",
                    product_id=product.id
                )
            )

        if movement_type == "IN":

            product.quantity += quantity

        elif movement_type == "OUT":

            if quantity > product.quantity:

                flash(
                    "Not enough stock available.",
                    "error"
                )

                return redirect(
                    url_for(
                        "stock_movement",
                        product_id=product.id
                    )
                )

            product.quantity -= quantity

        else:

            flash(
                "Invalid stock movement type.",
                "error"
            )

            return redirect(
                url_for(
                    "stock_movement",
                    product_id=product.id
                )
            )

        movement = StockMovement(
            product_id=product.id,
            quantity=quantity,
            movement_type=movement_type,
            reference=reference,
            user_id=current_user.id
        )

        db.session.add(movement)
        db.session.commit()

        flash(
            "Stock movement recorded successfully.",
            "success"
        )

        return redirect(
            url_for("stock")
        )

    return render_template(
        "stock_movement.html",
        product=product
    )


# ---------------------------------------------------------
# STOCK HISTORY
# ---------------------------------------------------------

@app.route("/stock/history")
@admin_required
def stock_history():

    movements = StockMovement.query.order_by(
        StockMovement.movement_date.desc()
    ).all()

    return render_template(
        "stock_history.html",
        movements=movements
    )


# =========================================================
# SALES
# =========================================================

@app.route("/sales")
@login_required
def sales():

    sales = Sale.query.order_by(
        Sale.sale_date.desc()
    ).all()

    return render_template(
        "sales.html",
        sales=sales
    )


# ---------------------------------------------------------
# NEW SALE
# ---------------------------------------------------------

@app.route("/sales/new")
@login_required
def new_sale():

    products = Product.query.all()

    cart = session.get(
        "cart",
        []
    )

    total = sum(
        float(item["subtotal"])
        for item in cart
    )

    return render_template(
        "new_sale.html",
        products=products,
        cart=cart,
        total=total
    )


# ---------------------------------------------------------
# ADD PRODUCT TO CART
# ---------------------------------------------------------

@app.route(
    "/sales/add-to-cart",
    methods=["POST"]
)
@login_required
def add_to_cart():

    product_id = int(
        request.form["product_id"]
    )

    quantity = int(
        request.form["quantity"]
    )

    product = Product.query.get_or_404(
        product_id
    )

    if quantity <= 0:

        flash(
            "Quantity must be greater than zero.",
            "error"
        )

        return redirect(
            url_for("new_sale")
        )

    if quantity > product.quantity:

        flash(
            "Not enough stock available.",
            "error"
        )

        return redirect(
            url_for("new_sale")
        )

    cart = session.get(
        "cart",
        []
    )

    # Check if product already exists in cart
    for item in cart:

        if item["product_id"] == product.id:

            new_quantity = (
                item["quantity"] + quantity
            )

            if new_quantity > product.quantity:

                flash(
                    "Not enough stock available.",
                    "error"
                )

                return redirect(
                    url_for("new_sale")
                )

            item["quantity"] = new_quantity

            item["subtotal"] = (
                new_quantity *
                item["unit_price"]
            )

            session["cart"] = cart
            session.modified = True

            return redirect(
                url_for("new_sale")
            )

    # Add new product
    cart.append({

        "product_id": product.id,

        "name": product.name,

        "quantity": quantity,

        "unit_price": float(
            product.selling_price
        ),

        "subtotal": (
            float(product.selling_price)
            * quantity
        )

    })

    session["cart"] = cart
    session.modified = True

    return redirect(
        url_for("new_sale")
    )


# ---------------------------------------------------------
# REMOVE PRODUCT FROM CART
# ---------------------------------------------------------

@app.route(
    "/sales/remove-from-cart/<int:product_id>",
    methods=["POST"]
)
@login_required
def remove_from_cart(product_id):

    cart = session.get(
        "cart",
        []
    )

    cart = [
        item
        for item in cart
        if item["product_id"] != product_id
    ]

    session["cart"] = cart
    session.modified = True

    return redirect(
        url_for("new_sale")
    )


# ---------------------------------------------------------
# COMPLETE SALE
# ---------------------------------------------------------

@app.route(
    "/sales/complete",
    methods=["POST"]
)
@login_required
def complete_sale():

    cart = session.get(
        "cart",
        []
    )

    if not cart:

        flash(
            "Cannot complete an empty sale.",
            "error"
        )

        return redirect(
            url_for("new_sale")
        )

    # Customer/reference
    customer_reference = request.form.get(
        "customer_reference",
        ""
    ).strip()

    if not customer_reference:

        flash(
            "Customer / Reference is required before completing the sale.",
            "error"
        )

        return redirect(
            url_for("new_sale")
        )

    try:

        # -------------------------------------------------
        # CHECK STOCK
        # -------------------------------------------------

        for item in cart:

            product = Product.query.get(
                item["product_id"]
            )

            if not product:

                raise Exception(
                    "A product in the cart no longer exists."
                )

            if item["quantity"] > product.quantity:

                flash(
                    f"Not enough stock available for {product.name}.",
                    "error"
                )

                return redirect(
                    url_for("new_sale")
                )

        # -------------------------------------------------
        # CALCULATE TOTAL
        # -------------------------------------------------

        total = sum(
            float(item["subtotal"])
            for item in cart
        )

        # -------------------------------------------------
        # RECEIPT NUMBER
        # -------------------------------------------------

        last_sale = Sale.query.order_by(
            Sale.id.desc()
        ).first()

        if last_sale:
            last_number = last_sale.id
        else:
            last_number = 0

        receipt_number = f"REC-{last_number + 1:010d}"  

        # -------------------------------------------------
        # CREATE SALE
        # -------------------------------------------------

        sale = Sale(

            receipt_number=receipt_number,

            user_id=current_user.id,

            customer_reference=customer_reference,

            total_amount=total

        )

        db.session.add(sale)

        # Generate sale ID
        db.session.flush()

        # -------------------------------------------------
        # CREATE SALE ITEMS
        # -------------------------------------------------

        for item in cart:

            product = Product.query.get(
                item["product_id"]
            )

            sale_item = SaleItem(

                sale_id=sale.id,

                product_id=product.id,

                quantity=item["quantity"],

                unit_price=item["unit_price"],

                subtotal=item["subtotal"]

            )

            # Reduce stock
            product.quantity -= item["quantity"]

            # -------------------------------------------------
            # STOCK MOVEMENT
            # -------------------------------------------------

            stock_movement = StockMovement(

                product_id=product.id,

                quantity=item["quantity"],

                movement_type="OUT",

                reference=f"Sale {receipt_number}",

                user_id=current_user.id

            )

            db.session.add(
                sale_item
            )

            db.session.add(
                stock_movement
            )

        # -------------------------------------------------
        # SAVE
        # -------------------------------------------------

        db.session.commit()

        # Clear cart
        session.pop(
            "cart",
            None
        )

        flash(
            f"Sale completed successfully. Receipt: {receipt_number}",
            "success"
        )

        return redirect(
            url_for(
                "sale_details",
                sale_id=sale.id
            )
        )

    except Exception as e:

        db.session.rollback()

        flash(
            f"Sale could not be completed: {str(e)}",
            "error"
        )

        return redirect(
            url_for("new_sale")
        )


# ---------------------------------------------------------
# SALE DETAILS
# ---------------------------------------------------------

@app.route(
    "/sales/<int:sale_id>/details"
)
@login_required
def sale_details(sale_id):

    sale = Sale.query.get_or_404(
        sale_id
    )

    items = SaleItem.query.filter_by(
        sale_id=sale.id
    ).all()

    return render_template(
        "sale_details.html",
        sale=sale,
        items=items
    )


# ---------------------------------------------------------
# SALE RECEIPT PDF
# ---------------------------------------------------------


@app.route(
    "/sales/<int:sale_id>/receipt"
)
@login_required
def sale_receipt(sale_id):

    sale = Sale.query.get_or_404(
        sale_id
    )

    items = SaleItem.query.filter_by(
        sale_id=sale.id
    ).all()


    # =====================================================
    # CREATE PDF BUFFER
    # =====================================================

    pdf_buffer = BytesIO()

    pdf = canvas.Canvas(
        pdf_buffer,
        pagesize=A4
    )

    width, height = A4


    # =====================================================
    # SCHOOL LOGO
    # =====================================================

    logo_path = os.path.join(
        app.root_path,
        "static",
        "images",
        "school_logo.png"
    )

    if os.path.exists(logo_path):

        logo = ImageReader(
            logo_path
        )

        pdf.drawImage(
            logo,
            55,
            height - 125,
            width=85,
            height=85,
            preserveAspectRatio=True,
            mask="auto"
        )


    # =====================================================
    # SCHOOL HEADER
    # =====================================================

    pdf.setFont(
        "Helvetica-Bold",
        16
    )

    pdf.drawCentredString(
        width / 2 + 25,
        height - 55,
        "HOPE OF RESTORATION ACADEMY"
    )


    pdf.setFont(
        "Helvetica-Bold",
        10
    )

    pdf.drawCentredString(
        width / 2 + 25,
        height - 72,
        "(REG NO. GSMAR/PJS270)"
    )


    pdf.setFont(
        "Helvetica",
        9
    )

    pdf.drawCentredString(
        width / 2 + 25,
        height - 88,
        "C/O P.O.BOX OH 385, AKWELEY"
    )

    pdf.drawCentredString(
        width / 2 + 25,
        height - 102,
        "Tel: 0249704472 / 0549813896"
    )

    pdf.drawCentredString(
        width / 2 + 25,
        height - 116,
        "Email: horarestoration@yahoo.com"
    )

    pdf.drawCentredString(
        width / 2 + 25,
        height - 130,
        "www.hopeofrestorationacademy.com"
    )


    # =====================================================
    # HEADER LINE
    # =====================================================

    pdf.setStrokeColor(
        colors.HexColor("#1f2937")
    )

    pdf.line(
        45,
        height - 145,
        width - 45,
        height - 145
    )


    # =====================================================
    # RECEIPT TITLE
    # =====================================================

    pdf.setFont(
        "Helvetica-Bold",
        16
    )

    pdf.drawCentredString(
        width / 2,
        height - 175,
        "SALES RECEIPT"
    )


    # =====================================================
    # RECEIPT INFORMATION
    # =====================================================

    y = height - 210


    # Receipt number

    pdf.setFont(
        "Helvetica-Bold",
        10
    )

    pdf.drawString(
        50,
        y,
        "Receipt No:"
    )

    pdf.setFont(
        "Helvetica",
        10
    )

    pdf.drawString(
        125,
        y,
        sale.receipt_number
    )


    # Date

    pdf.setFont(
        "Helvetica-Bold",
        10
    )

    pdf.drawString(
        350,
        y,
        "Date:"
    )

    pdf.setFont(
        "Helvetica",
        10
    )

    pdf.drawString(
        385,
        y,
        sale.sale_date.strftime(
            "%d-%m-%Y"
        )
    )


    # =====================================================
    # TIME & SOLD BY
    # =====================================================

    y -= 20


    pdf.setFont(
        "Helvetica-Bold",
        10
    )

    pdf.drawString(
        50,
        y,
        "Time:"
    )

    pdf.setFont(
        "Helvetica",
        10
    )

    pdf.drawString(
        125,
        y,
        sale.sale_date.strftime(
            "%H:%M:%S"
        )
    )


    pdf.setFont(
        "Helvetica-Bold",
        10
    )

    pdf.drawString(
        350,
        y,
        "Sold By:"
    )

    pdf.setFont(
        "Helvetica",
        10
    )

    pdf.drawString(
        405,
        y,
        sale.user.username
    )


    # =====================================================
    # CUSTOMER / REFERENCE
    # =====================================================

    y -= 20


    pdf.setFont(
        "Helvetica-Bold",
        10
    )

    pdf.drawString(
        50,
        y,
        "Customer / Reference:"
    )


    pdf.setFont(
        "Helvetica",
        10
    )

    customer_reference = (
        sale.customer_reference
        or "Walk-in Customer"
    )


    if len(customer_reference) > 55:

        customer_reference = (
            customer_reference[:52]
            + "..."
        )


    pdf.drawString(
        165,
        y,
        customer_reference
    )


    # =====================================================
    # PRODUCTS TABLE HEADER
    # =====================================================

    y -= 35


    pdf.setFillColor(
        colors.HexColor("#1f2937")
    )

    pdf.rect(
        45,
        y - 5,
        width - 90,
        25,
        fill=1,
        stroke=0
    )


    pdf.setFillColor(
        colors.white
    )

    pdf.setFont(
        "Helvetica-Bold",
        9
    )


    pdf.drawString(
        55,
        y + 3,
        "PRODUCT"
    )

    pdf.drawString(
        300,
        y + 3,
        "QTY"
    )

    pdf.drawString(
        350,
        y + 3,
        "UNIT PRICE"
    )

    pdf.drawString(
        455,
        y + 3,
        "SUBTOTAL"
    )


    # =====================================================
    # PRODUCTS
    # =====================================================

    y -= 30


    pdf.setFillColor(
        colors.black
    )

    pdf.setFont(
        "Helvetica",
        9
    )


    for item in items:

        product_name = item.product.name


        if len(product_name) > 38:

            product_name = (
                product_name[:35]
                + "..."
            )


        pdf.drawString(
            55,
            y,
            product_name
        )


        pdf.drawString(
            300,
            y,
            str(item.quantity)
        )


        pdf.drawString(
            350,
            y,
            f"GH₵ {item.unit_price:.2f}"
        )


        pdf.drawString(
            455,
            y,
            f"GH₵ {item.subtotal:.2f}"
        )


        y -= 22


        pdf.setStrokeColor(
            colors.HexColor("#dddddd")
        )

        pdf.line(
            45,
            y + 8,
            width - 45,
            y + 8
        )


        # Prevent content from running off the page

        if y < 100:

            pdf.showPage()

            y = height - 50


    # =====================================================
    # TOTAL
    # =====================================================

    y -= 15


    pdf.setFont(
        "Helvetica-Bold",
        13
    )


    pdf.drawString(
        350,
        y,
        "TOTAL:"
    )


    pdf.drawString(
        445,
        y,
        f"GH₵ {sale.total_amount:.2f}"
    )


    # =====================================================
    # FOOTER
    # =====================================================

    y -= 50


    pdf.setStrokeColor(
        colors.HexColor("#1f2937")
    )

    pdf.line(
        45,
        y + 20,
        width - 45,
        y + 20
    )


    pdf.setFont(
        "Helvetica-Bold",
        10
    )

    pdf.drawCentredString(
        width / 2,
        y,
        "Thank you for shopping with us!"
    )


    pdf.setFont(
        "Helvetica",
        8
    )

    pdf.drawCentredString(
        width / 2,
        y - 15,
        "Please keep this receipt for your records."
    )


    pdf.drawCentredString(
        width / 2,
        y - 30,
        "HOPE OF RESTORATION ACADEMY"
    )


    # =====================================================
    # FINISH PDF
    # =====================================================

    pdf.save()

    pdf_buffer.seek(0)


    return pdf_buffer.getvalue(), 200, {
        "Content-Type": "application/pdf",

        "Content-Disposition":
            f"inline; filename={sale.receipt_number}.pdf"
    }


# =========================================================
# USERS
# =========================================================

@app.route("/users")
@admin_required
def users():

    users = User.query.order_by(
        User.id.asc()
    ).all()

    return render_template(
        "users.html",
        users=users
    )


# ---------------------------------------------------------
# ADD USER
# ---------------------------------------------------------

@app.route(
    "/users/add",
    methods=["GET", "POST"]
)
@admin_required
def add_user():

    if request.method == "POST":

        username = request.form[
            "username"
        ].strip()

        password = request.form[
            "password"
        ]

        role = request.form[
            "role"
        ]

        if not username or not password:

            flash(
                "Username and password are required.",
                "error"
            )

            return redirect(
                url_for("add_user")
            )

        if role not in [
            "admin",
            "sales"
        ]:

            flash(
                "Invalid user role.",
                "error"
            )

            return redirect(
                url_for("add_user")
            )

        existing_user = User.query.filter_by(
            username=username
        ).first()

        if existing_user:

            flash(
                "Username already exists.",
                "error"
            )

            return redirect(
                url_for("add_user")
            )

        user = User(
            username=username,
            password=generate_password_hash(
                password
            ),
            role=role
        )

        db.session.add(user)
        db.session.commit()

        flash(
            "User created successfully.",
            "success"
        )

        return redirect(
            url_for("users")
        )

    return render_template(
        "add_user.html"
    )


# ---------------------------------------------------------
# DELETE USER
# ---------------------------------------------------------

@app.route(
    "/users/delete/<int:user_id>",
    methods=["POST"]
)
@admin_required
def delete_user(user_id):

    user = User.query.get_or_404(user_id)

    # Prevent the currently logged-in administrator
    # from deleting their own account
    if user.id == current_user.id:

        flash(
            "You cannot delete your own account.",
            "error"
        )

        return redirect(
            url_for("users")
        )

    # Check whether this user has made any sales
    sales_count = Sale.query.filter_by(
        user_id=user.id
    ).count()

    # Check whether this user has recorded
    # any stock movements
    stock_movement_count = StockMovement.query.filter_by(
        user_id=user.id
    ).count()

    # Do not delete users who have transaction history
    if sales_count > 0 or stock_movement_count > 0:

        flash(
            f"Cannot delete '{user.username}' because "
            f"the user has existing transaction records. "
            f"Deleting the account would affect your records.",
            "error"
        )

        return redirect(
            url_for("users")
        )

    # Safe to delete users with no transaction history
    db.session.delete(user)

    db.session.commit()

    flash(
        f"User '{user.username}' deleted successfully.",
        "success"
    )

    return redirect(
        url_for("users")
    )


# =========================================================
# REPORTS
# =========================================================

@app.route("/reports")
@admin_required
def reports():

    period = request.args.get("period", "all")
    selected_date = request.args.get("date", "")

    now = datetime.now()

    # =====================================================
    # DATE FILTER
    # =====================================================

    if period == "today":

        start_date = datetime(
            now.year,
            now.month,
            now.day
        )

        end_date = datetime(
            now.year,
            now.month,
            now.day,
            23,
            59,
            59
        )

        filtered_sales = Sale.query.filter(
            Sale.sale_date >= start_date,
            Sale.sale_date <= end_date
        )

    elif period == "month":

        start_date = datetime(
            now.year,
            now.month,
            1
        )

        filtered_sales = Sale.query.filter(
            Sale.sale_date >= start_date
        )

    elif selected_date:

        try:

            report_date = datetime.strptime(
                selected_date,
                "%Y-%m-%d"
            )

            next_day = datetime(
                report_date.year,
                report_date.month,
                report_date.day
            )

            from datetime import timedelta

            end_date = next_day + timedelta(days=1)

            filtered_sales = Sale.query.filter(
                Sale.sale_date >= next_day,
                Sale.sale_date < end_date
            )

        except ValueError:

            flash(
                "Invalid date selected.",
                "error"
            )

            filtered_sales = Sale.query

    else:

        filtered_sales = Sale.query


    # =====================================================
    # SALES SUMMARY
    # =====================================================

    sales_subquery = filtered_sales.with_entities(
        Sale.id
    ).subquery()

    total_sales = db.session.query(
        db.func.sum(Sale.total_amount)
    ).filter(
        Sale.id.in_(
            db.select(sales_subquery.c.id)
        )
    ).scalar() or 0


    sales_count = filtered_sales.count()


    # =====================================================
    # PROFIT
    # =====================================================

    total_profit = db.session.query(
        db.func.sum(
            (
                SaleItem.unit_price
                - Product.buying_price
            ) * SaleItem.quantity
        )
    ).join(
        Product,
        SaleItem.product_id == Product.id
    ).filter(
        SaleItem.sale_id.in_(
            db.select(sales_subquery.c.id)
        )
    ).scalar() or 0


    # =====================================================
    # PRODUCTS & STOCK
    # =====================================================

    product_count = Product.query.count()

    total_stock = db.session.query(
        db.func.sum(Product.quantity)
    ).scalar() or 0


    # =====================================================
    # INVENTORY VALUE
    # =====================================================

    inventory_cost_value = db.session.query(
        db.func.sum(
            Product.quantity *
            Product.buying_price
        )
    ).scalar() or 0


    potential_sales_value = db.session.query(
        db.func.sum(
            Product.quantity *
            Product.selling_price
        )
    ).scalar() or 0


    potential_profit = (
        potential_sales_value
        - inventory_cost_value
    )


    # =====================================================
    # LOW STOCK
    # =====================================================

    low_stock_products = Product.query.filter(
        Product.quantity <= Product.minimum_stock
    ).all()

    low_stock_count = len(
        low_stock_products
    )


    # =====================================================
    # TOP-SELLING BOOKS
    # =====================================================

    top_selling_books = db.session.query(
        Product.name,
        db.func.sum(
            SaleItem.quantity
        ).label("quantity_sold")
    ).join(
        SaleItem,
        SaleItem.product_id == Product.id
    ).filter(
        SaleItem.sale_id.in_(
            db.select(sales_subquery.c.id)
        )
    ).group_by(
        Product.id,
        Product.name
    ).order_by(
        db.func.sum(
            SaleItem.quantity
        ).desc()
    ).limit(10).all()


    # =====================================================
    # RECENT / FILTERED SALES
    # =====================================================

    recent_sales = filtered_sales.order_by(
        Sale.sale_date.desc()
    ).limit(50).all()


    # =====================================================
    # DISPLAY REPORT
    # =====================================================

    return render_template(

        "reports.html",

        total_sales=total_sales,

        total_profit=total_profit,

        inventory_cost_value=inventory_cost_value,

        potential_sales_value=potential_sales_value,

        potential_profit=potential_profit,

        sales_count=sales_count,

        product_count=product_count,

        total_stock=total_stock,

        low_stock_count=low_stock_count,

        low_stock_products=low_stock_products,

        top_selling_books=top_selling_books,

        recent_sales=recent_sales,

        period=period,

        selected_date=selected_date

    )

# =========================================================
# CATEGORIES
# =========================================================

@app.route("/categories")
@admin_required
def categories():

    categories = Category.query.all()

    return render_template(
        "categories.html",
        categories=categories
    )


# ---------------------------------------------------------
# ADD CATEGORY
# ---------------------------------------------------------

@app.route(
    "/categories/add",
    methods=["GET", "POST"]
)
@admin_required
def add_category():

    if request.method == "POST":

        name = request.form[
            "name"
        ]

        category = Category(
            name=name
        )

        db.session.add(category)
        db.session.commit()

        flash(
            "Category added successfully.",
            "success"
        )

        return redirect(
            url_for("categories")
        )

    return render_template(
        "add_category.html"
    )



@app.route(
    "/categories/edit/<int:category_id>",
    methods=["GET", "POST"]
)
@admin_required
def edit_category(category_id):

    category = Category.query.get_or_404(category_id)

    if request.method == "POST":

        name = request.form["name"].strip()

        if not name:

            flash(
                "Category name is required.",
                "error"
            )

            return redirect(
                url_for(
                    "edit_category",
                    category_id=category.id
                )
            )

        # Check whether another category already has this name
        existing_category = Category.query.filter(
            Category.name == name,
            Category.id != category.id
        ).first()

        if existing_category:

            flash(
                "A category with this name already exists.",
                "error"
            )

            return redirect(
                url_for(
                    "edit_category",
                    category_id=category.id
                )
            )

        category.name = name

        db.session.commit()

        flash(
            f"Category '{category.name}' updated successfully.",
            "success"
        )

        return redirect(
            url_for("categories")
        )

    return render_template(
        "edit_category.html",
        category=category
    )




@app.route(
    "/categories/delete/<int:category_id>",
    methods=["POST"]
)
@admin_required
def delete_category(category_id):

    category = Category.query.get_or_404(category_id)

    # Check whether any products are using this category
    product_count = Product.query.filter_by(
        category_id=category.id
    ).count()

    if product_count > 0:

        flash(
            f"Cannot delete '{category.name}'. "
            f"{product_count} product(s) are assigned to this category.",
            "error"
        )

        return redirect(
            url_for("categories")
        )

    # Safe to delete because no products use this category
    db.session.delete(category)

    db.session.commit()

    flash(
        f"Category '{category.name}' deleted successfully.",
        "success"
    )

    return redirect(
        url_for("categories")
    )







# =========================================================
# RUN APPLICATION
# =========================================================

@app.route("/reports/daily/pdf")
@admin_required
def daily_report_pdf():

    selected_date = request.args.get("date")

    if not selected_date:
        flash("Please select a date first.", "error")
        return redirect(url_for("reports"))

    try:
        report_date = datetime.strptime(
            selected_date,
            "%Y-%m-%d"
        )

    except ValueError:
        flash("Invalid date.", "error")
        return redirect(url_for("reports"))

    from datetime import timedelta

    # ==========================================
    # DATE RANGE
    # ==========================================

    start_date = datetime(
        report_date.year,
        report_date.month,
        report_date.day
    )

    end_date = start_date + timedelta(days=1)

    # ==========================================
    # GET SALES FOR SELECTED DAY
    # ==========================================

    sales = Sale.query.filter(
        Sale.sale_date >= start_date,
        Sale.sale_date < end_date
    ).order_by(
        Sale.sale_date.asc()
    ).all()

    # ==========================================
    # GET SALE ITEMS
    # ==========================================

    sale_ids = [sale.id for sale in sales]

    if sale_ids:

        sale_items = SaleItem.query.filter(
            SaleItem.sale_id.in_(sale_ids)
        ).all()

    else:

        sale_items = []

    # ==========================================
    # CALCULATE TOTALS
    # ==========================================

    total_sales = sum(
        float(sale.total_amount)
        for sale in sales
    )

    total_items = sum(
        item.quantity
        for item in sale_items
    )

    sales_count = len(sales)

    # ==========================================
    # CREATE PDF
    # ==========================================

    pdf_buffer = BytesIO()

    pdf = canvas.Canvas(
        pdf_buffer,
        pagesize=A4
    )

    width, height = A4

    # ==========================================
    # HEADER
    # ==========================================

    pdf.setFont(
        "Helvetica-Bold",
        18
    )

    pdf.drawCentredString(
        width / 2,
        height - 55,
        "HOPE OF RESTORATION ACADEMY"
    )

    pdf.setFont(
        "Helvetica-Bold",
        14
    )

    pdf.drawCentredString(
        width / 2,
        height - 80,
        "BOOKSHOP DAILY SALES REPORT"
    )

    pdf.setFont(
        "Helvetica",
        10
    )

    pdf.drawCentredString(
        width / 2,
        height - 100,
        f"Date: {report_date.strftime('%d-%m-%Y')}"
    )

    pdf.line(
        45,
        height - 115,
        width - 45,
        height - 115
    )

    # ==========================================
    # SUMMARY
    # ==========================================

    y = height - 145

    pdf.setFont(
        "Helvetica-Bold",
        10
    )

    pdf.drawString(
        50,
        y,
        f"Number of Sales: {sales_count}"
    )

    pdf.drawString(
        220,
        y,
        f"Items Sold: {total_items}"
    )

    pdf.drawString(
        380,
        y,
        f"Revenue: GH₵ {total_sales:.2f}"
    )

    y -= 30

    # ==========================================
    # COLUMN POSITIONS
    # ==========================================

    receipt_x = 48
    product_x = 145
    qty_x = 285
    unit_price_x = 335
    subtotal_x = 420
    sold_by_x = 505

    # ==========================================
    # FUNCTION TO DRAW TABLE HEADER
    # ==========================================

    def draw_table_header():

        nonlocal y

        pdf.setFillColor(
            colors.HexColor("#1f2937")
        )

        pdf.rect(
            40,
            y - 5,
            width - 80,
            25,
            fill=1,
            stroke=0
        )

        pdf.setFillColor(
            colors.white
        )

        pdf.setFont(
            "Helvetica-Bold",
            7.5
        )

        pdf.drawString(
            receipt_x,
            y + 3,
            "RECEIPT"
        )

        pdf.drawString(
            product_x,
            y + 3,
            "PRODUCT"
        )

        pdf.drawString(
            qty_x,
            y + 3,
            "QTY"
        )

        pdf.drawString(
            unit_price_x,
            y + 3,
            "UNIT PRICE"
        )

        pdf.drawString(
            subtotal_x,
            y + 3,
            "SUBTOTAL"
        )

        pdf.drawString(
            sold_by_x,
            y + 3,
            "SOLD BY"
        )

        y -= 25

        pdf.setFillColor(
            colors.black
        )

        pdf.setFont(
            "Helvetica",
            7.5
        )

    # ==========================================
    # TABLE HEADER
    # ==========================================

    draw_table_header()

    # ==========================================
    # PRODUCTS SOLD
    # ==========================================

    for item in sale_items:

        # ------------------------------------------
        # GET RELATED SALE
        # ------------------------------------------

        sale = Sale.query.get(item.sale_id)

        if not sale:
            continue

        # ------------------------------------------
        # RECEIPT NUMBER
        # ------------------------------------------

        receipt_number = sale.receipt_number

        # ------------------------------------------
        # PRODUCT NAME
        # ------------------------------------------

        if item.product:

            product_name = item.product.name

        else:

            product_name = "Unknown Product"

        if len(product_name) > 20:

            product_name = (
                product_name[:17]
                + "..."
            )

        # ------------------------------------------
        # SOLD BY
        # ------------------------------------------

        if sale.user:

            username = sale.user.username

        else:

            username = "Unknown"

        if len(username) > 10:

            username = (
                username[:7]
                + "..."
            )

        # ------------------------------------------
        # DRAW RECEIPT
        # ------------------------------------------

        pdf.drawString(
            receipt_x,
            y,
            receipt_number
        )

        # ------------------------------------------
        # DRAW PRODUCT
        # ------------------------------------------

        pdf.drawString(
            product_x,
            y,
            product_name
        )

        # ------------------------------------------
        # DRAW QUANTITY
        # ------------------------------------------

        pdf.drawRightString(
            qty_x + 15,
            y,
            str(item.quantity)
        )

        # ------------------------------------------
        # DRAW UNIT PRICE
        # ------------------------------------------

        pdf.drawRightString(
            unit_price_x + 65,
            y,
            f"GH₵ {float(item.unit_price):.2f}"
        )

        # ------------------------------------------
        # DRAW SUBTOTAL
        # ------------------------------------------

        pdf.drawRightString(
            subtotal_x + 65,
            y,
            f"GH₵ {float(item.subtotal):.2f}"
        )

        # ------------------------------------------
        # DRAW SOLD BY
        # ------------------------------------------

        pdf.drawString(
            sold_by_x,
            y,
            username
        )

        # ------------------------------------------
        # ROW LINE
        # ------------------------------------------

        pdf.setStrokeColor(
            colors.HexColor("#dddddd")
        )

        pdf.line(
            40,
            y - 5,
            width - 40,
            y - 5
        )

        # Move to next row
        y -= 18

        # ==========================================
        # NEW PAGE
        # ==========================================

        if y < 60:

            pdf.showPage()

            y = height - 50

            draw_table_header()

    # ==========================================
    # NO SALES
    # ==========================================

    if not sale_items:

        pdf.setFont(
            "Helvetica",
            10
        )

        pdf.drawString(
            50,
            y,
            "No sales were recorded on this date."
        )

        y -= 25

    # ==========================================
    # GRAND TOTAL
    # ==========================================

    y -= 15

    pdf.setStrokeColor(
        colors.black
    )

    pdf.line(
        40,
        y + 15,
        width - 40,
        y + 15
    )

    pdf.setFont(
        "Helvetica-Bold",
        13
    )

    pdf.drawString(
        330,
        y - 5,
        "TOTAL SALES:"
    )

    pdf.drawRightString(
        width - 45,
        y - 5,
        f"GH₵ {total_sales:.2f}"
    )

    # ==========================================
    # FOOTER
    # ==========================================

    pdf.setFont(
        "Helvetica",
        8
    )

    pdf.drawCentredString(
        width / 2,
        30,
        "HOPE OF RESTORATION ACADEMY - BOOKSHOP"
    )

    # ==========================================
    # SAVE PDF
    # ==========================================

    pdf.save()

    pdf_buffer.seek(0)

    return pdf_buffer.getvalue(), 200, {
        "Content-Type": "application/pdf",
        "Content-Disposition": (
            f"inline; filename=daily_report_{selected_date}.pdf"
        )
    }





# =========================================================
# CLEAR TEST DATA
# =========================================================

@app.route(
    "/admin/clear-test-data",
    methods=["GET", "POST"]
)
@admin_required
def clear_test_data():

    # -----------------------------------------------------
    # SHOW CONFIRMATION PAGE
    # -----------------------------------------------------

    if request.method == "GET":

        return render_template(
            "clear_test_data.html"
        )

    # -----------------------------------------------------
    # CONFIRMATION
    # -----------------------------------------------------

    confirmation = request.form.get(
        "confirmation",
        ""
    ).strip()

    if confirmation != "CLEAR DATA":

        flash(
            "Incorrect confirmation. No data was deleted.",
            "error"
        )

        return redirect(
            url_for("clear_test_data")
        )

    try:

        # -------------------------------------------------
        # DELETE SALE ITEMS
        # -------------------------------------------------

        SaleItem.query.delete(
            synchronize_session=False
        )

        # -------------------------------------------------
        # DELETE SALES
        # -------------------------------------------------

        Sale.query.delete(
            synchronize_session=False
        )

        # -------------------------------------------------
        # DELETE STOCK MOVEMENT HISTORY
        # -------------------------------------------------

        StockMovement.query.delete(
            synchronize_session=False
        )

        # -------------------------------------------------
        # RESET PRODUCT STOCK
        # -------------------------------------------------

        products = Product.query.all()

        for product in products:

            product.quantity = 0

        # -------------------------------------------------
        # SAVE CHANGES
        # -------------------------------------------------

        db.session.commit()

        flash(
            "All test sales and stock records have been cleared successfully.",
            "success"
        )

        return redirect(
            url_for("reports")
        )

    except Exception as e:

        db.session.rollback()

        flash(
            f"Could not clear test data: {str(e)}",
            "error"
        )

        return redirect(
            url_for("clear_test_data")
        )


if __name__ == "__main__":

    def start_flask():
        app.run(
            host="127.0.0.1",
            port=5000,
            debug=False,
            use_reloader=False
        )

    flask_thread = threading.Thread(
        target=start_flask,
        daemon=True
    )

    flask_thread.start()

    time.sleep(1.5)

    webview.create_window(
        "HORA Bookshop Management System",
        "http://127.0.0.1:5000",
        width=1280,
        height=800,
        resizable=True,
        min_size=(1000, 650)
    )

    webview.start()