import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime
from time import strftime
from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    rows = db.execute("SELECT * FROM transactions WHERE :id",
                        id = session["user_id"])
    data = []
    symbols_owned = set()
    balance = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])[0]['cash']
    grand_total = balance
    for row in rows:
        symbols_owned.add(row["symbol"])
    for symbol in list(symbols_owned):

        name = lookup(symbol)["name"]
        price = lookup(symbol)["price"]
        shares = db.execute("SELECT SUM(shares) FROM transactions WHERE symbol = :symbol AND id = :id",id=session["user_id"],symbol=symbol)[0]["SUM(shares)"]
        if shares == None:
            total = 0
            shares = 0
        else:
            total = price * shares
        grand_total = grand_total + total
        if shares != 0:
            data.append((symbol, name, shares, usd(price), usd(total)))

    return render_template("index.html",
                            grand_total=usd(grand_total),
                            data=data,
                            balance=usd(balance))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "GET":
        return render_template("buy.html")
    if request.method == "POST":
        req = lookup(request.form.get("symbol"))
        if not request.form.get("symbol") or not req:
            return apology("Invalid input")

        SQL = db.execute("SELECT cash FROM users WHERE id = :id", id = session["user_id"])
        cash = SQL[0]["cash"]
        company_name = req["name"]
        price = req["price"]
        symbol = req["symbol"]
        quantity = int(request.form.get("shares"))
        total = price * int(quantity)
        time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if cash < total :
            return apology("You can't afford it")
        else:
            db.execute("INSERT INTO transactions (id, symbol, name, shares, price, total, transacted) VALUES (:user_id, :symbol, :name, :shares, :price, :total, :time)",
                        user_id = session["user_id"],
                        symbol = symbol,
                        name = company_name,
                        shares = int(request.form.get("shares")),
                        price = price,
                        total = usd(total),
                        time = time)
            cash = cash - total
            db.execute("UPDATE users SET cash =:cash WHERE id =:id",
                        cash = cash,
                        id = session["user_id"])


            return redirect("/")

@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    rows = db.execute("SELECT * FROM transactions WHERE id = :id", id = session["user_id"])
    data = []
    for row in rows:
        symbol = row["symbol"]
        shares = row["shares"]
        price = usd(row["price"])
        transacted = row["transacted"]
        data.append((symbol, shares, price, transacted))

    return render_template("history.html",data=data)


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
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
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
    if request.method == "GET":
        return render_template("quote.html")
    if request.method == "POST":
        req = lookup(request.form.get("quote"))
        if req == None :
            return apology("Invalid symbol")
        else:
            company_name = req["name"]
            price = usd(req["price"])
            symbol = req["symbol"]
            return render_template("quoted.html", company_name=company_name, price=price, symbol=symbol)

       # return render_template("quoted.html", companyName=companyName, price=price, symbol=symbol)




@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        if not request.form.get("username"):
            return apology("Must provide username.")

        if not request.form.get("password"):
            return apology("Must provide password.")

        if not request.form.get("confirm"):
            return apology("Must confirm password.")

        if request.form.get("password") != request.form.get("confirm"):
            return apology("Password confirmation failed.")

        result = db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)",
                            username = request.form.get("username"),
                            hash = generate_password_hash(request.form.get("password")))
        if not result:
            return apology("User already existed")
        else:
            rows = db.execute("SELECT * FROM users WHERE username = :username",
                              username=request.form.get("username"))
            session["user_id"] = rows[0]["id"]
            return redirect("/")

    if request.method == "GET":
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "GET":
        return render_template("sell.html")
    if request.method == "POST":
        req = lookup(request.form.get("symbol"))
        if not request.form.get("symbol") or not req :
            return apology("Missing symbol")
        if not request.form.get("shares"):
            return apology("Missing shares")
        cash = db.execute("SELECT cash FROM users WHERE id = :id", id = session["user_id"])[0]["cash"]
        company_name = req["name"]
        price = req["price"]
        time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        symbol = request.form.get("symbol")
        shares = int(request.form.get("shares"))
        total = price * int(shares)
        shares_owned = db.execute("SELECT SUM(shares) FROM transactions WHERE symbol = :symbol AND id = :id",id=session["user_id"],symbol=symbol)[0]["SUM(shares)"]
        if not shares_owned:
            return apology("Missing stock")
        if shares > shares_owned:
            return apology("Too many stocks")
        else:
            db.execute("INSERT INTO transactions (id, symbol, name, shares, price, total, transacted) VALUES (:user_id, :symbol, :name, :shares, :price, :total, :time)",
                        user_id = session["user_id"],
                        symbol = symbol,
                        name = company_name,
                        shares = - shares,
                        price = price,
                        total = usd(total),
                        time = time)
            cash = cash + total
            db.execute("UPDATE users SET cash =:cash WHERE id =:id",
                        cash = cash,
                        id = session["user_id"])
            return redirect("/")





def errorhandler(e):
    """Handle error"""
    return apology(e.name, e.code)


# listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
