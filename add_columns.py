import sqlite3

def add_columns():
    print("Dodawanie kolumn email i phone do tabeli project_managers...")
    
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    # Sprawdzenie czy kolumny już istnieją
    cursor.execute("PRAGMA table_info(project_managers)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'email' not in columns:
        print("Dodawanie kolumny 'email'...")
        cursor.execute("ALTER TABLE project_managers ADD COLUMN email TEXT")
    else:
        print("Kolumna 'email' już istnieje.")
    
    if 'phone' not in columns:
        print("Dodawanie kolumny 'phone'...")
        cursor.execute("ALTER TABLE project_managers ADD COLUMN phone TEXT")
    else:
        print("Kolumna 'phone' już istnieje.")
    
    conn.commit()
    conn.close()
    print("Operacja zakończona pomyślnie.")

if __name__ == "__main__":
    add_columns() 