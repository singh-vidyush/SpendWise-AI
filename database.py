import sqlite3
import hashlib

DB_NAME = "spendwise_users.db"


# -------------------------
# DATABASE CONNECTION
# -------------------------

def get_connection():
    return sqlite3.connect(DB_NAME)


# -------------------------
# CREATE TABLE
# -------------------------

def create_table():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )
    """)

    conn.commit()
    conn.close()


# -------------------------
# HASH PASSWORD
# -------------------------

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def verify_user(email, password):

    user = get_user_by_email(email)

    if not user:
        return None

    stored_hash = user[3]

    if stored_hash == hash_password(password):
        return user

    return None


# -------------------------
# ADD USER
# -------------------------

def add_user(username, email, password):
    conn = get_connection()
    cursor = conn.cursor()

    hashed_password = hash_password(password)

    try:
        cursor.execute("""
        INSERT INTO users (username, email, password)
        VALUES (?, ?, ?)
        """, (username, email, hashed_password))

        conn.commit()

        user_id = cursor.lastrowid

        conn.close()

        return user_id

    except sqlite3.IntegrityError:
        conn.close()
        return None


# -------------------------
# GET USER BY ID
# -------------------------

def get_user_by_id(user_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT *
    FROM users
    WHERE user_id = ?
    """, (user_id,))

    user = cursor.fetchone()

    conn.close()

    return user


# -------------------------
# GET USER NAME
# -------------------------

def get_user_name(user_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT username
    FROM users
    WHERE user_id = ?
    """, (user_id,))

    result = cursor.fetchone()

    conn.close()

    return result[0] if result else None


# -------------------------
# GET USER ID USING EMAIL
# -------------------------

def get_user_id(email):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT user_id
    FROM users
    WHERE email = ?
    """, (email,))

    result = cursor.fetchone()

    conn.close()

    return result[0] if result else None


# -------------------------
# GET USER BY EMAIL
# -------------------------

def get_user_by_email(email):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT *
    FROM users
    WHERE email = ?
    """, (email,))

    user = cursor.fetchone()

    conn.close()

    return user


# -------------------------
# INITIALIZE DATABASE
# -------------------------

create_table()