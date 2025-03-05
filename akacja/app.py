from flask import Flask, render_template, request, redirect, url_for
import sqlite3

app = Flask(__name__)

# -------------------------------------------------
# Strona główna
# -------------------------------------------------
@app.route('/')
def home():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    c.execute('SELECT COUNT(*) FROM project_managers')
    total_pm = c.fetchone()[0]

    c.execute('SELECT COUNT(*) FROM project_managers WHERE travel_ready = 1')
    ready_to_travel = c.fetchone()[0]

    conn.close()
    return render_template('index.html', total_pm=total_pm, ready_to_travel=ready_to_travel)

# -------------------------------------------------
# Wyświetlanie listy PM-ów
# -------------------------------------------------
@app.route('/pm-list')
def pm_list():
    conn = sqlite3.connect('database.db')
    # (opcjonalnie) umożliwiamy dostęp po nazwach kolumn:
    conn.row_factory = sqlite3.Row

    c = conn.cursor()
    c.execute('SELECT * FROM project_managers')
    pm_rows = c.fetchall()
    conn.close()

    return render_template('pm_list.html', pm_rows=pm_rows)

# -------------------------------------------------
# Dodawanie nowego PM-a
# -------------------------------------------------
@app.route('/add-pm', methods=['GET', 'POST'])
def add_pm():
    if request.method == 'POST':
        # -------------------------------
        # 1. Pobranie danych z formularza
        # -------------------------------
        name = request.form.get('name')
        surname = request.form.get('surname')

        # Suwaki "Doświadczenie jako PM" / "Doświadczenie jako PM w IT"
        experience_pm = request.form.get('experience_pm', 0)
        experience_pm_it = request.form.get('experience_pm_it', 0)

        continent = request.form.get('continent')
        country   = request.form.get('country')
        region    = request.form.get('region')

        # Checkbox gotowości do zmiany miejsca zamieszkania
        travel_ready = 'travel_ready' in request.form

        level_seniority  = request.form.get('level_seniority')
        field_of_study   = request.form.get('field_of_study')
        technical_ed     = request.form.get('technical_ed')  # 'tak'/'nie' radio
        # Języki (dynamiczne) => name="language[]" i nazwy poziomów => name="level[]"
        languages = request.form.getlist('language[]')  # lista np. ['Polski','Angielski']
        levels    = request.form.getlist('level[]')     # np. ['C2','B2']
        # Łączymy pary w jednego stringa, np. "Polski(C2);Angielski(B2)"
        lang_level_pairs = []
        for lang, lvl in zip(languages, levels):
            if lang or lvl:  # w razie gdyby user coś nie wypełnił
                lang_level_pairs.append(f"{lang}({lvl})")
        language_levels = ";".join(lang_level_pairs)

        # Checkboxy metodologie / narzędzia
        methodologies = request.form.getlist('methodologies')  # np. ["Scrum","Kanban"]
        tools         = request.form.getlist('tools')          # np. ["Jira","Trello"]

        # Pola tekstowe: certyfikaty, dodatkowe info
        certificates     = request.form.get('certificates')
        additional_info  = request.form.get('additional_info')

        # "Możliwość pracy wyłącznie stacjonarnie"
        stacjonarnie = 'stacjonarnie' in request.form

        # Preferowany tryb pracy
        remote_on_site = request.form.get('remote_on_site')

        # -------------------------------
        # 2. Zapis do bazy (INSERT)
        # -------------------------------
        conn = sqlite3.connect('database.db')
        c = conn.cursor()

        c.execute("""
            INSERT INTO project_managers (
                name,
                surname,
                experience_pm,
                experience_pm_it,
                continent,
                country,
                region,
                travel_ready,
                level_seniority,
                field_of_study,
                technical_ed,
                language_levels,
                methodologies,
                tools,
                certificates,
                additional_info,
                stacjonarnie,
                remote_on_site
            )
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            name,
            surname,
            experience_pm,
            experience_pm_it,
            continent,
            country,
            region,
            1 if travel_ready else 0,
            level_seniority,
            field_of_study,
            technical_ed,
            language_levels,            # powstały łańcuch z par "Język(poziom)"
            ",".join(methodologies),    # łańcuch np. "Scrum,Kanban"
            ",".join(tools),           # łańcuch np. "Jira,Trello"
            certificates,
            additional_info,
            1 if stacjonarnie else 0,  # checkbox
            remote_on_site             # 'Remote'/'On-site'/'Hybrid'
        ))

        conn.commit()
        conn.close()

        return redirect(url_for('pm_list'))

    # Metoda GET: wyświetlamy sam formularz
    return render_template('add_pm.html')

# -------------------------------------------------
# Usuwanie PM-a
# -------------------------------------------------
@app.route('/delete-pm/<int:pm_id>', methods=['POST'])
def delete_pm(pm_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('DELETE FROM project_managers WHERE id = ?', (pm_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('pm_list'))

# -------------------------------------------------
# Edycja istniejącego PM-a (przykład: prosta edycja
# np. name, surname, travel_ready, etc.)
# -------------------------------------------------
@app.route('/edit-pm/<int:pm_id>', methods=['GET', 'POST'])
def edit_pm(pm_id):
    if request.method == 'POST':
        name = request.form.get('name')
        surname = request.form.get('surname')
        travel_ready = ('travel_ready' in request.form)

        # i ewentualnie odczyt innych pól

        conn = sqlite3.connect('database.db')
        c = conn.cursor()

        # Prosty UPDATE wybranych kolumn:
        c.execute('''
            UPDATE project_managers
            SET
                name = ?,
                surname = ?,
                travel_ready = ?
            WHERE id = ?
        ''', (
            name,
            surname,
            1 if travel_ready else 0,
            pm_id
        ))

        conn.commit()
        conn.close()
        return redirect(url_for('pm_list'))

    # GET: pobieramy dane PM-a
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT * FROM project_managers WHERE id = ?', (pm_id,))
    pm = c.fetchone()
    conn.close()
    return render_template('edit_pm.html', pm=pm)

# -------------------------------------------------
# Wyszukiwanie
# -------------------------------------------------
@app.route('/search', methods=['GET'])
def search():
    location = request.args.get('location', '')
    experience = request.args.get('experience', '')

    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    query = 'SELECT * FROM project_managers WHERE 1=1'
    params = []

    if location:
        query += ' AND province LIKE ?'
        params.append(f'%{location}%')

    if experience:
        query += ' AND experience_pm LIKE ?'
        params.append(f'%{experience}%')

    c.execute(query, params)
    results = c.fetchall()
    conn.close()

    return render_template('search.html', results=results)

# -------------------------------------------------
# Obsługa błędu 404
# -------------------------------------------------
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

# -------------------------------------------------
# Uruchomienie aplikacji
# -------------------------------------------------
if __name__ == '__main__':
    app.run(debug=True)
