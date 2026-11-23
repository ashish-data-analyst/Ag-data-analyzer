"""Login + SQLite database + demo timer + admin panel for AG Data Analyzer."""
import base64
import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import time
from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st

DB_PATH = os.environ.get("AGDA_DB", "agda_users.db")
FOREVER = "9999-12-31 00:00:00"
DEFAULT_LI = "https://www.linkedin.com/in/ashish-kumar-700278417"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, email TEXT UNIQUE, phone TEXT,
  salt TEXT, pw_hash TEXT, role TEXT DEFAULT 'user', created_at TEXT, last_login TEXT,
  used_seconds REAL DEFAULT 0, trial_minutes REAL, access_until TEXT, plan TEXT);
CREATE TABLE IF NOT EXISTS requests(
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, message TEXT, created_at TEXT, status TEXT DEFAULT 'new');
CREATE TABLE IF NOT EXISTS feedback(
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, rating INTEGER, text TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS payments(
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, utr TEXT, amount TEXT, created_at TEXT,
  status TEXT DEFAULT 'pending', confirmed_at TEXT, notified INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS resets(
  id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT, created_at TEXT, status TEXT DEFAULT 'new');
"""


# ---------------------------------------------------------------- basics
def _ts(days=0):
    t = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=days)
    return t.strftime("%Y-%m-%d %H:%M:%S")


def _cfg(key, default=""):
    try:
        return st.secrets[key] if key in st.secrets else default
    except Exception:
        return default


def q(sql, args=(), write=False):
    con = sqlite3.connect(DB_PATH, timeout=15)
    con.row_factory = sqlite3.Row
    try:
        cur = con.execute(sql, args)
        if write:
            con.commit()
            return cur.lastrowid
        return [dict(r) for r in cur.fetchall()]
    finally:
        con.close()


def get_setting(key):
    r = q("SELECT value FROM settings WHERE key=?", (key,))
    return r[0]["value"] if r else ""


def set_setting(key, value):
    q("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (key, str(value)), write=True)


def _hash(pw, salt=None):
    salt = salt or secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 200_000).hex()
    return salt, h


def _verify(pw, user):
    return hmac.compare_digest(_hash(pw, user["salt"])[1], user["pw_hash"])


@st.cache_resource
def init_db(admin_sig=("", "")):
    # admin_sig is part of the cache key, so changing the secrets re-creates the admin account
    con = sqlite3.connect(DB_PATH)
    con.executescript(SCHEMA)
    con.commit()
    try:
        con.execute("ALTER TABLE users ADD COLUMN must_change INTEGER DEFAULT 0")
        con.commit()
    except sqlite3.OperationalError:
        pass  # column already exists
    con.close()
    q("INSERT OR IGNORE INTO settings VALUES('demo_minutes','10')", write=True)
    q("INSERT OR IGNORE INTO settings VALUES('price_text',?)",
      ("💳 Full access is a paid subscription. I will share the price and payment details when you contact me.",),
      write=True)
    em, pw = admin_sig[0].strip().lower(), admin_sig[1]
    if em and pw:
        salt, h = _hash(pw)
        if q("SELECT id FROM users WHERE email=?", (em,)):
            q("UPDATE users SET salt=?,pw_hash=?,role='admin' WHERE email=?", (salt, h, em), write=True)
        else:
            q("INSERT INTO users(name,email,salt,pw_hash,role,created_at) VALUES('Admin',?,?,?,'admin',?)",
              (em, salt, h, _ts()), write=True)


def current_user():
    uid = st.session_state.get("uid")
    if not uid:
        return None
    r = q("SELECT * FROM users WHERE id=?", (uid,))
    return r[0] if r else None


# ---------------------------------------------------------------- access / timer
def access_status(u):
    if u["role"] == "admin":
        return dict(allowed=True, kind="admin")
    if u["access_until"] and u["access_until"] > _ts():
        return dict(allowed=True, kind="full", until=u["access_until"])
    limit = float(u["trial_minutes"] if u["trial_minutes"] is not None else get_setting("demo_minutes")) * 60
    left = limit - float(u["used_seconds"] or 0)
    return dict(allowed=left > 0, kind="demo", left=max(left, 0), limit=limit)


def tick(u):
    """Add the time since the last tick to the user's demo usage (max 30 s per tick)."""
    now, last = time.time(), st.session_state.get("last_tick")
    st.session_state["last_tick"] = now
    if u["role"] == "admin" or (u["access_until"] and u["access_until"] > _ts()):
        return
    if last:
        q("UPDATE users SET used_seconds=used_seconds+? WHERE id=?", (min(now - last, 30), u["id"]), write=True)


def gate(light_css):
    """Login wall. Returns (user, status) only for logged-in users who still have access."""
    init_db((str(_cfg("ADMIN_EMAIL")), str(_cfg("ADMIN_PASSWORD"))))
    u = current_user()
    if not u:
        light_css()
        login_screen()
        st.stop()
    tick(u)
    u = current_user()
    if u is None:
        st.session_state.clear()
        st.rerun()
    if u.get("must_change"):
        light_css()
        force_change_screen(u)
        st.stop()
    s = access_status(u)
    if not s["allowed"]:
        light_css()
        locked_screen(u)
        st.stop()
    for p in q("SELECT id FROM payments WHERE user_id=? AND status='confirmed' AND notified=0", (u["id"],)):
        q("UPDATE payments SET notified=1 WHERE id=?", (p["id"],), write=True)
        msg = "Payment confirmed! Your full access is now active. Thank you 🙏"
        st.toast(msg, icon="🎉")
        st.success("✅ " + msg)
    return u, s


# ---------------------------------------------------------------- screens
def login_screen():
    mins = get_setting("demo_minutes")
    c = st.columns([1, 1.5, 1])[1]
    with c:
        st.markdown(
            f'<div class="hero" style="padding:26px 30px"><div class="eyebrow">AG DATA ANALYZER</div>'
            f'<h1 style="font-size:28px">Welcome 👋</h1>'
            f'<p>Log in or sign up to start your free {mins}-minute demo.</p></div>', unsafe_allow_html=True)
        if not _cfg("ADMIN_EMAIL"):
            st.warning("Admin is not configured. Create this file with ADMIN_EMAIL and ADMIN_PASSWORD, then restart the app: "
                       + os.path.join(os.getcwd(), ".streamlit", "secrets.toml"))
        t_in, t_up, t_fp = st.tabs(["Log in", "Sign up", "Forgot password"])

        with t_in:
            with st.form("login"):
                em = st.text_input("Email")
                pw = st.text_input("Password", type="password")
                ok = st.form_submit_button("Log in", width="stretch")
            if ok:
                if st.session_state.get("tries", 0) >= 5:
                    st.error("Too many wrong attempts. Please try again later.")
                else:
                    r = q("SELECT * FROM users WHERE email=?", (em.strip().lower(),))
                    if r and _verify(pw, r[0]):
                        q("UPDATE users SET last_login=? WHERE id=?", (_ts(), r[0]["id"]), write=True)
                        st.session_state.update(uid=r[0]["id"], last_tick=None, tries=0)
                        st.rerun()
                    st.session_state["tries"] = st.session_state.get("tries", 0) + 1
                    st.error("Invalid email or password.")

        with t_up:
            with st.form("signup"):
                name = st.text_input("Full name")
                email = st.text_input("Email ")
                phone = st.text_input("Phone (optional)")
                p1 = st.text_input("Password (min 8 characters)", type="password")
                p2 = st.text_input("Confirm password", type="password")
                agree = st.checkbox("I agree that my name, email and phone are stored to give me access. "
                                    "My uploaded files are not saved to any database.")
                ok = st.form_submit_button("Create account", width="stretch")
            if ok:
                email = email.strip().lower()
                if not name.strip() or not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
                    st.error("Please enter your name and a valid email.")
                elif len(p1) < 8 or p1 != p2:
                    st.error("Password must be at least 8 characters and both passwords must match.")
                elif not agree:
                    st.error("Please accept the consent box to continue.")
                else:
                    salt, h = _hash(p1)
                    try:
                        uid = q("INSERT INTO users(name,email,phone,salt,pw_hash,created_at,last_login) "
                                "VALUES(?,?,?,?,?,?,?)", (name.strip(), email, phone.strip(), salt, h, _ts(), _ts()),
                                write=True)
                        st.session_state.update(uid=uid, last_tick=None)
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("This email is already registered. Please log in.")

        with t_fp:
            st.write("Enter your registered email. I will be notified and will send you a temporary password.")
            with st.form("forgot"):
                fe = st.text_input("Registered email", key="fp_email")
                ok = st.form_submit_button("Request password reset", width="stretch")
            if ok:
                em = fe.strip().lower()
                if em and q("SELECT id FROM users WHERE email=?", (em,)) \
                        and not q("SELECT id FROM resets WHERE email=? AND status='new'", (em,)):
                    q("INSERT INTO resets(email,created_at) VALUES(?,?)", (em, _ts()), write=True)
                st.success("If this email is registered, your request has been sent. "
                           "You can also message me on LinkedIn to get the temporary password faster.")
            st.link_button("💬 Open LinkedIn", _cfg("LINKEDIN_URL", DEFAULT_LI), width="stretch")


def qr_bytes():
    b = get_setting("qr_b64")
    return base64.b64decode(b) if b else None


def _extend(cur, days):
    """New expiry = days added on top of the current expiry (or now)."""
    if cur and cur.startswith("9999"):
        return cur
    base = max(cur or "", _ts())
    t = datetime.strptime(base, "%Y-%m-%d %H:%M:%S") + timedelta(days=int(days))
    return t.strftime("%Y-%m-%d %H:%M:%S")


def pay_ui(u):
    """'Pay now' button -> QR code -> user submits the transaction ID."""
    pend = q("SELECT * FROM payments WHERE user_id=? AND status='pending' ORDER BY id DESC", (u["id"],))
    if pend:
        st.info(f"⏳ Your payment (ID {pend[0]['utr']}) is waiting for confirmation. "
                "You will get a confirmation message here as soon as it is verified.")
        if st.button("🔄 Check payment status"):
            st.rerun()
        return
    if st.button("💳 Pay now"):
        st.session_state["show_qr"] = True
    if st.session_state.get("show_qr"):
        img = qr_bytes()
        if not img:
            st.warning("Payment QR is not available right now. Please contact me on LinkedIn.")
            return
        c1, c2 = st.columns([1, 1.4])
        c1.image(img, width=260, caption="Scan with any UPI app")
        with c2:
            with st.form("payform"):
                st.write("After paying, enter the transaction details:")
                utr = st.text_input("UTR / Transaction ID")
                amt = st.text_input("Amount paid (₹)")
                ok = st.form_submit_button("✅ I have paid", width="stretch")
            if ok:
                utr = utr.strip()
                if len(utr) < 6 or not amt.strip():
                    st.error("Please enter the transaction ID and the amount.")
                elif q("SELECT id FROM payments WHERE lower(utr)=?", (utr.lower(),)):
                    st.error("This transaction ID has already been submitted.")
                else:
                    q("INSERT INTO payments(user_id,utr,amount,created_at) VALUES(?,?,?,?)",
                      (u["id"], utr, amt.strip(), _ts()), write=True)
                    st.session_state["show_qr"] = False
                    st.rerun()


def access_request_ui(u):
    s = access_status(u)
    if s["kind"] == "admin":
        st.info("You are the admin, so you have unlimited access.")
        return
    if s["kind"] == "full":
        till = "lifetime" if s["until"].startswith("9999") else s["until"][:10]
        st.success(f"✅ You already have full access (valid till {till}).")
        return
    st.info(get_setting("price_text"))
    has_req = q("SELECT id FROM requests WHERE user_id=? AND status='new'", (u["id"],))
    pay_open = has_req or q("SELECT id FROM payments WHERE user_id=? AND status IN ('pending','rejected')", (u["id"],))
    if not pay_open:
        msg = (f"Hi Ashish, I'm {u['name']} ({u['email']}). I tried AG Data Analyzer and I would like full access. "
               f"Please share the subscription plan and payment details.")
        st.markdown("#### Step 1 · Send your access request")
        st.write("Copy this message and send it to me on LinkedIn, then press the button below.")
        st.code(msg, language=None)
        st.link_button("💬 Open LinkedIn", _cfg("LINKEDIN_URL", DEFAULT_LI), width="stretch")
        if st.button("📩 Send access request", width="stretch"):
            q("INSERT INTO requests(user_id,message,created_at) VALUES(?,?,?)", (u["id"], msg, _ts()), write=True)
            st.rerun()
    else:
        st.success("📩 Your request has been sent. Now complete your payment below.")
        if not q("SELECT id FROM payments WHERE user_id=? AND status='pending'", (u["id"],)) and \
                q("SELECT id FROM payments WHERE user_id=? AND status='rejected'", (u["id"],)):
            st.warning("Your last payment could not be verified. Please check the transaction ID and try again.")
        st.markdown("#### Step 2 · Pay and get access")
        pay_ui(u)

def locked_screen(u):
    c = st.columns([1, 2, 1])[1]
    with c:
        st.markdown("## ⏱️ Your free demo has ended")
        st.write("Thanks for trying AG Data Analyzer! To continue with full access, contact me using the steps below.")
        access_request_ui(u)
        st.divider()
        if st.button("Log out"):
            st.session_state.clear()
            st.rerun()


def change_password_form(u, forced=False):
    with st.form("chpw"):
        old = "" if forced else st.text_input("Current password", type="password")
        n1 = st.text_input("New password (min 8 characters)", type="password")
        n2 = st.text_input("Confirm new password", type="password")
        ok = st.form_submit_button("Update password", width="stretch")
    if ok:
        if not forced and not _verify(old, u):
            st.error("Current password is wrong.")
        elif len(n1) < 8 or n1 != n2:
            st.error("New password must be at least 8 characters and both entries must match.")
        else:
            salt, h = _hash(n1)
            q("UPDATE users SET salt=?,pw_hash=?,must_change=0 WHERE id=?", (salt, h, u["id"]), write=True)
            st.success("Password updated ✅")
            if forced:
                st.rerun()


def force_change_screen(u):
    c = st.columns([1, 1.5, 1])[1]
    with c:
        st.markdown("## 🔑 Set a new password")
        st.write("You logged in with a temporary password. Please choose your own password to continue.")
        change_password_form(u, forced=True)
        if st.button("Log out"):
            st.session_state.clear()
            st.rerun()


def account_page(u):
    s = access_status(u)
    st.markdown(f"**Name:** {u['name']}  \n**Email:** {u['email']}  \n**Phone:** {u['phone'] or '-'}  \n"
                f"**Joined (UTC):** {(u['created_at'] or '')[:10]}")
    if s["kind"] == "full":
        till = "lifetime" if s["until"].startswith("9999") else s["until"][:10]
        st.success(f"✅ Full access, valid till {till}")
    elif s["kind"] == "demo":
        st.info(f"⏱️ Demo: {int(s['left'] // 60)} min left")
    st.markdown("#### Change password")
    if u["role"] == "admin":
        st.info("The admin password is set in your Streamlit secrets (ADMIN_PASSWORD).")
    else:
        change_password_form(u)


def feedback_page(u):
    st.write("Tell me what worked and what you want next. It goes straight to the app owner.")
    with st.form("fb"):
        rating = st.select_slider("Rating", options=[1, 2, 3, 4, 5], value=5)
        text = st.text_area("Your feedback or feature request")
        ok = st.form_submit_button("Send feedback")
    if ok and text.strip():
        q("INSERT INTO feedback(user_id,rating,text,created_at) VALUES(?,?,?,?)",
          (u["id"], rating, text.strip(), _ts()), write=True)
        st.success("Thank you! Feedback received 🙏")


# ---------------------------------------------------------------- sidebar account box
@st.fragment(run_every=10)
def _timer(uid):
    u = q("SELECT * FROM users WHERE id=?", (uid,))[0]
    tick(u)
    u = q("SELECT * FROM users WHERE id=?", (uid,))[0]
    s = access_status(u)
    if not s["allowed"]:
        st.rerun()
    if s["kind"] == "demo":
        m, sec = divmod(int(s["left"]), 60)
        st.progress(min(max(s["left"] / s["limit"], 0.0), 1.0))
        st.markdown(f"⏱️ Demo time left: **{m:02d}:{sec:02d}**")
    elif s["kind"] == "full":
        st.markdown("✅ Full access active")
    else:
        st.markdown("👑 Admin")


def account_box(u):
    st.markdown('<div class="side-label">👤 ACCOUNT</div>', unsafe_allow_html=True)
    st.markdown(f"**{u['name']}**  \n{u['email']}")
    _timer(u["id"])
    if st.button("Log out", width="stretch"):
        st.session_state.clear()
        st.rerun()


# ---------------------------------------------------------------- admin
def admin_panel():
    rows = q("SELECT id,name,email,phone,created_at,last_login,ROUND(used_seconds/60.0,1) AS used_min,"
             "trial_minutes,access_until,plan FROM users WHERE role!='admin' ORDER BY id DESC")
    users = pd.DataFrame(rows)
    reqs = q("SELECT r.id,u.name,u.email,u.phone,r.created_at,r.status FROM requests r "
             "JOIN users u ON u.id=r.user_id ORDER BY r.id DESC")
    now = _ts()
    full = sum(1 for r in rows if r["access_until"] and r["access_until"] > now)
    a, b, c, d = st.columns(4)
    a.metric("Total users", len(rows))
    b.metric("Full-access users", full)
    c.metric("New access requests", sum(1 for r in reqs if r["status"] == "new"))
    d.metric("Pending payments", q("SELECT COUNT(*) AS n FROM payments WHERE status='pending'")[0]["n"])
    st.caption("All times are UTC (IST = UTC + 5:30).")

    t1, t6, t2, t3, t4, t7, t5, t8, t9 = st.tabs(["Users", "Payments", "Grant access", "Requests", "Feedback",
                                              "Payment QR", "Settings", "🗑️ Delete", "🔑 Password resets"])
    with t1:
        if users.empty:
            st.info("No users yet.")
        else:
            st.dataframe(users, width="stretch", hide_index=True)
            st.download_button("⬇️ Download users CSV", users.to_csv(index=False).encode("utf-8-sig"),
                               "ag_users.csv", "text/csv")
    with t2:
        if not rows:
            st.info("No users yet.")
        else:
            opts = {f"{r['name']} · {r['email']}": r for r in rows}
            who = opts[st.selectbox("User", list(opts))]
            action = st.radio("Action", ["Grant full access (days)", "Grant lifetime access",
                                         "Add demo minutes", "Reset demo usage", "Revoke full access"])
            days = mins = 0
            plan = ""
            if action.startswith("Grant full"):
                days = st.number_input("Days", 1, 3650, 30)
            if action.startswith("Grant"):
                plan = st.text_input("Plan / note (e.g. Monthly, paid via UPI)")
            if action == "Add demo minutes":
                mins = st.number_input("Extra minutes", 1, 600, 10)
            if st.button("Apply"):
                uid = who["id"]
                if action.startswith("Grant full"):
                    q("UPDATE users SET access_until=?,plan=? WHERE id=?", (_ts(days), plan, uid), write=True)
                elif action == "Grant lifetime access":
                    q("UPDATE users SET access_until=?,plan=? WHERE id=?", (FOREVER, plan, uid), write=True)
                elif action == "Add demo minutes":
                    cur = who["trial_minutes"] if who["trial_minutes"] is not None else float(get_setting("demo_minutes"))
                    q("UPDATE users SET trial_minutes=? WHERE id=?", (cur + mins, uid), write=True)
                elif action == "Reset demo usage":
                    q("UPDATE users SET used_seconds=0 WHERE id=?", (uid,), write=True)
                else:
                    q("UPDATE users SET access_until=NULL WHERE id=?", (uid,), write=True)
                q("UPDATE requests SET status='done' WHERE user_id=?", (uid,), write=True)
                st.success("Done ✅")
                st.rerun()
    with t3:
        if reqs:
            st.dataframe(pd.DataFrame(reqs), width="stretch", hide_index=True)
            if st.button("Mark all as done"):
                q("UPDATE requests SET status='done'", write=True)
                st.rerun()
        else:
            st.info("No requests yet.")
    with t4:
        fb = q("SELECT f.created_at,u.name,u.email,f.rating,f.text FROM feedback f "
               "JOIN users u ON u.id=f.user_id ORDER BY f.id DESC")
        if fb:
            st.metric("Average rating", f"{sum(r['rating'] for r in fb) / len(fb):.1f} / 5")
            st.dataframe(pd.DataFrame(fb), width="stretch", hide_index=True)
        else:
            st.info("No feedback yet.")
    with t5:
        st.markdown("##### Default demo time for every new user")
        dm = st.number_input("Demo minutes", 1, 600, int(float(get_setting("demo_minutes"))))
        pt = st.text_area("Pricing / subscription message shown to users", get_setting("price_text"))
        if st.button("Save settings"):
            set_setting("demo_minutes", dm)
            set_setting("price_text", pt)
            st.success("Saved ✅")
        st.divider()
        st.warning("On Streamlit Community Cloud the database file can be reset when the app restarts. "
                   "Download a backup regularly.")
        with open(DB_PATH, "rb") as f:
            st.download_button("⬇️ Backup database (.db)", f.read(), "agda_users_backup.db")

    with t6:
        pays = q("SELECT p.id,u.name,u.email,u.phone,p.utr,p.amount,p.created_at,p.status,p.confirmed_at,p.user_id "
                 "FROM payments p JOIN users u ON u.id=p.user_id ORDER BY p.id DESC")
        if not pays:
            st.info("No payments yet.")
        else:
            st.dataframe(pd.DataFrame(pays).drop(columns=["user_id"]), width="stretch", hide_index=True)
            pend = [p for p in pays if p["status"] == "pending"]
            if pend:
                st.markdown("##### Confirm or reject a pending payment")
                st.caption("First check the UTR and amount in your bank / UPI app.")
                lab = {f"#{p['id']} · {p['name']} · ₹{p['amount']} · UTR {p['utr']}": p for p in pend}
                p = lab[st.selectbox("Pending payment", list(lab))]
                life = st.checkbox("Lifetime access")
                days = st.number_input("Access days", 1, 3650, 30, disabled=life)
                b1, b2 = st.columns(2)
                if b1.button("✅ Confirm payment and activate access", width="stretch"):
                    cur = q("SELECT access_until FROM users WHERE id=?", (p["user_id"],))[0]["access_until"]
                    until = FOREVER if life else _extend(cur, days)
                    q("UPDATE users SET access_until=?,plan=? WHERE id=?",
                      (until, f"Paid Rs {p['amount']} UTR {p['utr']}", p["user_id"]), write=True)
                    q("UPDATE payments SET status='confirmed',confirmed_at=?,notified=0 WHERE id=?",
                      (_ts(), p["id"]), write=True)
                    q("UPDATE requests SET status='done' WHERE user_id=?", (p["user_id"],), write=True)
                    st.rerun()
                if b2.button("❌ Reject", width="stretch"):
                    q("UPDATE payments SET status='rejected' WHERE id=?", (p["id"],), write=True)
                    st.rerun()

    with t7:
        cur = qr_bytes()
        if cur:
            st.image(cur, width=260, caption="Current payment QR (users see this)")
        up = st.file_uploader("Upload your UPI QR code (PNG / JPG)", type=["png", "jpg", "jpeg"])
        if up and st.button("Save QR"):
            data = up.getvalue()
            if len(data) > 1_500_000:
                st.error("Image is too large (max 1.5 MB).")
            else:
                set_setting("qr_b64", base64.b64encode(data).decode())
                st.rerun()
        if cur and st.button("🗑️ Delete QR"):
            set_setting("qr_b64", "")
            st.rerun()

    with t8:
        st.warning("Deleting is permanent. Download a database backup first (Settings tab).")
        singles = {
            "A user (with all their data)": ("users", "SELECT id, name || ' · ' || email AS l FROM users WHERE role!='admin'"),
            "A payment record": ("payments", "SELECT id, '#' || id || ' · UTR ' || utr || ' · Rs ' || amount AS l FROM payments"),
            "A request": ("requests", "SELECT id, '#' || id || ' · ' || created_at AS l FROM requests"),
            "A feedback entry": ("feedback", "SELECT id, '#' || id || ' · ' || substr(text,1,40) AS l FROM feedback"),
        }
        bulk = {"ALL feedback": "feedback", "ALL requests": "requests", "ALL payments": "payments",
                "ALL password resets": "resets"}
        what = st.selectbox("What do you want to delete?", list(singles) + list(bulk))
        sure = st.checkbox("Yes, delete permanently")
        if what in singles:
            table, sql = singles[what]
            items = q(sql)
            if not items:
                st.info("Nothing to delete.")
            else:
                pick = st.selectbox("Select", [i["l"] for i in items])
                rid = next(i["id"] for i in items if i["l"] == pick)
                if st.button("🗑️ Delete", disabled=not sure):
                    if table == "users":
                        for t in ("payments", "requests", "feedback"):
                            q(f"DELETE FROM {t} WHERE user_id=?", (rid,), write=True)
                    q(f"DELETE FROM {table} WHERE id=?", (rid,), write=True)
                    st.rerun()
        elif st.button(f"🗑️ Delete {what}", disabled=not sure):
            q(f"DELETE FROM {bulk[what]}", write=True)
            st.rerun()

    with t9:
        rs = q("SELECT r.id,r.email,r.created_at,r.status,u.name,u.phone,u.id AS uid FROM resets r "
               "LEFT JOIN users u ON u.email=r.email ORDER BY r.id DESC")
        if not rs:
            st.info("No password reset requests.")
        else:
            st.dataframe(pd.DataFrame(rs).drop(columns=["uid"]), width="stretch", hide_index=True)
            new = [r for r in rs if r["status"] == "new" and r["uid"]]
            if new:
                lab = {f"#{r['id']} · {r['name']} · {r['email']}": r for r in new}
                r = lab[st.selectbox("Reset request", list(lab))]
                st.caption("Verify the person first (LinkedIn / phone), then share the temporary password with them.")
                if st.button("🔑 Generate temporary password"):
                    tmp = secrets.token_urlsafe(6)
                    salt, h = _hash(tmp)
                    q("UPDATE users SET salt=?,pw_hash=?,must_change=1 WHERE id=?", (salt, h, r["uid"]), write=True)
                    q("UPDATE resets SET status='done' WHERE id=?", (r["id"],), write=True)
                    st.session_state["tmp_pw"] = (r["email"], tmp)
                    st.rerun()
        if st.session_state.get("tmp_pw"):
            em, tmp = st.session_state["tmp_pw"]
            st.success(f"Temporary password for {em} (shown only now):")
            st.code(tmp, language=None)
            if st.button("Hide"):
                st.session_state.pop("tmp_pw")
                st.rerun()
