import sqlite3

def create_database():
    # lacze sie z baza danych tutaj
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    # tworze tabele dla pmów
    c.execute('''
        CREATE TABLE IF NOT EXISTS project_managers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            experience TEXT NOT NULL,
            location TEXT NOT NULL,
            travel_ready BOOLEAN NOT NULL
        )
    ''')

    # Zatwierdzenie zmian i zamknięcie połączenia
    conn.commit()
    conn.close()
    print("Baza danych została utworzona!")

if __name__ == '__main__':
    create_database()
