import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "analytics.db")

def print_separator(title=""):
    print("\n" + "=" * 25 + f" {title} " + "=" * 25)

def show_database():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print_separator("SQLITE DATABASE ARCHITECTURE: analytics.db")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    tables = [t[0] for t in cursor.fetchall()]
    print(f"Total Registered Tables: {len(tables)}")
    for t in tables:
        cursor.execute(f"PRAGMA table_info({t});")
        cols = cursor.fetchall()
        col_names = [f"{c[1]} ({c[2]})" for c in cols]
        cursor.execute(f"SELECT COUNT(*) FROM {t};")
        count = cursor.fetchone()[0]
        print(f"  • {t.upper():<20} | Rows: {count:<4} | Schema: {', '.join(col_names[:4])}...")

    # 1. Message Logs (OmniChat)
    print_separator("TABLE 1: message_logs (OmniChat Inbound & Latency)")
    cursor.execute("SELECT id, user_message, detected_language, response_time_ms, timestamp FROM message_logs ORDER BY id DESC LIMIT 8;")
    rows = cursor.fetchall()
    print(f"{'ID':<4} | {'Lang':<5} | {'Latency':<9} | {'Time (UTC)':<19} | {'User Message'}")
    print("-" * 75)
    for r in rows:
        msg = r[1].replace("\n", " ")
        if len(msg) > 35:
            msg = msg[:32] + "..."
        print(f"{r[0]:<4} | {r[2]:<5} | {r[3]:<7.1f}ms | {str(r[4])[:19]:<19} | \"{msg}\"")

    # 2. Call Logs (Voicera Voice Sessions)
    print_separator("TABLE 2: call_logs (Voicera Full-Duplex Voice Sessions)")
    cursor.execute("SELECT id, duration_seconds, detected_language, turn_count, timestamp FROM call_logs ORDER BY id DESC LIMIT 5;")
    crows = cursor.fetchall()
    print(f"{'ID':<4} | {'Duration':<10} | {'Lang':<5} | {'Turns':<6} | {'Timestamp'}")
    print("-" * 60)
    for r in crows:
        print(f"{r[0]:<4} | {r[1]:<7} sec | {r[2]:<5} | {r[3]:<6} | {str(r[4])[:19]}")

    # 3. Lead Records (CRM Capture)
    print_separator("TABLE 3: lead_records (Autonomous Voice & Chat CRM Ingestion)")
    cursor.execute("SELECT id, caller_name, contact, category, source, timestamp FROM lead_records ORDER BY id DESC LIMIT 5;")
    lrows = cursor.fetchall()
    print(f"{'ID':<4} | {'Caller Name':<16} | {'Contact':<14} | {'Category':<16} | {'Source'}")
    print("-" * 70)
    for r in lrows:
        print(f"{r[0]:<4} | {r[1]:<16} | {r[2]:<14} | {r[3]:<16} | {r[4]}")

    # 4. Memory Snippets (Memory Vault)
    print_separator("TABLE 4: memory_snippets (AutoForm Profile Knowledge Base)")
    cursor.execute("SELECT id, category, title, content FROM memory_snippets ORDER BY id DESC LIMIT 5;")
    mrows = cursor.fetchall()
    if mrows:
        for r in mrows:
            print(f"ID {r[0]} | Category: {r[1]} | Title: {r[2]} | Content: {r[3][:40]}...")
    else:
        print("Table initialized and active (Populates automatically when documents are ingested in /autoform).")

    conn.close()
    print("\n" + "=" * 65 + "\n")

if __name__ == "__main__":
    show_database()
