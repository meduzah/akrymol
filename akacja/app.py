from flask import Flask, render_template, request, redirect, url_for, send_from_directory
import sqlite3
import os

app = Flask(__name__)
global logged_user
logged_user = None

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
    return render_template('index.html', total_pm=total_pm, ready_to_travel=ready_to_travel, logged_in=(logged_user is not None))


# -------------------------------------------------
# Login
# -------------------------------------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    global logged_user
    if logged_user is None:
        if request.method == 'POST':
            conn = sqlite3.connect('database.db')
            c = conn.cursor()
            username = request.form.get('username')
            password = request.form.get('password')
            c.execute('SELECT username, password FROM users WHERE username = ?', (username,))
            user = c.fetchone()
            if user is not None and password == user[1]:
                logged_local_user = user[0]
            else:
                return redirect(url_for('login'))

            logged_user = logged_local_user

            return redirect(url_for('search'))
        return render_template('login.html', logged_in=False)
    else:
        return redirect(url_for('search'))

# -------------------------------------------------
# Rejestracja
# -------------------------------------------------

@app.route('/register', methods=['GET', 'POST'])
def register():
    if logged_user is None:
        if request.method == 'POST':
            username = request.form.get('username')
            email = request.form.get('email')
            password = request.form.get('password')

            conn = sqlite3.connect('database.db')
            c = conn.cursor()
            c.execute('SELECT id FROM users WHERE username = ?', (username,))
            user_existing = c.fetchone()
            if user_existing is not None:
                return redirect(url_for('register'))

            c.execute(f'''
                INSERT INTO users (
                    username,
                    email,
                    password
                ) VALUES (?, ?, ?)
            ''', (username, email, password))
            conn.commit()
            conn.close()
            return redirect(url_for('login'))

        return render_template('register.html', logged_in=False)
    else:
        return redirect(url_for('search'))

# -------------------------------------------------
# Wyloguj
# -------------------------------------------------

@app.route('/logout')
def logout():
    global logged_user
    if logged_user is not None:
        logged_user = None
    return redirect(url_for('home'))

# -------------------------------------------------
# Wyświetlanie listy PM-ów
# -------------------------------------------------

@app.route('/add-pm', methods=['GET', 'POST'])
def add_pm():
    if logged_user is not None:
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

            os.makedirs('./cv_files', exist_ok=True)
            cv_file = request.files['cv_file']

            # -------------------------------
            # 2. Zapis do bazy (INSERT)
            # -------------------------------
            conn = sqlite3.connect('database.db')
            c = conn.cursor()

            cur = c.execute("""
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
                    remote_on_site,
                    username
                )
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
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
                remote_on_site,             # 'Remote'/'On-site'/'Hybrid',
                logged_user
            ))

            conn.commit()
            cv_file.save(os.path.join('cv_files', 'cv_' + str(cur.lastrowid) + '.' + cv_file.filename.split('.')[-1]))
            conn.close()

            return redirect(url_for('search'))

        # Metoda GET: wyświetlamy sam formularz
        return render_template('add_pm.html', logged_in=(logged_user is not None))
    else:
        return redirect(url_for('login'))

# -------------------------------------------------
# Usuwanie PM-a
# -------------------------------------------------

@app.route('/pm/<int:pm_id>')
def pm_details(pm_id):
    if logged_user is not None:
        conn = sqlite3.connect('database.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM project_managers WHERE id = ?', (pm_id,))
        pm = c.fetchone()
        conn.close()

        if pm is None:
            return "Nie znaleziono takiego Project Managera!", 404

        pm = dict(pm)
        pm_id = pm['id']
        cv_files = os.listdir('./cv_files')
        for i in range(len(cv_files)):
            cv_files[i] = cv_files[i].split('.')[0]
        if 'cv_' + str(pm_id) in cv_files:
            pm['cv_file'] = os.path.join('./cv_files', f'cv_{pm_id}')

        return render_template('pm_details.html', pm=pm, logged_in=(logged_user is not None))
    else:
        return redirect(url_for('login'))

@app.route('/download_file/<int:pm_id>')
def download_file(pm_id):
    if logged_user is not None:
        cv_files = os.listdir('./cv_files')
        for cv_file in cv_files:
            if f'cv_{pm_id}' == cv_file.split('.')[0]:
                correct_cv_file = cv_file
        return send_from_directory('cv_files', correct_cv_file, as_attachment=True)
    else:
        abort(404)

@app.route('/delete-pm/<int:pm_id>', methods=['POST'])
def delete_pm(pm_id):
    if logged_user is not None:
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute('DELETE FROM project_managers WHERE id = ?', (pm_id,))
        conn.commit()
        conn.close()
        return redirect(url_for('pm_list'))
    else:
        return redirect(url_for('login'))

# -------------------------------------------------
# Edycja istniejącego PM-a (przykład: prosta edycja
# np. name, surname, travel_ready, etc.)
# -------------------------------------------------
@app.route('/edit-pm/<int:pm_id>', methods=['GET', 'POST'])
def edit_pm(pm_id):
    if logged_user is not None:
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
        return render_template('edit_pm.html', pm=pm, logged_in=(logged_user is not None))
    else:
        return redirect(url_for('login'))

# -------------------------------------------------
# Wyszukiwanie
# -------------------------------------------------
@app.route('/search', methods=['GET'])
def search():
    if logged_user is not None:
        location = request.args.get('location', '').strip()
        level_seniority = request.args.get('level_seniority', '').strip()
        travel_ready = request.args.get('travel_ready', '').strip()
        remote_on_site = request.args.get('remote_on_site', '').strip()
        tools = request.args.get('tools', '').strip()
        methodologies = request.args.get('methodologies', '').strip()
        languages = request.args.get('languages', '').strip()

        query = 'SELECT * FROM project_managers WHERE username=?'
        print(logged_user)
        params = [logged_user]

        additional_conditions = []

        if location:
            additional_conditions.append('(country LIKE ? OR region LIKE ?)')
            params.extend([f'%{location}%', f'%{location}%'])

        if level_seniority:
            additional_conditions.append('level_seniority = ?')
            params.append(level_seniority)

        if travel_ready:
            additional_conditions.append('travel_ready = ?')
            params.append(travel_ready)

        if remote_on_site:
            additional_conditions.append('remote_on_site = ?')
            params.append(remote_on_site)

        if tools:
            additional_conditions.append('tools LIKE ?')
            params.append(f'%{tools}%')

        if methodologies:
            additional_conditions.append('methodologies LIKE ?')
            params.append(f'%{methodologies}%')

        if languages:
            additional_conditions.append('languages LIKE ?')
            params.append(f'%{languages}%')

        if additional_conditions:
            query += ' AND ' + ' AND '.join(additional_conditions)

        print("SQL Query:", query)
        print("Parameters:", params)

        conn = sqlite3.connect('database.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute(query, params)
        results = c.fetchall()
        conn.close()

        return render_template('search.html', results=results, logged_in=(logged_user is not None))
    else:
        return redirect(url_for('login'))


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
