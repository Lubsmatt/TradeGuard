from flask import Flask, render_template, request, redirect, url_for, session
from datetime import datetime
import sqlite3
from datetime import datetime
import os
import bcrypt
print("Database absolute path:", os.path.abspath("database.db"))

app = Flask(__name__)
DATABASE = "database.db"

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn
app.secret_key = "tradeguard_secure_key_2026"

# ===================== ALL PAIRS =====================

PAIR_VALUES = {
    # FOREX
    "EURUSD": 10,
    "GBPUSD": 10,
    "USDJPY": 9,
    "AUDUSD": 10,
    "NZDUSD": 10,
    "USDCAD": 10,
    "USDCHF": 10,
    "EURGBP": 10,
    "EURJPY": 9,
    "GBPJPY": 9,

    # METALS
    "XAUUSD (Gold)": 1,
    "XAGUSD (Silver)": 0.5,

    # INDICES
    "NAS100": 1,
    "SPX500": 1,
    "US30": 1,
    "GER40": 1,

    # CRYPTO
    "BTCUSD": 1,
    "ETHUSD": 1,
    "XRPUSD": 1,
    "SOLUSD": 1,
    "BNBUSD": 1
}

# ===================== HOME =====================

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/home")
def home():
    return render_template("home.html")

# ===================== REGISTER =====================

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()

        hashed_password = bcrypt.hashpw(
            password.encode("utf-8"),
            bcrypt.gensalt()
        )

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                (username, hashed_password)
            )
            conn.commit()
            print("User saved:", username)
            conn.close()
            return redirect(url_for("login"))
        except:
            conn.close()
            return "Username already exists"

    return render_template("register.html")

# ===================== LOGIN =====================

@app.route("/login", methods=["GET", "POST"])
def login():

    error = None

    if request.method == "POST":

        username = request.form["username"].strip()
        password = request.form["password"].strip()

        conn = get_db_connection()

        user = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        ).fetchone()

        conn.close()

        # ✅ MOVE THIS BLOCK INSIDE POST
        if user is None:
            error = "Username not found"
        else:
            stored_password = user["password"]

            if isinstance(stored_password, str):
                stored_password = stored_password.encode("utf-8")

            if not bcrypt.checkpw(password.encode("utf-8"), stored_password):
                error = "Wrong password"
            else:
                session.clear()

                session["user_id"] = user["id"]
                session["username"] = user["username"]
                session["plan"] = user["plan"]

                session["trade_count"] = 0
                session["daily_risk"] = 0
                session["last_trade"] = False

                return redirect(url_for("home"))

    return render_template("login.html", error=error)

    # ===================== LOGOUT =====================

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ===================== RISK CALCULATOR =====================
@app.route("/risk", methods=["GET", "POST"])
def risk():
    if "user_id" not in session:
        return redirect(url_for("login"))

    result = None
    error = None

    if "daily_risk" not in session:
        session["daily_risk"] = 0

    if request.method == "POST":
        try:
            balance = float(request.form["balance"])
            risk_percent = float(request.form["risk_percent"])
            sl = float(request.form["sl"])
            tp = float(request.form["tp"])
            pair = request.form["pair"]

            pip_value = PAIR_VALUES.get(pair)

            # ---- BASIC VALIDATIONS ----
            if pip_value is None:
                error = "Invalid trading pair selected."

            elif balance <= 0 or risk_percent <= 0:
                error = "Balance and Risk must be greater than 0."

            elif sl <= 0 or tp <= 0:
                error = "SL and TP must be greater than 0."

            elif session["plan"] == "free" and risk_percent > 2:
                error = "Free plan allows max 2% risk per trade. Upgrade to Pro."
        

            # ---- TRADE COUNT CHECK ----
            if error is None and session["plan"] == "free":
                if "trade_count" not in session:
                    session["trade_count"] = 0

                if session["trade_count"] >= 3:
                    error = "Free plan allows only 3 calculations per session. Upgrade to Pro."

            # ---- DAILY LIMIT CHECK ----
            if error is None:
                if session["daily_risk"] + risk_percent > 5:
                    error = "⚠️ Daily risk limit (5%) exceeded!"

            # ---- CALCULATION ----
            if error is None:

                if session["plan"] == "free":
                    session["trade_count"] += 1

                risk_amount = balance * (risk_percent / 100)
                lot = risk_amount / (sl * pip_value)
                lot = round(lot, 4)
                if lot < 0.01:
                    error = "Lot size too small. Increase risk or reduce stop loss."
                reward = lot * tp * pip_value
                reward = round(reward, 2)
                position_size = lot * 100000
                rr_ratio = round(tp / sl, 2)

                session["daily_risk"] += risk_percent
                session["last_trade"] = True

                result = {
                    "pair": pair,
                    "risk_amount": round(risk_amount, 2),
                    "lot": round (lot, 4),
                    "reward": reward,
                    "rr_ratio": rr_ratio,
                    "position_size": round(position_size, 2)
                }

                session["pending_trade"] = {
                    "pair": pair,
                    "risk_percent": risk_percent,
                    "rr_ratio": rr_ratio,
                    "risk_amount": round(risk_amount, 2),
                    "reward": reward
                }

        except Exception as e:
            error = f"Error: {str(e)}"

    return render_template(
        "risk.html",
        pairs=PAIR_VALUES.keys(),
        result=result,
        error=error,
        daily_risk=session["daily_risk"]
    )
         

# ===================== CHECKLIST =====================

@app.route("/check")
def check():

    if not session.get("last_trade"):
        return redirect(url_for("risk"))

    return render_template("check.html")


# ===================== RESET DAILY RISK =====================

@app.route("/reset")
def reset():
    session["daily_risk"] = 0
    return redirect(url_for("risk"))

@app.route("/confirm_trade", methods=["POST"])
def confirm_trade():

    if "user_id" not in session:
        return redirect(url_for("login"))

    trade = session.get("pending_trade")

    if not trade:
        return "Error: No trade found. Please calculate risk again."

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        user_id = session["user_id"]

        # ================= DAILY LIMIT CHECK =================
        cursor.execute(
            "SELECT daily_trades, last_trade_date, plan FROM users WHERE id = ?",
            (user_id,)
        )
        user = cursor.fetchone()

        daily_trades = user["daily_trades"] or 0
        last_trade_date = user["last_trade_date"]
        plan = user["plan"]

        today = datetime.now().strftime("%Y-%m-%d")

        if not last_trade_date or last_trade_date != today:
            daily_trades = 0

        # Limit free users
        if plan == "free" and daily_trades >= 5:
            return "Daily trade limit reached (5 trades). Upgrade to Pro."

        # Update count
        daily_trades += 1

        cursor.execute("""
            UPDATE users
            SET daily_trades = ?, last_trade_date = ?
            WHERE id = ?
        """, (daily_trades, today, user_id))

        # ================= SAVE TRADE =================
        cursor.execute("""
            INSERT INTO trades (
                user_id,
                pair,
                risk_percent,
                risk_amount,
                rr_ratio,
                reward,
                result,
                date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            trade.get("pair"),
            trade.get("risk_percent"),
            trade.get("risk_amount"),
            trade.get("rr_ratio"),
            trade.get("reward", 0),
            "pending",
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))

        conn.commit()

    except Exception as e:
        conn.close()
        return f"Error saving trade: {str(e)}"

    conn.close()

    session.pop("pending_trade", None)

    return redirect(url_for("journal"))

@app.route("/journal")
def journal():

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()

    trades = conn.execute(
        "SELECT * FROM trades WHERE user_id = ? ORDER BY date ASC",
        (session["user_id"],)
    ).fetchall()

    conn.close()

    # Separate trades
    wins = [t for t in trades if t["result"] == "win"]
    losses = [t for t in trades if t["result"] == "loss"]

    completed_trades = wins + losses
    total_trades = len(completed_trades)

    # Profit & Loss
    total_profit = sum(t["reward"] for t in wins)
    total_loss = sum(t["risk_amount"] for t in losses)

    net_pl = total_profit - total_loss

    # Win rate
    win_rate = (len(wins) / total_trades * 100) if total_trades > 0 else 0

    # Profit factor
    profit_factor = (total_profit / total_loss) if total_loss > 0 else total_profit

    # Total risk used today
    total_risk = sum(t["risk_percent"] for t in completed_trades)

    remaining_risk = 5 - total_risk
    if remaining_risk < 0:
        remaining_risk = 0

    # ================= EQUITY CURVE =================

    equity = 0
    equity_curve = []

    for trade in trades:

        if trade["result"] == "win":
            equity += trade["reward"]

        elif trade["result"] == "loss":
            equity -= trade["risk_amount"]

        equity_curve.append(round(equity, 2))

    print("Equity curve:", equity_curve)

    # ================= DRAWDOWN TRACKER =================

    peak = 0
    max_drawdown = 0
    current_drawdown = 0

    for value in equity_curve:

        if value > peak:
            peak = value

        drawdown = peak - value

        if drawdown > max_drawdown:
            max_drawdown = drawdown

        current_drawdown = drawdown

   # ================= PAIR ANALYTICS =================

    pair_stats = {}

    for trade in trades:

        pair = trade["pair"]

        if pair not in pair_stats:
           pair_stats[pair] = {
               "profit": 0,
               "trades": 0
           }

        pair_stats[pair]["trades"] += 1

        if trade["result"] == "win":
            pair_stats[pair]["profit"] += trade["reward"]

        elif trade["result"] == "loss":
            pair_stats[pair]["profit"] -= trade["risk_amount"]


    best_pair = None
    worst_pair = None
    most_traded = None

    if pair_stats:

        best_pair = max(pair_stats, key=lambda p: pair_stats[p]["profit"])
        worst_pair = min(pair_stats, key=lambda p: pair_stats[p]["profit"])
        most_traded = max(pair_stats, key=lambda p: pair_stats[p]["trades"])

    # ================= STREAK TRACKER =================

    current_streak = 0
    current_type = None

    max_win_streak = 0
    max_loss_streak = 0

    temp_streak = 0
    temp_type = None

    for trade in trades:

        result = trade["result"]

        if result not in ["win", "loss"]:
            continue

        if result == temp_type:
            temp_streak += 1
        else:
            temp_type = result
            temp_streak = 1

        if temp_type == "win":
            max_win_streak = max(max_win_streak, temp_streak)
        else:
            max_loss_streak = max(max_loss_streak, temp_streak)

        current_streak = temp_streak
        current_type = temp_type
         
    return render_template(
        "journal.html",
        trades=trades,
        total_trades=total_trades,
        total_risk=round(total_risk, 2),
        remaining_risk=round(remaining_risk, 2),
        net_pl=round(net_pl, 2),
        win_rate=round(win_rate, 2),
        profit_factor=round(profit_factor, 2),
        equity_curve=equity_curve,
        best_pair=best_pair,
        worst_pair=worst_pair,
        most_traded=most_traded,
        current_streak=current_streak,
        current_type=current_type,
        max_win_streak=max_win_streak,
        max_loss_streak=max_loss_streak,
        max_drawdown=round(max_drawdown,2),
        current_drawdown=round(current_drawdown,2),
    )

@app.route("/update_result/<int:trade_id>/<result>")
def update_result(trade_id, result):

    if result not in ["win", "loss"]:
        return redirect(url_for("journal"))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE trades SET result = ? WHERE id = ? AND user_id = ?",
        (result, trade_id, session["user_id"])
    )

    conn.commit()
    conn.close()

    return redirect(url_for("journal"))

def init_db():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    # USERS TABLE
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password BLOB,
        plan TEXT DEFAULT 'free',
        daily_trades INTEGER DEFAULT 0,
        last_trade_date TEXT
    )
    """)

    # Add columns if they don’t exist
    try:
        c.execute("ALTER TABLE users ADD COLUMN daily_trades INTEGER DEFAULT 0")
    except:
        pass

    try:
        c.execute("ALTER TABLE users ADD COLUMN last_trade_date TEXT")
    except:
        pass

    # TRADES TABLE (🔥 MOVE THIS UP BEFORE CLOSE)
    c.execute("""
    CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        pair TEXT,
        risk_percent REAL,
        risk_amount REAL,
        rr_ratio REAL,
        reward REAL,
        result TEXT DEFAULT 'pending',
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
        date = db.Column(db.Date, default=date.today)
    )
    """)

    conn.commit()
    conn.close()
    
@app.route("/history")
def history():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("""
        SELECT pair, risk_percent, risk_amount, rr_ratio, reward, date
        FROM trades
        WHERE user_id = ?
        ORDER BY date DESC
    """, (session["user_id"],))

    trades = c.fetchall()
    conn.close()

    print("Current session user_id:", session["user_id"])

    return render_template("history.html", trades=trades)  

import os

init_db()  # runs when app starts on Render

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)