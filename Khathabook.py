import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import matplotlib.pyplot as plt
import hashlib

# ------------------ DATABASE SETUP ------------------
conn = sqlite3.connect("khatabook.db", check_same_thread=False)
c = conn.cursor()

# Users table
c.execute('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password_hash TEXT
)
''')

# Transactions table
c.execute('''
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    date TEXT,
    category TEXT,
    description TEXT,
    type TEXT,
    amount REAL,
    FOREIGN KEY(user_id) REFERENCES users(id)
)
''')
conn.commit()

# ------------------ FUNCTIONS ------------------
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def register_user(username, password):
    try:
        c.execute("INSERT INTO users (username, password_hash) VALUES (?,?)", (username, hash_password(password)))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False

def login_user(username, password):
    c.execute("SELECT * FROM users WHERE username=? AND password_hash=?", (username, hash_password(password)))
    return c.fetchone()

def get_transactions(user_id):
    df = pd.read_sql_query("SELECT * FROM transactions WHERE user_id=?", conn, params=(user_id,))
    return df

def add_transactions(user_id, df):
    for _, row in df.iterrows():
        c.execute('''INSERT INTO transactions (user_id,date,category,description,type,amount)
                     VALUES (?,?,?,?,?,?)''',
                  (user_id, row["Date"], row["Category"], row["Description"], row["Type"], row["Amount"]))
    conn.commit()

# ------------------ STREAMLIT UI ------------------
st.set_page_config(page_title="Khatabook - MultiUser Expense Tracker", layout="centered")
st.title("💰 Khatabook - Multi-User Expense Tracker")

# --- AUTHENTICATION ---
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

auth_choice = st.sidebar.selectbox("Login/Register", ["Login", "Register"])

if auth_choice == "Register":
    st.sidebar.subheader("Create Account")
    username = st.sidebar.text_input("Username")
    password = st.sidebar.text_input("Password", type="password")
    if st.sidebar.button("Register"):
        if register_user(username, password):
            st.sidebar.success("Account created! Please login.")
        else:
            st.sidebar.error("Username already exists.")
else:
    st.sidebar.subheader("Login")
    username = st.sidebar.text_input("Username", key="login_user")
    password = st.sidebar.text_input("Password", type="password", key="login_pass")
    if st.sidebar.button("Login"):
        user = login_user(username, password)
        if user:
            st.session_state["logged_in"] = True
            st.session_state["user_id"] = user[0]
            st.success(f"Welcome, {username}!")
        else:
            st.error("Invalid username or password")

# --- MAIN APP ---
if st.session_state.get("logged_in"):

    user_id = st.session_state["user_id"]

    # --- Add Multiple Transactions ---
    st.subheader("➕ Add Transactions")

    categories = ["Food", "Travel", "Rent", "Shopping", "Salary", "Other"]
    template_df = pd.DataFrame({
        "Category": [categories[0]],
        "Description": [""],
        "Type": ["Expense"],
        "Amount": [0.0]
    })

    edited_df = st.data_editor(
        template_df,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Category": st.column_config.SelectboxColumn("Category", options=categories),
            "Type": st.column_config.SelectboxColumn("Type", options=["Expense", "Income"])
        }
    )

    if st.button("💾 Save Transactions"):
        edited_df = edited_df[edited_df["Description"] != ""]
        if not edited_df.empty:
            edited_df["Date"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            add_transactions(user_id, edited_df)
            st.success(f"{len(edited_df)} transaction(s) saved!")

    # --- Show Summary ---
    df = get_transactions(user_id)
    if not df.empty:
        income = df[df["type"]=="Income"]["amount"].sum()
        expense = df[df["type"]=="Expense"]["amount"].sum()
        balance = income - expense

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Income", f"₹{income:.2f}", delta_color="normal")
        col2.metric("Total Expense", f"₹{expense:.2f}", delta_color="inverse")
        col3.metric("Balance", f"₹{balance:.2f}")

        st.subheader("📜 Transactions")
        st.dataframe(df[["date","category","description","type","amount"]], use_container_width=True)

        # --- Charts ---
        st.subheader("📈 Charts")

        # Pie: Income vs Expense
        totals = df.groupby("type")["amount"].sum()
        if not totals.empty:
            fig1, ax1 = plt.subplots()
            ax1.pie(totals, labels=totals.index, autopct='%1.1f%%', startangle=90)
            ax1.set_title("Income vs Expense")
            st.pyplot(fig1)

        # Bar: Expenses by Category
        st.markdown("#### Expenses by Category")
        expense_df = df[df["type"]=="Expense"]
        if not expense_df.empty:
            grouped = expense_df.groupby("category")["amount"].sum()
            st.bar_chart(grouped)

        # Line: Expense trend over time
        st.markdown("#### Expense Trend Over Time")
        df_sorted = df.copy()
        df_sorted["date"] = pd.to_datetime(df_sorted["date"])
        daily_expense = df_sorted[df_sorted["type"]=="Expense"].groupby("date")["amount"].sum()
        if not daily_expense.empty:
            st.line_chart(daily_expense)

        # Download CSV
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="⬇️ Download Transactions (CSV)",
            data=csv,
            file_name="transactions.csv",
            mime="text/csv"
        )
    else:
        st.info("No transactions yet. Add some above!")
