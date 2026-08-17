from flask import Flask, request, jsonify, render_template_string, redirect, url_for
from flask_login import LoginManager, login_user, logout_user, login_required, UserMixin, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import random

app = Flask(__name__)
app.secret_key = "secret_key_here"

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


# ==========================
# DB 初期化
# ==========================
def init_db():
    conn = sqlite3.connect("users.db")
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        coins INTEGER DEFAULT 100
    )
    """)
    conn.commit()
    conn.close()


init_db()


# ==========================
# User クラス
# ==========================
class User(UserMixin):
    def __init__(self, id, username, password_hash, coins):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.coins = coins


def get_user_by_username(username):
    conn = sqlite3.connect("users.db")
    cur = conn.cursor()
    cur.execute("SELECT id, username, password, coins FROM users WHERE username=?", (username,))
    row = cur.fetchone()
    conn.close()
    if row:
        return User(row[0], row[1], row[2], row[3])
    return None


def get_user_by_id(user_id):
    conn = sqlite3.connect("users.db")
    cur = conn.cursor()
    cur.execute("SELECT id, username, password, coins FROM users WHERE id=?", (user_id,))
    row = cur.fetchone()
    conn.close()
    if row:
        return User(row[0], row[1], row[2], row[3])
    return None


@login_manager.user_loader
def load_user(user_id):
    return get_user_by_id(user_id)


# ==========================
# ログイン
# ==========================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        user = get_user_by_username(username)
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect("/games")

        return render_template_string("""
        <h2>ログイン失敗</h2>
        <a href="/login">戻る</a>
        """)

    return render_template_string("""
    <h2>ログイン</h2>
    <form method="POST">
        <input name="username" placeholder="ユーザー名"><br>
        <input name="password" type="password" placeholder="パスワード"><br>
        <button type="submit">ログイン</button>
    </form>
    <a href="/">トップへ</a>
    """)


@app.route("/logout")
def logout():
    logout_user()
    return redirect("/")


# ==========================
# YouTube 変換
# ==========================
def convert_youtube_url(url: str) -> str:
    base_mobile = "https://m.youtube.com/watch?v="
    base_pc = "https://www.youtube.com/watch?v="
    base_short = "https://youtu.be/"

    if url.startswith(base_short):
        return url
    if url.startswith(base_mobile):
        video_id = url[len(base_mobile):]
        return f"https://youtu.be/{video_id}"
    if url.startswith(base_pc):
        video_id = url[len(base_pc):]
        return f"https://youtu.be/{video_id}"

    raise ValueError("対応していないURL形式です")


@app.route("/")
def index():
    logged_in = current_user.is_authenticated
    login_button = """
    <button onclick="location.href='/login'">ログイン</button>
    """ if not logged_in else """
    <button onclick="location.href='/games'">ゲームへ</button>
    """

    return render_template_string(f"""
    <h1>YouTube URL 変換ツール</h1>
    {login_button}
    <input id="urlInput" placeholder="URLを入力">
    <button onclick="convert()">変換</button>
    <p id="status"></p>

    <script>
    async function convert() {{
        const url = document.getElementById("urlInput").value;
        const res = await fetch("/convert", {{
            method: "POST",
            headers: {{"Content-Type": "application/json"}},
            body: JSON.stringify({{url}})
        }});
        const data = await res.json();
        if (data.success) {{
            document.getElementById("status").innerText = data.converted;
        }} else {{
            document.getElementById("status").innerText = data.error;
        }}
    }}
    </script>
    """)


@app.route("/convert", methods=["POST"])
def convert():
    data = request.json
    url = data.get("url")

    try:
        result = convert_youtube_url(url)
        return jsonify({"success": True, "converted": result})
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400


# ==========================
# ゲーム一覧
# ==========================
@app.route("/games")
@login_required
def games():
    return render_template_string(f"""
    <h2>ゲーム一覧</h2>
    <p>{current_user.username} さん</p>
    <button onclick="location.href='/slot'">スロット</button>
    <button onclick="location.href='/highlow'">ハイロー</button>
    <button onclick="location.href='/mines'">マイン</button>
    <a href="/">変換ツールへ</a>
    <a href="/logout">ログアウト</a>
    """)


# ==========================
# スロット
# ==========================
@app.route("/slot")
@login_required
def slot():
    return render_template_string("""
    <h2>3×3 スロット</h2>
    <p>コイン: <span id="coins">読み込み中...</span></p>

    <input id="bet" type="number" value="10">
    <button onclick="spin()">回す</button>
    <button onclick="location.href='/games'">ゲーム一覧へ</button>

    <p id="result"></p>

    <script>
    async function spin() {{
        const bet = Number(document.getElementById("bet").value);
        const res = await fetch("/slot_spin", {{
            method: "POST",
            headers: {{"Content-Type": "application/json"}},
            body: JSON.stringify({{ bet }})
        }});
        const data = await res.json();
        document.getElementById("coins").innerText = data.coins;
        document.getElementById("result").innerText =
            data.multiplier === 0 ? "ハズレ…" : "当たり！ +" + data.win;
    }}

    fetch("/get_coins").then(r => r.json()).then(d => {{
        document.getElementById("coins").innerText = d.coins;
    }});
    </script>
    """)


@app.route("/slot_spin", methods=["POST"])
@login_required
def slot_spin():
    data = request.json
    bet = int(data.get("bet", 10))

    symbols = ["🍒", "🍋", "⭐", "💎", "7️⃣"]
    grid = [[random.choice(symbols) for _ in range(3)] for _ in range(3)]

    lines = [
        grid[0], grid[1], grid[2],
        [grid[0][0], grid[1][0], grid[2][0]],
        [grid[0][1], grid[1][1], grid[2][1]],
        [grid[0][2], grid[1][2], grid[2][2]],
        [grid[0][0], grid[1][1], grid[2][2]],
        [grid[0][2], grid[1][1], grid[0][0]],
    ]

    total_multiplier = 0
    for line in lines:
        if line[0] == line[1] == line[2]:
            total_multiplier += 5

    win = bet * total_multiplier

    conn = sqlite3.connect("users.db")
    cur = conn.cursor()
    cur.execute("SELECT coins FROM users WHERE id=?", (current_user.id,))
    coins = cur.fetchone()[0]

    coins = coins - bet + win

    cur.execute("UPDATE users SET coins=? WHERE id=?", (coins, current_user.id))
    conn.commit()
    conn.close()

    return jsonify({
        "win": win,
        "multiplier": total_multiplier,
        "coins": coins
    })


@app.route("/get_coins")
@login_required
def get_coins():
    conn = sqlite3.connect("users.db")
    cur = conn.cursor()
    cur.execute("SELECT coins FROM users WHERE id=?", (current_user.id,))
    coins = cur.fetchone()[0]
    conn.close()
    return jsonify({"coins": coins})


# ==========================
# ハイロー
# ==========================
def generate_card():
    value = random.randint(1, 13)
    suit = random.choice(["♠️", "♥️", "♦️", "♣️"])
    return value, suit


def calc_multiplier(current_value, choice):
    if choice == "high":
        prob = (13 - current_value) / 13
    else:
        prob = (current_value - 1) / 13

    if prob <= 0:
        return None

    return round(1 / prob, 3)


@app.route("/highlow")
@login_required
def highlow():
    value, suit = generate_card()

    return render_template_string(f"""
    <h2>High & Low</h2>
    <p>コイン: {current_user.coins}</p>

    <div style="font-size:50px;">{suit} {value}</div>

    <input id="bet" type="number" value="10">

    <button onclick="play('high', {value})">High</button>
    <button onclick="play('low', {value})">Low</button>
    <button onclick="location.href='/games'">ゲーム一覧へ</button>

    <script>
    async function play(choice, current_value) {{
        const bet = Number(document.getElementById("bet").value);

        const res = await fetch("/highlow_play", {{
            method: "POST",
            headers: {{"Content-Type": "application/json"}},
            body: JSON.stringify({{
                choice: choice,
                current_value: current_value,
                bet: bet
            }})
        }});

        const data = await res.json();
        document.body.innerHTML = data.html;
    }}
    </script>
    """)


@app.route("/highlow_play", methods=["POST"])
@login_required
def highlow_play():
    data = request.json
    choice = data["choice"]
    current_value = int(data["current_value"])
    bet = int(data["bet"])

    next_value, next_suit = generate_card()

    if next_value == current_value:
        html = f"""
        <h2>引き分け！</h2>
        <div style='font-size:50px;'>{next_suit} {next_value}</div>
        <button onclick="location.href='/highlow_continue?value={next_value}&suit={next_suit}&bet={bet}'">続ける</button>
        <button onclick="location.href='/games'">ゲーム一覧へ</button>
        """
        return jsonify({"html": html})

    win = (next_value > current_value) if choice == "high" else (next_value < current_value)
    multiplier = calc_multiplier(current_value, choice)

    conn = sqlite3.connect("users.db")
    cur = conn.cursor()
    cur.execute("SELECT coins FROM users WHERE id=?", (current_user.id,))
    coins = cur.fetchone()[0]

    if win:
        gain = int(bet * multiplier)
        coins += gain
        result_text = f"勝ち！ +{gain}（倍率 {multiplier}）"
    else:
        coins -= bet
        result_text = f"負け… -{bet}"

    cur.execute("UPDATE users SET coins=? WHERE id=?", (coins, current_user.id))
    conn.commit()
    conn.close()

    html = f"""
    <h2>{result_text}</h2>
    <div style='font-size:50px;'>{next_suit} {next_value}</div>
    <button onclick="location.href='/highlow_continue?value={next_value}&suit={next_suit}&bet={bet}'">続ける</button>
    <button onclick="location.href='/games'">ゲーム一覧へ</button>
    """

    return jsonify({"html": html})


@app.route("/highlow_continue")
@login_required
def highlow_continue():
    value = int(request.args.get("value"))
    suit = request.args.get("suit")
    bet = int(request.args.get("bet"))

    return render_template_string(f"""
    <h2>High & Low（続き）</h2>
    <p>コイン: {current_user.coins}</p>

    <div style="font-size:50px;">{suit} {value}</div>

    <input id="bet" type="number" value="{bet}">

    <button onclick="play('high', {value})">High</button>
    <button onclick="play('low', {value})">Low</button>
    <button onclick="location.href='/games'">ゲーム一覧へ</button>

    <script>
    async function play(choice, current_value) {{
        const bet = Number(document.getElementById("bet").value);

        const res = await fetch("/highlow_play", {{
            method: "POST",
            headers: {{"Content-Type": "application/json"}},
            body: JSON.stringify({{
                choice: choice,
                current_value: current_value,
                bet: bet
            }})
        }});

        const data = await res.json();
        document.body.innerHTML = data.html;
    }}
    </script>
    """)


# ==========================
# マイン（これから追加）
# ==========================
@app.route("/mines")
@login_required
def mines():
    return "マインはこれから追加するよ！"


# ==========================
# 起動
# ==========================
if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=10000, debug=True)
