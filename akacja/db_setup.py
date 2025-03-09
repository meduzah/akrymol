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
            surname TEXT NOT NULL,
            experience_pm TEXT NOT NULL,
            experience_pm_it TEXT NOT NULL,
            continent TEXT NOT NULL,
            country TEXT NOT NULL,
            region TEXT NOT NULL,
            travel_ready BOOLEAN NOT NULL,
            level_seniority TEXT NOT NULL,
            field_of_study TEXT NOT NULL,
            technical_ed TEXT,
            language_levels TEXT NOT NULL,
            methodologies TEXT NOT NULL,
            tools TEXT NOT NULL,
            certificates TEXT NOT NULL,
            additional_info TEXT NOT NULL,
            stacjonarnie BOOLEAN NOT NULL,
            remote_on_site TEXT NOT NULL,
            username TEXT NOT NULL
        )
    ''')
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                email TEXT NOT NULL,
                password TEXT NOT NULL
              )
        ''')

    # Zatwierdzenie zmian i zamknięcie połączenia
    conn.commit()
    conn.close()
    print("Baza danych została utworzona!")

if __name__ == '__main__':
    create_database()
