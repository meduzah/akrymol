import sqlite3

def clear_users():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # Delete all users
    c.execute('DELETE FROM users')
    
    # Get number of deleted users
    deleted_count = c.rowcount
    
    conn.commit()
    conn.close()
    
    print(f"Usunięto {deleted_count} kont użytkowników.")

if __name__ == '__main__':
    clear_users() 