from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash, session
from flask_mail import Mail
import sqlite3
import os
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from config import Config
from security import (validate_password, validate_email, generate_verification_token,
                      generate_2fa_code, send_verification_email, send_2fa_code,
                      check_login_attempts, update_login_attempts)

# Load the .env file
load_dotenv()

# Debug prints to check email configuration
print("Email settings:")
print(f"MAIL_USERNAME: {os.environ.get('MAIL_USERNAME')}")
print(f"MAIL_PASSWORD: {os.environ.get('MAIL_PASSWORD')} exists: {bool(os.environ.get('MAIL_PASSWORD'))}")

app = Flask(__name__)
app.config.from_object(Config)

# Initialize Flask-Mail with debug prints
mail = Mail(app)
print("Flask-Mail Configuration:")
print(f"MAIL_SERVER: {app.config['MAIL_SERVER']}")
print(f"MAIL_PORT: {app.config['MAIL_PORT']}")
print(f"MAIL_USE_TLS: {app.config['MAIL_USE_TLS']}")
print(f"MAIL_USERNAME: {app.config['MAIL_USERNAME']}")
print(f"MAIL_PASSWORD exists: {bool(app.config['MAIL_PASSWORD'])}")

# -------------------------------------------------
# Strona główna
# -------------------------------------------------
@app.route('/')
def home():
    conn = sqlite3.connect(app.config['DATABASE_PATH'])
    c = conn.cursor()

    c.execute('SELECT COUNT(*) FROM project_managers')
    total_pm = c.fetchone()[0]

    c.execute('SELECT COUNT(*) FROM project_managers WHERE travel_ready = 1')
    ready_to_travel = c.fetchone()[0]

    conn.close()
    return render_template('index.html', 
                         total_pm=total_pm, 
                         ready_to_travel=ready_to_travel, 
                         logged_in=('user_id' in session))

# -------------------------------------------------
# Rejestracja
# -------------------------------------------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('search'))

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        # Walidacja danych
        if not all([username, email, password, confirm_password]):
            flash('Wszystkie pola są wymagane', 'error')
            return render_template('register.html')

        if password != confirm_password:
            flash('Hasła nie są identyczne', 'error')
            return render_template('register.html')

        # Walidacja hasła
        is_valid, error_msg = validate_password(password)
        if not is_valid:
            flash(error_msg, 'error')
            return render_template('register.html')

        # Walidacja email
        is_valid, error_msg = validate_email(email)
        if not is_valid:
            flash(error_msg, 'error')
            return render_template('register.html')

        conn = sqlite3.connect(app.config['DATABASE_PATH'])
        c = conn.cursor()

        # Sprawdzenie czy użytkownik/email już istnieje
        c.execute('SELECT id FROM users WHERE username = ? OR email = ?', (username, email))
        if c.fetchone() is not None:
            conn.close()
            flash('Użytkownik lub email już istnieje', 'error')
            return render_template('register.html')

        # Generowanie tokenu weryfikacyjnego
        token, token_expires = generate_verification_token()

        # Zapis do bazy
        try:
            c.execute('''
                INSERT INTO users (
                    username, email, password, 
                    verification_token, verification_token_expires
                ) VALUES (?, ?, ?, ?, ?)
            ''', (
                username,
                email,
                generate_password_hash(password),
                token,
                token_expires.isoformat()
            ))
            conn.commit()

            # Wysłanie emaila weryfikacyjnego
            send_verification_email(mail, email, token)

            flash('Rejestracja wstępna udana! Sprawdź swoją skrzynkę email (w tym folder SPAM) i kliknij w link aktywacyjny, aby potwierdzić konto.', 'success')
            return redirect(url_for('login'))

        except Exception as e:
            conn.rollback()
            flash('Wystąpił błąd podczas rejestracji. Spróbuj ponownie.', 'error')
            return render_template('register.html')

        finally:
            conn.close()

    return render_template('register.html')

# -------------------------------------------------
# Weryfikacja email
# -------------------------------------------------
@app.route('/verify/<token>')
def verify_email(token):
    conn = sqlite3.connect(app.config['DATABASE_PATH'])
    c = conn.cursor()
    
    # Sprawdzenie tokenu
    c.execute('''
        SELECT id, verification_token_expires 
        FROM users 
        WHERE verification_token = ? AND is_verified = 0
    ''', (token,))
    
    user = c.fetchone()
    
    if user is None:
        flash('Nieprawidłowy lub wykorzystany token weryfikacyjny', 'error')
        return redirect(url_for('login'))
    
    # Sprawdzenie czy token nie wygasł
    expires = datetime.fromisoformat(user[1])
    if datetime.now() > expires:
        flash('Token weryfikacyjny wygasł. Zarejestruj się ponownie.', 'error')
        return redirect(url_for('register'))
    
    # Aktywacja konta
    c.execute('''
        UPDATE users 
        SET is_verified = 1,
            verification_token = NULL,
            verification_token_expires = NULL
        WHERE id = ?
    ''', (user[0],))
    
    conn.commit()
    conn.close()
    
    flash('Konto zostało pomyślnie aktywowane! Możesz się teraz zalogować.', 'success')
    return redirect(url_for('login'))

# -------------------------------------------------
# Login
# -------------------------------------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('home'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            flash('Wprowadź nazwę użytkownika i hasło', 'error')
            return render_template('login.html')

        conn = sqlite3.connect(app.config['DATABASE_PATH'])
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        # Pobierz dane użytkownika
        c.execute('''
            SELECT id, username, email, password, is_verified, 
                   failed_login_attempts, account_locked_until 
            FROM users 
            WHERE username = ?
        ''', (username,))
        user = c.fetchone()

        if user is None:
            flash('Nieprawidłowa nazwa użytkownika lub hasło', 'error')
            return render_template('login.html')

        # Sprawdź czy konto jest zweryfikowane
        if not user['is_verified']:
            flash('Konto nie zostało jeszcze aktywowane. Sprawdź swoją skrzynkę email.', 'error')
            return render_template('login.html')

        # Sprawdź czy konto nie jest zablokowane
        is_allowed, error_msg = check_login_attempts(user)
        if not is_allowed:
            flash(error_msg, 'error')
            return render_template('login.html')

        # Sprawdź hasło
        if not check_password_hash(user['password'], password):
            update_login_attempts(conn, username, False)
            flash('Nieprawidłowa nazwa użytkownika lub hasło', 'error')
            return render_template('login.html')

        # Zaloguj użytkownika
        update_login_attempts(conn, username, True)
        session['user_id'] = user['id']
        session['username'] = user['username']
        conn.close()

        flash('Zalogowano pomyślnie!', 'success')
        return redirect(url_for('home'))

    return render_template('login.html')

# -------------------------------------------------
# Wyloguj
# -------------------------------------------------
@app.route('/logout')
def logout():
    session.clear()
    flash('Wylogowano pomyślnie', 'success')
    return redirect(url_for('home'))

# -------------------------------------------------
# Wyświetlanie listy PM-ów
# -------------------------------------------------

@app.route('/add-pm', methods=['GET', 'POST'])
def add_pm():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        # -------------------------------
        # 1. Pobranie danych z formularza
        # -------------------------------
        name = request.form.get('name')
        surname = request.form.get('surname')

        # Suwaki "Doświadczenie jako PM" / "Doświadczenie jako PM w IT"
        experience_pm = int(request.form.get('experience_pm', 0))
        experience_pm_it = int(request.form.get('experience_pm_it', 0))

        # Walidacja: doświadczenie PM w IT nie może być większe niż ogólne doświadczenie PM
        if experience_pm_it > experience_pm:
            return render_template('add_pm.html', 
                                error="Doświadczenie jako PM w IT nie może być większe niż całkowite doświadczenie jako PM", 
                                logged_in=True)

        continent = request.form.get('continent')
        country = request.form.get('country')
        region = request.form.get('region')

        # Walidacja kraju dla Antarktydy
        if continent == "Antarktyda" and not country:
            country = "Brak państw"
        elif not country and continent != "Antarktyda":
            return render_template('add_pm.html',
                                error="Proszę wybrać kraj",
                                logged_in=True)

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

        # Pobierz email i telefon
        email = request.form.get('email')
        phone = request.form.get('phone')
        
        os.makedirs('./cv_files', exist_ok=True)
        cv_file = request.files['cv_file']

        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        cur = c.execute("""
            INSERT INTO project_managers (
                name,
                surname,
                email,
                phone,
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
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            name,
            surname,
            email,
            phone,
            experience_pm,
            experience_pm_it,
            continent,
            country,
            region,
            1 if travel_ready else 0,
            level_seniority,
            field_of_study,
            technical_ed,
            language_levels,
            ",".join(methodologies),
            ",".join(tools),
            certificates,
            additional_info,
            1 if stacjonarnie else 0,
            remote_on_site,
            session.get('username')
        ))

        conn.commit()
        cv_file.save(os.path.join('cv_files', 'cv_' + str(cur.lastrowid) + '.' + cv_file.filename.split('.')[-1]))
        conn.close()

        return redirect(url_for('search'))

    # Metoda GET: wyświetlamy sam formularz
    return render_template('add_pm.html', logged_in=True)

# -------------------------------------------------
# Usuwanie PM-a
# -------------------------------------------------

@app.route('/pm/<int:pm_id>')
def pm_details(pm_id):
    if 'user_id' in session:
        conn = sqlite3.connect('database.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # Dodajemy sprawdzenie czy PM należy do zalogowanego użytkownika
        c.execute('SELECT * FROM project_managers WHERE id = ? AND username = ?', (pm_id, session.get('username')))
        pm = c.fetchone()
        conn.close()

        if pm is None:
            return render_template('error.html', 
                                error_message="Nie znaleziono takiego Project Managera lub nie masz uprawnień do jego wyświetlenia",
                                logged_in=True)

        pm = dict(pm)
        pm_id = pm['id']
        
        # Sprawdzanie czy CV istnieje
        cv_exists = False
        cv_extension = None
        cv_files = os.listdir('./cv_files')
        for file in cv_files:
            if file.startswith(f'cv_{pm_id}.'):
                cv_exists = True
                cv_extension = file.split('.')[-1]
                break
                
        if cv_exists:
            pm['cv_file'] = {
                'exists': True,
                'extension': cv_extension
            }
        else:
            pm['cv_file'] = {
                'exists': False
            }

        return render_template('pm_details.html', pm=pm, logged_in=True)
    else:
        return redirect(url_for('login'))

@app.route('/download_file/<int:pm_id>')
def download_file(pm_id):
    if 'user_id' in session:
        # Sprawdź czy plik istnieje
        cv_files = os.listdir('./cv_files')
        cv_file = None
        for file in cv_files:
            if file.startswith(f'cv_{pm_id}.'):
                cv_file = file
                break
                
        if cv_file:
            return send_from_directory('cv_files', cv_file, as_attachment=True)
        else:
            flash('Plik CV nie został dołączony dla tego Project Managera.', 'error')
            return redirect(url_for('pm_details', pm_id=pm_id))
    else:
        return redirect(url_for('login'))

@app.route('/delete-pm/<int:pm_id>', methods=['POST'])
def delete_pm(pm_id):
    if 'user_id' in session:
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        
        # Najpierw sprawdzamy czy PM istnieje i należy do zalogowanego użytkownika
        c.execute('SELECT id FROM project_managers WHERE id = ? AND username = ?', (pm_id, session.get('username')))
        pm = c.fetchone()
        
        if pm is None:
            conn.close()
            return render_template('error.html', 
                                error_message="Nie znaleziono takiego Project Managera lub nie masz uprawnień do jego usunięcia",
                                logged_in=True)
            
        # Usuwamy plik CV jeśli istnieje
        cv_files = os.listdir('./cv_files')
        for cv_file in cv_files:
            if f'cv_{pm_id}' == cv_file.split('.')[0]:
                os.remove(os.path.join('./cv_files', cv_file))
                
        # Usuwamy PM-a z bazy
        c.execute('DELETE FROM project_managers WHERE id = ? AND username = ?', (pm_id, session.get('username')))
        conn.commit()
        conn.close()
        return redirect(url_for('search'))
    else:
        return redirect(url_for('login'))

# -------------------------------------------------
# Edycja istniejącego PM-a
# -------------------------------------------------
@app.route('/edit-pm/<int:pm_id>', methods=['GET', 'POST'])
def edit_pm(pm_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Sprawdzamy czy PM istnieje i należy do zalogowanego użytkownika
    c.execute('SELECT * FROM project_managers WHERE id = ? AND username = ?', 
              (pm_id, session.get('username')))
    pm = c.fetchone()

    if pm is None:
        conn.close()
        return render_template('error.html',
                            error_message="Nie znaleziono takiego Project Managera lub nie masz uprawnień do jego edycji",
                            logged_in=True)

    if request.method == 'POST':
        # Pobranie danych z formularza
        name = request.form.get('name')
        surname = request.form.get('surname')
        email = request.form.get('email')
        phone = request.form.get('phone')
        experience_pm = int(request.form.get('experience_pm', 0))
        experience_pm_it = int(request.form.get('experience_pm_it', 0))
        
        # Walidacja: doświadczenie PM w IT nie może być większe niż ogólne doświadczenie PM
        if experience_pm_it > experience_pm:
            return render_template('edit_pm.html',
                                error="Doświadczenie jako PM w IT nie może być większe niż całkowite doświadczenie jako PM",
                                pm=pm,
                                logged_in=True)

        continent = request.form.get('continent')
        country = request.form.get('country')
        region = request.form.get('region')

        # Walidacja kraju dla Antarktydy
        if continent == "Antarktyda" and not country:
            country = "Brak państw"
        elif not country and continent != "Antarktyda":
            return render_template('edit_pm.html',
                                error="Proszę wybrać kraj",
                                pm=pm,
                                logged_in=True)

        # Pozostałe pola
        travel_ready = 'travel_ready' in request.form
        level_seniority = request.form.get('level_seniority')
        field_of_study = request.form.get('field_of_study')
        technical_ed = request.form.get('technical_ed')

        # Języki
        languages = request.form.getlist('language[]')
        levels = request.form.getlist('level[]')
        lang_level_pairs = []
        for lang, lvl in zip(languages, levels):
            if lang and lvl:
                lang_level_pairs.append(f"{lang}({lvl})")
        language_levels = ";".join(lang_level_pairs)

        # Metodologie i narzędzia
        methodologies = request.form.getlist('methodologies')
        tools = request.form.getlist('tools')

        # Dodatkowe informacje
        certificates = request.form.get('certificates')
        additional_info = request.form.get('additional_info')
        stacjonarnie = 'stacjonarnie' in request.form
        remote_on_site = request.form.get('remote_on_site')

        # Aktualizacja w bazie danych
        c.execute("""
            UPDATE project_managers
            SET name = ?,
                surname = ?,
                email = ?,
                phone = ?,
                experience_pm = ?,
                experience_pm_it = ?,
                continent = ?,
                country = ?,
                region = ?,
                travel_ready = ?,
                level_seniority = ?,
                field_of_study = ?,
                technical_ed = ?,
                language_levels = ?,
                methodologies = ?,
                tools = ?,
                certificates = ?,
                additional_info = ?,
                stacjonarnie = ?,
                remote_on_site = ?
            WHERE id = ? AND username = ?
        """, (
            name, surname, email, phone, experience_pm, experience_pm_it,
            continent, country, region,
            1 if travel_ready else 0,
            level_seniority, field_of_study, technical_ed,
            language_levels,
            ",".join(methodologies),
            ",".join(tools),
            certificates, additional_info,
            1 if stacjonarnie else 0,
            remote_on_site,
            pm_id, session.get('username')
        ))

        # Obsługa pliku CV
        if 'cv_file' in request.files and request.files['cv_file'].filename:
            cv_file = request.files['cv_file']
            # Usuń stary plik CV jeśli istnieje
            cv_files = os.listdir('./cv_files')
            for file in cv_files:
                if file.startswith(f'cv_{pm_id}.'):
                    os.remove(os.path.join('./cv_files', file))
            # Zapisz nowy plik CV
            cv_file.save(os.path.join('cv_files', f'cv_{pm_id}.{cv_file.filename.split(".")[-1]}'))

        conn.commit()
        conn.close()
        return redirect(url_for('pm_details', pm_id=pm_id))

    # GET: wyświetl formularz z wypełnionymi danymi
    return render_template('edit_pm.html', pm=pm, logged_in=True)

# -------------------------------------------------
# Wyszukiwanie
# -------------------------------------------------
@app.route('/search', methods=['GET'])
def search():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # Pobieranie wszystkich parametrów wyszukiwania
    name = request.args.get('name', '').strip()
    surname = request.args.get('surname', '').strip()
    email = request.args.get('email', '').strip()
    phone = request.args.get('phone', '').strip()
    
    experience_pm_min = request.args.get('experience_pm_min', '').strip()
    experience_pm_max = request.args.get('experience_pm_max', '').strip()
    experience_pm_it_min = request.args.get('experience_pm_it_min', '').strip()
    experience_pm_it_max = request.args.get('experience_pm_it_max', '').strip()
    
    level_seniority = request.args.get('level_seniority', '').strip()
    location = request.args.get('location', '').strip()
    continent = request.args.get('continent', '').strip()
    travel_ready = request.args.get('travel_ready', '').strip()
    
    remote_on_site = request.args.get('remote_on_site', '').strip()
    stacjonarnie = request.args.get('stacjonarnie', '').strip()
    technical_ed = request.args.get('technical_ed', '').strip()
    field_of_study = request.args.get('field_of_study', '').strip()
    
    tools = request.args.get('tools', '').strip()
    methodologies = request.args.get('methodologies', '').strip()
    languages = request.args.get('languages', '').strip()
    certificates = request.args.get('certificates', '').strip()
    additional_info = request.args.get('additional_info', '').strip()

    query = 'SELECT * FROM project_managers WHERE username = ?'
    params = [session.get('username')]

    additional_conditions = []

    # Dane osobowe
    if name:
        additional_conditions.append('name LIKE ?')
        params.append(f'%{name}%')
        
    if surname:
        additional_conditions.append('surname LIKE ?')
        params.append(f'%{surname}%')
        
    if email:
        additional_conditions.append('email LIKE ?')
        params.append(f'%{email}%')
        
    if phone:
        additional_conditions.append('phone LIKE ?')
        params.append(f'%{phone}%')
        
    # Doświadczenie
    if experience_pm_min:
        additional_conditions.append('experience_pm >= ?')
        params.append(int(experience_pm_min))
        
    if experience_pm_max:
        additional_conditions.append('experience_pm <= ?')
        params.append(int(experience_pm_max))
        
    if experience_pm_it_min:
        additional_conditions.append('experience_pm_it >= ?')
        params.append(int(experience_pm_it_min))
        
    if experience_pm_it_max:
        additional_conditions.append('experience_pm_it <= ?')
        params.append(int(experience_pm_it_max))

    # Lokalizacja
    if location:
        additional_conditions.append('(country LIKE ? OR region LIKE ?)')
        params.extend([f'%{location}%', f'%{location}%'])
        
    if continent:
        additional_conditions.append('continent LIKE ?')
        params.append(f'%{continent}%')

    # Poziom i preferencje pracy
    if level_seniority:
        additional_conditions.append('level_seniority = ?')
        params.append(level_seniority)

    if travel_ready:
        additional_conditions.append('travel_ready = ?')
        params.append(int(travel_ready))

    if remote_on_site:
        additional_conditions.append('remote_on_site = ?')
        params.append(remote_on_site)
        
    if stacjonarnie:
        additional_conditions.append('stacjonarnie = ?')
        params.append(int(stacjonarnie))

    # Wykształcenie
    if technical_ed:
        additional_conditions.append('technical_ed = ?')
        params.append(technical_ed)
        
    if field_of_study:
        additional_conditions.append('field_of_study LIKE ?')
        params.append(f'%{field_of_study}%')

    # Umiejętności i dodatkowe informacje
    if tools:
        additional_conditions.append('tools LIKE ?')
        params.append(f'%{tools}%')

    if methodologies:
        additional_conditions.append('methodologies LIKE ?')
        params.append(f'%{methodologies}%')

    if languages:
        additional_conditions.append('language_levels LIKE ?')
        params.append(f'%{languages}%')
        
    if certificates:
        additional_conditions.append('certificates LIKE ?')
        params.append(f'%{certificates}%')
        
    if additional_info:
        additional_conditions.append('additional_info LIKE ?')
        params.append(f'%{additional_info}%')

    if additional_conditions:
        query += ' AND ' + ' AND '.join(additional_conditions)
    
    # Dodanie sortowania po ID malejąco
    query += ' ORDER BY id DESC'

    try:
        conn = sqlite3.connect('database.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute(query, params)
        results = c.fetchall()
        conn.close()
    except Exception as e:
        print(f"Error executing search query: {e}")
        results = []

    return render_template('search.html', results=results, logged_in=True)

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
