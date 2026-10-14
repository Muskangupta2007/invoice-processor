"""
InvoSync Password Reset Utility
Run this script to reset all passwords back to defaults.
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "invoices.db")

print(f"\n[InvoSync] Connecting to database: {DB_PATH}")

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Show current values
print("\n--- Current Settings ---")
cursor.execute("SELECT key, value FROM settings WHERE key IN ('admin_username', 'admin_password', 'settings_password')")
rows = cursor.fetchall()
for row in rows:
    val = row['value']
    # Mask hashed passwords
    if val and (val.startswith("scrypt:") or val.startswith("pbkdf2:") or val.startswith("sha256$")):
        val = "[HASHED PASSWORD]"
    print(f"  {row['key']} = {val}")

print("\n--- Resetting to defaults ---")
cursor.execute("UPDATE settings SET value = 'admin' WHERE key = 'admin_username'")
cursor.execute("UPDATE settings SET value = 'invosync2026' WHERE key = 'admin_password'")
cursor.execute("UPDATE settings SET value = 'settings2026' WHERE key = 'settings_password'")
conn.commit()
conn.close()

print("\n[SUCCESS] Passwords reset successfully!")
print("\nNew credentials:")
print("  Username        : admin")
print("  Password        : invosync2026")
print("  Settings Lock   : settings2026")
print("\nRestart the server and log in with the above credentials.\n")
