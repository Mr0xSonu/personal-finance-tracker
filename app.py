
import re
import os

from datetime import timedelta, datetime
from urllib.parse import urlparse

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash
)

from flask_sqlalchemy import SQLAlchemy

from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    login_required,
    current_user,
    logout_user
)

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)


# ==========================================
# DATABASE AND LOGIN INITIALIZATION
# ==========================================

db = SQLAlchemy()
login_manager = LoginManager()


# ==========================================
# CATEGORY LISTS
# ==========================================

EXPENSE_CATEGORIES = {
    "Food",
    "Shopping",
    "Travel",
    "Education",
    "Bills",
    "Entertainment",
    "Health",
    "Other"
}

INCOME_CATEGORIES = {
    "Salary",
    "Business",
    "Freelancing",
    "Investment",
    "Gift",
    "Other"
}


# ==========================================
# USER MODEL
# ==========================================

class User(UserMixin, db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    username = db.Column(
        db.String(80),
        unique=True,
        nullable=False
    )

    email = db.Column(
        db.String(120),
        unique=True,
        nullable=False
    )

    password_hash = db.Column(
        db.String(255),
        nullable=False
    )

    def __repr__(self):
        return f"<User {self.username}>"


# ==========================================
# EXPENSE MODEL
# ==========================================

class Expense(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    amount = db.Column(
        db.Float,
        nullable=False
    )

    category = db.Column(
        db.String(100),
        nullable=False
    )

    description = db.Column(
        db.String(255)
    )

    date = db.Column(
        db.Date,
        nullable=False
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False,
        index=True
    )

    def __repr__(self):
        return f"<Expense {self.amount}>"


# ==========================================
# INCOME MODEL
# ==========================================

class Income(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    amount = db.Column(
        db.Float,
        nullable=False
    )

    category = db.Column(
        db.String(100),
        nullable=False
    )

    description = db.Column(
        db.String(255)
    )

    date = db.Column(
        db.Date,
        nullable=False
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False,
        index=True
    )

    def __repr__(self):
        return f"<Income {self.amount}>"


# ==========================================
# SAFE REDIRECT FUNCTION
# ==========================================

def is_safe_local_path(target):

    if not target:
        return False

    parts = urlparse(target)

    return (
        parts.scheme == ""
        and parts.netloc == ""
        and target.startswith("/")
        and not target.startswith("//")
    )


# ==========================================
# APPLICATION FACTORY
# ==========================================

def create_app():

    app = Flask(__name__)

    app.config["SECRET_KEY"] = os.environ.get(
        "SECRET_KEY",
        "dev-secret-key"
    )

    # SQLite Database
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///app.db"

    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    app.config["REMEMBER_COOKIE_DURATION"] = timedelta(days=15)

    # Initialize Database
    db.init_app(app)

    # Initialize Login Manager
    login_manager.init_app(app)

    login_manager.login_view = "login"

    # Create Database Tables
    with app.app_context():

        db.create_all()

        print("Database tables created successfully!")

        print("Database location:", db.engine.url.database)

    # ======================================
    # DATABASE USER LOADER
    # ======================================

    @login_manager.user_loader
    def load_user(user_id):

        try:
            return db.session.get(User, int(user_id))

        except (ValueError, TypeError):
            return None

    # ======================================
    # HOME ROUTE
    # ======================================

    @app.route("/")
    def index():

        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))

        return render_template("index.html")

    # ======================================
    # DATABASE HEALTH CHECK
    # ======================================

    @app.route("/health/db")
    def database_health():

        try:

            db.session.execute(text("SELECT 1"))

            return {
                "status": "connected",
                "database": "SQLite"
            }

        except Exception as e:

            return {
                "status": "error",
                "message": str(e)
            }, 500

    # ======================================
    # DASHBOARD
    # ======================================

    @app.route("/dashboard")
    @login_required
    def dashboard():

        expenses = Expense.query.filter_by(
            user_id=current_user.id
        ).order_by(
            Expense.date.desc(),
            Expense.id.desc()
        ).all()

        incomes = Income.query.filter_by(
            user_id=current_user.id
        ).order_by(
            Income.date.desc(),
            Income.id.desc()
        ).all()

        total_expenses = sum(
            expense.amount for expense in expenses
        )

        total_income = sum(
            income.amount for income in incomes
        )

        total_balance = total_income - total_expenses

        return render_template(
            "dashboard.html",
            expenses=expenses,
            incomes=incomes,
            total_income=total_income,
            total_expenses=total_expenses,
            total_balance=total_balance
        )

    # ======================================
    # ADD EXPENSE
    # ======================================

    @app.route("/add_expense", methods=["POST"])
    @login_required
    def add_expense():

        try:

            amount = float(request.form.get("amount", 0))

            category = request.form.get(
                "category", ""
            ).strip()

            description = request.form.get(
                "description", ""
            ).strip()

            date_value = request.form.get("date", "")

            if not 0 < amount <= 100000000:

                flash(
                    "Please enter a valid expense amount.",
                    "error"
                )

                return redirect(url_for("dashboard"))

            if category not in EXPENSE_CATEGORIES:

                flash(
                    "Please select a valid expense category.",
                    "error"
                )

                return redirect(url_for("dashboard"))

            if len(description) > 255:

                flash(
                    "Description is too long.",
                    "error"
                )

                return redirect(url_for("dashboard"))

            expense_date = datetime.strptime(
                date_value,
                "%Y-%m-%d"
            ).date()

            new_expense = Expense(
                amount=amount,
                category=category,
                description=description,
                date=expense_date,
                user_id=current_user.id
            )

            db.session.add(new_expense)

            db.session.commit()

            flash(
                "Expense added successfully!",
                "success"
            )

        except (ValueError, TypeError):

            db.session.rollback()

            flash(
                "Please enter valid expense details.",
                "error"
            )

        except Exception:

            db.session.rollback()

            flash(
                "Something went wrong while adding expense.",
                "error"
            )

        return redirect(url_for("dashboard"))

    # ======================================
    # EDIT EXPENSE
    # ======================================

    @app.route(
        "/expense/<int:expense_id>/edit",
        methods=["POST"]
    )
    @login_required
    def edit_expense(expense_id):

        expense = Expense.query.filter_by(
            id=expense_id,
            user_id=current_user.id
        ).first_or_404()

        try:

            amount = float(request.form.get("amount", 0))

            category = request.form.get(
                "category", ""
            ).strip()

            description = request.form.get(
                "description", ""
            ).strip()

            date_value = request.form.get("date", "")

            if not 0 < amount <= 100000000:

                flash(
                    "Please enter a valid amount.",
                    "error"
                )

                return redirect(url_for("dashboard"))

            if category not in EXPENSE_CATEGORIES:

                flash(
                    "Invalid expense category.",
                    "error"
                )

                return redirect(url_for("dashboard"))

            if len(description) > 255:

                flash(
                    "Description is too long.",
                    "error"
                )

                return redirect(url_for("dashboard"))

            expense.date = datetime.strptime(
                date_value,
                "%Y-%m-%d"
            ).date()

            expense.amount = amount

            expense.category = category

            expense.description = description

            db.session.commit()

            flash(
                "Expense updated successfully!",
                "success"
            )

        except (ValueError, TypeError):

            db.session.rollback()

            flash(
                "Invalid expense details.",
                "error"
            )

        except Exception:

            db.session.rollback()

            flash(
                "Unable to update expense.",
                "error"
            )

        return redirect(url_for("dashboard"))

    # ======================================
    # DELETE EXPENSE
    # ======================================

    @app.route(
        "/expense/<int:expense_id>/delete",
        methods=["POST"]
    )
    @login_required
    def delete_expense(expense_id):

        expense = Expense.query.filter_by(
            id=expense_id,
            user_id=current_user.id
        ).first_or_404()

        try:

            db.session.delete(expense)

            db.session.commit()

            flash(
                "Expense deleted successfully!",
                "success"
            )

        except Exception:

            db.session.rollback()

            flash(
                "Unable to delete expense.",
                "error"
            )

        return redirect(url_for("dashboard"))

    # ======================================
    # ADD INCOME
    # ======================================

    @app.route("/add_income", methods=["POST"])
    @login_required
    def add_income():

        try:

            amount = float(request.form.get("amount", 0))

            category = request.form.get(
                "category", ""
            ).strip()

            description = request.form.get(
                "description", ""
            ).strip()

            date_value = request.form.get("date", "")

            if not 0 < amount <= 100000000:

                flash(
                    "Please enter a valid income amount.",
                    "error"
                )

                return redirect(url_for("dashboard"))

            if category not in INCOME_CATEGORIES:

                flash(
                    "Please select a valid income category.",
                    "error"
                )

                return redirect(url_for("dashboard"))

            if len(description) > 255:

                flash(
                    "Description is too long.",
                    "error"
                )

                return redirect(url_for("dashboard"))

            income_date = datetime.strptime(
                date_value,
                "%Y-%m-%d"
            ).date()

            new_income = Income(
                amount=amount,
                category=category,
                description=description,
                date=income_date,
                user_id=current_user.id
            )

            db.session.add(new_income)

            db.session.commit()

            flash(
                "Income added successfully!",
                "success"
            )

        except (ValueError, TypeError):

            db.session.rollback()

            flash(
                "Please enter valid income details.",
                "error"
            )

        except Exception:

            db.session.rollback()

            flash(
                "Something went wrong while adding income.",
                "error"
            )

        return redirect(url_for("dashboard"))

    # ======================================
    # EDIT INCOME
    # ======================================

    @app.route(
        "/income/<int:income_id>/edit",
        methods=["POST"]
    )
    @login_required
    def edit_income(income_id):

        income = Income.query.filter_by(
            id=income_id,
            user_id=current_user.id
        ).first_or_404()

        try:

            amount = float(request.form.get("amount", 0))

            category = request.form.get(
                "category", ""
            ).strip()

            description = request.form.get(
                "description", ""
            ).strip()

            date_value = request.form.get("date", "")

            if not 0 < amount <= 100000000:

                flash(
                    "Please enter a valid income amount.",
                    "error"
                )

                return redirect(url_for("dashboard"))

            if category not in INCOME_CATEGORIES:

                flash(
                    "Invalid income category.",
                    "error"
                )

                return redirect(url_for("dashboard"))

            if len(description) > 255:

                flash(
                    "Description is too long.",
                    "error"
                )

                return redirect(url_for("dashboard"))

            income.date = datetime.strptime(
                date_value,
                "%Y-%m-%d"
            ).date()

            income.amount = amount

            income.category = category

            income.description = description

            db.session.commit()

            flash(
                "Income updated successfully!",
                "success"
            )

        except (ValueError, TypeError):

            db.session.rollback()

            flash(
                "Invalid income details.",
                "error"
            )

        except Exception:

            db.session.rollback()

            flash(
                "Unable to update income.",
                "error"
            )

        return redirect(url_for("dashboard"))

    # ======================================
    # DELETE INCOME
    # ======================================

    @app.route(
        "/income/<int:income_id>/delete",
        methods=["POST"]
    )
    @login_required
    def delete_income(income_id):

        income = Income.query.filter_by(
            id=income_id,
            user_id=current_user.id
        ).first_or_404()

        try:

            db.session.delete(income)

            db.session.commit()

            flash(
                "Income deleted successfully!",
                "success"
            )

        except Exception:

            db.session.rollback()

            flash(
                "Unable to delete income.",
                "error"
            )

        return redirect(url_for("dashboard"))

    # ======================================
    # REGISTER
    # ======================================

    @app.route("/register", methods=["GET", "POST"])
    def register():

        if current_user.is_authenticated:

            return redirect(url_for("dashboard"))

        if request.method == "POST":

            username = request.form.get(
                "username", ""
            ).strip()

            email = request.form.get(
                "email", ""
            ).strip().lower()

            password = request.form.get(
                "password", ""
            )

            confirm_password = request.form.get(
                "confirm_password", ""
            )

            if len(username) < 3 or len(username) > 80:

                flash(
                    "Username must be between 3 and 80 characters.",
                    "error"
                )

                return redirect(url_for("register"))

            if not re.match(
                r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
                email
            ):

                flash(
                    "Please enter a valid email address.",
                    "error"
                )

                return redirect(url_for("register"))

            if len(password) < 6:

                flash(
                    "Password must contain at least 6 characters.",
                    "error"
                )

                return redirect(url_for("register"))

            if password != confirm_password:

                flash(
                    "Passwords do not match.",
                    "error"
                )

                return redirect(url_for("register"))

            new_user = User(
                username=username,
                email=email,
                password_hash=generate_password_hash(password)
            )

            try:

                db.session.add(new_user)

                db.session.commit()

                flash(
                    "Registration successful! Please login.",
                    "success"
                )

                return redirect(url_for("login"))

            except IntegrityError:

                db.session.rollback()

                flash(
                    "Username or email already exists.",
                    "error"
                )

            except Exception:

                db.session.rollback()

                flash(
                    "Registration failed. Please try again.",
                    "error"
                )

        return render_template("register.html")

    # ======================================
    # LOGIN
    # ======================================

    @app.route("/login", methods=["GET", "POST"])
    def login():

        if current_user.is_authenticated:

            return redirect(url_for("dashboard"))

        if request.method == "POST":

            email = request.form.get(
                "email", ""
            ).strip().lower()

            password = request.form.get(
                "password", ""
            )

            remember = request.form.get("remember") == "1"

            user = User.query.filter_by(
                email=email
            ).first()

            if user and check_password_hash(
                user.password_hash,
                password
            ):

                login_user(
                    user,
                    remember=remember
                )

                next_page = request.args.get("next")

                flash(
                    "Login successful!",
                    "success"
                )

                if is_safe_local_path(next_page):

                    return redirect(next_page)

                return redirect(url_for("dashboard"))

            flash(
                "Invalid email or password.",
                "error"
            )

        return render_template("login.html")

    # ======================================
    # LOGOUT
    # ======================================

    @app.route("/logout")
    @login_required
    def logout():

        logout_user()

        flash(
            "You have been logged out.",
            "success"
        )

        return redirect(url_for("login"))

    # ======================================
    # CHANGE PASSWORD
    # ======================================

    @app.route(
        "/change_password",
        methods=["GET", "POST"]
    )
    @login_required
    def change_password():

        if request.method == "POST":

            current_password = request.form.get(
                "current_password", ""
            )

            new_password = request.form.get(
                "new_password", ""
            )

            confirm_password = request.form.get(
                "confirm_password", ""
            )

            if not check_password_hash(
                current_user.password_hash,
                current_password
            ):

                flash(
                    "Current password is incorrect.",
                    "error"
                )

                return redirect(url_for("change_password"))

            if len(new_password) < 6:

                flash(
                    "New password must contain at least 6 characters.",
                    "error"
                )

                return redirect(url_for("change_password"))

            if new_password != confirm_password:

                flash(
                    "New passwords do not match.",
                    "error"
                )

                return redirect(url_for("change_password"))

            current_user.password_hash = generate_password_hash(
                new_password
            )

            db.session.commit()

            flash(
                "Password changed successfully!",
                "success"
            )

            return redirect(url_for("dashboard"))

        return render_template("change_password.html")

    # ======================================
    # TEST ROUTE
    # ======================================

    @app.route("/test")
    @login_required
    def test():

        return "Flask Login System Working Successfully!"

    return app


# ==========================================
# CREATE APPLICATION
# ==========================================

app = create_app()


# ==========================================
# RUN APPLICATION
# ==========================================

if __name__ == "__main__":

    app.run(
        debug=True,
        port=5555
    )

