import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    # Get the user's cash balance from the database
    user_id = session["user_id"]
    user = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=user_id)
    cash = user[0]["cash"]

    # Get the user's stocks from the database
    stocks = db.execute(
        "SELECT * FROM stocks WHERE user_id = :user_id", user_id=user_id
    )

    # Create a list to store the data for each stock
    stocks_data = []

    for stock in stocks:
        symbol = stock["symbol"]
        shares = int(stock["share"])
        result = lookup(symbol)
        price = result["price"]
        name = result["name"]
        total = shares * price

        stocks_data.append(
            {
                "symbol": symbol,
                "name": name,
                "shares": shares,
                "price": price,
                "total": total,
            }
        )

    # Calculate the total value of stocks
    total_stocks_value = sum([stock["total"] for stock in stocks_data])

    # Calculate the overall total (cash + stocks value)
    total_balance = cash + total_stocks_value

    return render_template(
        "index.html",
        cash=usd(cash),
        stocks=stocks_data,
        total_balance=usd(total_balance),
    )


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    if request.method == "POST":
        if not request.form.get("symbol"):
            return apology("must provide form", 400)

        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        # Ensure that the number of shares is positive
        try:
            if (not shares) or (not float(shares).is_integer()) or float(shares) < 1:
                return apology("shares must be a positive number", 400)
        except:
            return apology("shares must be a positive number", 400)

        result = lookup(symbol)
        if result is None:
            return apology("The symbol is invalid")

        # Calculate the total cost of the shares
        final_price = result["price"] * int(shares)

        # Get the user's cash balance from the database
        user_id = session["user_id"]
        user = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=user_id)
        cash_balance = user[0]["cash"]

        try:
            # Check if the user has enough cash to buy the shares
            if final_price <= cash_balance:
                # Deduct the cost from the user's cash balance
                new_cash_balance = cash_balance - final_price
                db.execute(
                    "UPDATE users SET cash = :new_cash_balance WHERE id = :user_id",
                    new_cash_balance=new_cash_balance,
                    user_id=user_id,
                )

                # Record the transaction in the database
                db.execute(
                    "INSERT INTO transactions (user_id, symbol, price, shares, action) VALUES (:user_id, :symbol, :price, :shares, 'BUY')",
                    user_id=user_id,
                    symbol=symbol,
                    price=result["price"],
                    shares=shares,
                )

                # Check if the user already owns shares of this stock
                existing_stock = db.execute(
                    "SELECT * FROM stocks WHERE user_id = :user_id AND symbol = :symbol",
                    user_id=user_id,
                    symbol=symbol,
                )

                if existing_stock:
                    # Update the number of shares
                    existing_shares = existing_stock[0]["share"]
                    new_shares = existing_shares + int(shares)
                    db.execute(
                        "UPDATE stocks SET share = :new_shares WHERE user_id = :user_id AND symbol = :symbol",
                        new_shares=new_shares,
                        user_id=user_id,
                        symbol=symbol,
                    )
                else:
                    # Insert a new stock entry for the user
                    db.execute(
                        "INSERT INTO stocks (user_id, symbol, share) VALUES (:user_id, :symbol, :share)",
                        user_id=user_id,
                        symbol=symbol,
                        share=int(shares),
                    )

                flash("Shares purchased successfully!")
                return redirect("/")
            else:
                return apology(
                    "You do not have enough money to buy this number of shares"
                )
        except:
            flash("Transaction failed")
            return redirect("/")

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    user_id = session["user_id"]
    transactions = db.execute(
        "SELECT * FROM transactions WHERE user_id = :user_id", user_id=user_id
    )
    return render_template("history.html", transactions=transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    if request.method == "POST":
        if not request.form.get("symbol"):
            return apology("must provide symbol", 400)

        symbol = request.form.get("symbol")
        result = lookup(symbol)

        if result is None:
            return apology("The symbol is invalid")

        return render_template(
            "quoted.html",
            symbol=result["symbol"],
            name=result["name"],
            price=(result["price"]),
        )

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Ensure confirmation password was submitted
        elif not request.form.get("confirmation"):
            return apology("must provide confirmation password", 400)

        # Check if passwords match
        if request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords do not match", 400)

        # Query database for existing username
        existing_user = db.execute(
            "SELECT * FROM users WHERE username = :username",
            username=request.form.get("username"),
        )

        # Check if the username already exists
        if existing_user:
            return apology("username already exists", 400)

        # Hash the password
        hashed_password = generate_password_hash(request.form.get("password"))

        # Insert the new user into the database
        result = db.execute(
            "INSERT INTO users (username, hash, cash) VALUES (:username, :hash, 10000.00)",
            username=request.form.get("username"),
            hash=hashed_password,
        )

        # Check if the registration was successful
        if not result:
            return apology("registration failed", 500)

        # Log in the newly registered user
        user_id = db.execute(
            "SELECT id FROM users WHERE username = :username",
            username=request.form.get("username"),
        )
        session["user_id"] = user_id[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        user_id = session["user_id"]
        symbol = request.form.get("symbol")
        share = int(request.form.get("shares"))

        # Ensure that the number of shares is positive
        if share < 1:
            return apology("number of shares must be a positive number", 400)

        result = lookup(symbol)
        if result is None:
            return apology("The symbol is invalid")

        # Get the user's shares of the stock from the database
        user_stock = db.execute(
            "SELECT share FROM stocks WHERE user_id = :user_id AND symbol = :symbol",
            user_id=user_id,
            symbol=symbol,
        )

        if not user_stock or user_stock[0]["share"] < share:
            return apology("You don't have enough shares to sell", 400)

        try:
            # Calculate the total value of the shares being sold
            total_sale_amount = result["price"] * share

            # Update the user's cash balance
            db.execute(
                "UPDATE users SET cash = cash + :total_sale_amount WHERE id = :user_id",
                total_sale_amount=total_sale_amount,
                user_id=user_id,
            )

            # Update the user's stock portfolio
            db.execute(
                "UPDATE stocks SET share = share - :share WHERE user_id = :user_id AND symbol = :symbol",
                share=share,
                user_id=user_id,
                symbol=symbol,
            )

            # Record the transaction in the database
            db.execute(
                "INSERT INTO transactions (user_id, symbol, price, shares, action) VALUES (:user_id, :symbol, :price, :shares, 'SELL')",
                user_id=user_id,
                symbol=symbol,
                price=result["price"],
                shares=share,
            )

            flash("Shares sold successfully!")
            return redirect("/")
        except:
            flash("Transaction failed")
            return redirect("/")

    else:
        # Get the symbols of stocks that the user owns
        user_id = session["user_id"]
        stocks = db.execute(
            "SELECT DISTINCT symbol FROM stocks WHERE user_id = :user_id",
            user_id=user_id,
        )
        return render_template("sell.html", stocks=stocks)



@app.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():
    """User investment"""

    if request.method == "POST":
        id = session["user_id"]
        user_cash = request.form.get("cash")
        cash = db.execute("SELECT cash FROM users WHERE id = :id", id=id)

        total_amount = cash[0]["cash"] + int(user_cash)
        db.execute("UPDATE users SET cash = :total_amount WHERE id = :id", total_amount=total_amount, id=id)

        flash("Transaction successfully!")
        return redirect("/")

    else:
        return render_template("deposit.html")

