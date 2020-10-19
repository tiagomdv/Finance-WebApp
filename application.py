import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

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

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    userid = session["user_id"]

    # Database query to get all the information to build the table
    status = db.execute("SELECT upper(symbol) symbol, sum(shares) shares FROM history WHERE id=:userid GROUP BY symbol", userid=userid)

    # Variable to sum all the values throghout this part of code
    totalValue = 0

    # Goes through every row and adds the dict with quote info to the list of dicts that will form the table
    for row in status:
        quote = lookup(row["symbol"])
        row.update(quote)

        row["value"] = row["shares"] * row["price"]
        totalValue += int(row["value"])

        # Does some cell formatting
        row["price"] = usd(row["price"])
        row["value"] = usd(row["value"])

    # Creates 2 lists of dict to form the last 2 rows. One with the cash values and other with total value
    getCash = db.execute("SELECT cash FROM users WHERE id=:userid", userid=userid)
    currentCash = usd(getCash[0]["cash"])

    totalValue += int(getCash[0]["cash"])

    # Creates the lists
    cash = {"symbol": "CASH", "value": currentCash}
    total = {"symbol": "Total Value", "value": usd(totalValue)}

    # Updates the list of dict with the 2 lists
    status.append(cash)
    status.append(total)

    return render_template("index.html", status=status)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "GET":
        return render_template("buy.html")

    if request.method == "POST":

        # Executes different commands depending on which button is pressed, Buy or Check Quote
        if request.form["submit"] == "buy":
            # Gets the info from the form
            shares = request.form.get("shares")
            symbol = request.form.get("symbol")

            # Gets the remaining info to fill the database entry
            quote = lookup(symbol)
            userid = session["user_id"]

            # Gets the value to check if theres cash available to put the order
            total_value = int(quote["price"]) * int(shares)
            row = db.execute("SELECT cash FROM users WHERE id=:userid", userid=userid)
            actual_cash = row[0]["cash"]

            if int(total_value) > int(actual_cash):
                return render_template("buy.html", total=usd(total_value), cash=usd(actual_cash))

            # Creates table if not exists
            db.execute("CREATE TABLE IF NOT EXISTS history (order_id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, date DATA NOT NULL, shares NUMERIC NOT NULL, symbol TEXT NOT NULL, price NUMERIC NOT NULL, id INTEGER NOT NULL, FOREIGN KEY (id) REFERENCES users (id));")

            # Creates a registry of the buying order
            db.execute("INSERT INTO history (date, shares, symbol, price, id) VALUES (datetime(), :shares, :symbol, :price, :userid);", shares=shares, symbol=symbol, price=quote["price"], userid=userid)

            # Updates the cash column in the users database
            new_cash_value = actual_cash - total_value
            db.execute("UPDATE users SET cash=:newcash WHERE id=:userid", newcash=new_cash_value, userid=userid)

            flash("YOU BOUGHT SHARES DUDE")
            return render_template("buy.html", userid=userid, shares=shares, symbol=symbol, price=quote["price"], name=quote["name"])

        if request.form["submit"] == "check":
            quote = lookup(request.form.get("symbol"))

            shares = request.form.get("shares")

            return render_template("buy.html", shares=shares, companyName=quote["name"], stockPrice=quote["price"], symbol=quote["symbol"])


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    userid = session["user_id"]

    history = db.execute("SELECT * FROM history WHERE id=:userid", userid=userid)

    return render_template("history.html", history=history)


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

    symbol = request.form.get("quote")

    if request.method == "GET":
        return render_template("quote.html")

    if request.method == "POST":

        if symbol:
            quote = lookup(symbol)
            return render_template("quote.html", companyName=quote["name"], stockPrice=quote["price"], symbol=quote["symbol"])
        else:
            flash("Insert a valid company symbol!")
            return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "GET":
        return render_template("register.html")

    if request.method == "POST":

        # Ensure username is correctly introduced
        if not request.form.get("username"):
            return apology("Must provide username", 403)

        # Ensure password is correctly introduced
        if not request.form.get("password"):
            return apology("Must provide password", 403)

        # Command to insert user data into database
        db.execute("INSERT INTO users (username, hash) VALUES (:username, :passhash)", username=request.form.get("username"), passhash=generate_password_hash(request.form.get("password"), method='pbkdf2:sha256', salt_length=8))

    return redirect("/login")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    if request.method == "GET":
        return render_template("sell.html")

    if request.method == "POST":
        # Getting necessary variables
        symbol = request.form.get("symbol")
        shares = int(request.form.get("shares")) * (-1)
        userid = session["user_id"]

        # Get current price
        quote = lookup(symbol)
        currentPrice = quote["price"]
        cashReturn = shares * currentPrice

        # Checks if user is selling more shares than it has
        # Get current share number of selected stock

        numberShares = db.execute("SELECT sum(shares) shares FROM history WHERE id = :userid AND symbol = :symbol GROUP BY symbol", userid=userid, symbol=symbol)
        hasValue = numberShares[0]["shares"]

        if (shares * (-1)) > numberShares[0]["shares"]:
            return render_template("sell.html", shares=numberShares[0]["shares"], numbershares=shares*(-1), symbol=symbol)
        else:
            if hasValue == 0:
                return render_template("sell.html", shares=numberShares[0]["shares"], numbershares=shares*(-1), symbol=symbol)

        # Update shares history
        db.execute("INSERT INTO history (date, shares, symbol, price, id) VALUES (datetime(), :shares, :symbol, :price, :userid);", shares=shares, symbol=symbol, price=currentPrice, userid=userid)

        # Update cash position
        # Get actual cash position
        cashPosition = db.execute("SELECT cash FROM users WHERE id=:userid",userid=userid)

        # Updates cash position and updates database
        cashUpdated = cashPosition[0]["cash"] - cashReturn

        db.execute("UPDATE users SET cash=:newcash", newcash = cashUpdated)

        return render_template("sell.html", userid=userid, shares=shares * (-1), name=quote["name"], symbol=symbol)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
