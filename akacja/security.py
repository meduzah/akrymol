import re
from datetime import datetime, timedelta
import secrets
import string
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Message
from flask import url_for

def validate_password(password):
    """Sprawdza czy hasło spełnia wymagania bezpieczeństwa"""
    if len(password) < 8:
        return False, "Hasło musi mieć co najmniej 8 znaków"
    
    if not re.search(r"[A-Z]", password):
        return False, "Hasło musi zawierać przynajmniej jedną wielką literę"
    
    if not re.search(r"[a-z]", password):
        return False, "Hasło musi zawierać przynajmniej jedną małą literę"
    
    if not re.search(r"\d", password):
        return False, "Hasło musi zawierać przynajmniej jedną cyfrę"
    
    if not re.search(r"[ !@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?]", password):
        return False, "Hasło musi zawierać przynajmniej jeden znak specjalny"
    
    return True, None

def validate_email(email):
    """Sprawdza poprawność adresu email"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email):
        return False, "Nieprawidłowy format adresu email"
    return True, None

def generate_token(length=32):
    """Generuje losowy token"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def generate_verification_token():
    """Generuje token weryfikacyjny i datę jego wygaśnięcia"""
    token = generate_token()
    expires = datetime.now() + timedelta(hours=24)
    return token, expires

def generate_2fa_code():
    """Generuje 6-cyfrowy kod do weryfikacji dwuetapowej"""
    return ''.join(secrets.choice(string.digits) for _ in range(6))

def send_verification_email(mail, user_email, token):
    """Wysyła email z linkiem weryfikacyjnym"""
    try:
        msg = Message('Potwierdź swoje konto w PMfinder',
                     recipients=[user_email])
        
        verification_link = url_for('verify_email', token=token, _external=True)
        
        msg.html = f'''
        <h2>Dziękujemy za rejestrację w PMfinder!</h2>
        <p>Aby aktywować swoje konto, kliknij w poniższy link:</p>
        <p><a href="{verification_link}">Aktywuj konto</a></p>
        <p>Link jest ważny przez 24 godziny.</p>
        <p>Jeśli nie rejestrowałeś się w naszym serwisie, zignoruj tę wiadomość.</p>
        '''
        
        print(f"Próba wysłania emaila do: {user_email}")
        print(f"Link weryfikacyjny: {verification_link}")
        mail.send(msg)
        print("Email wysłany pomyślnie")
        return True
    except Exception as e:
        print(f"Błąd podczas wysyłania emaila: {str(e)}")
        return False

def send_2fa_code(mail, user_email, code):
    """Wysyła kod weryfikacji dwuetapowej"""
    try:
        msg = Message('Twój kod weryfikacyjny do PMfinder',
                     recipients=[user_email])
        
        msg.html = f'''
        <h2>Kod weryfikacji dwuetapowej</h2>
        <p>Twój kod weryfikacyjny to: <strong>{code}</strong></p>
        <p>Kod jest ważny przez 10 minut.</p>
        <p>Jeśli nie próbowałeś się zalogować, zignoruj tę wiadomość.</p>
        '''
        
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Błąd podczas wysyłania kodu 2FA: {str(e)}")
        return False

def check_login_attempts(user):
    """Sprawdza czy konto nie jest zablokowane i aktualizuje licznik prób logowania"""
    now = datetime.now()
    
    # Jeśli konto jest zablokowane
    if user['account_locked_until'] and datetime.fromisoformat(user['account_locked_until']) > now:
        remaining_time = datetime.fromisoformat(user['account_locked_until']) - now
        minutes = remaining_time.total_seconds() / 60
        return False, f"Konto jest tymczasowo zablokowane. Spróbuj ponownie za {int(minutes)} minut."
    
    return True, None

def update_login_attempts(conn, username, success):
    """Aktualizuje licznik prób logowania"""
    c = conn.cursor()
    now = datetime.now()
    
    if success:
        # Resetuj licznik po udanym logowaniu
        c.execute('''
            UPDATE users 
            SET failed_login_attempts = 0,
                last_login_attempt = ?,
                account_locked_until = NULL
            WHERE username = ?
        ''', (now.isoformat(), username))
    else:
        # Zwiększ licznik nieudanych prób
        c.execute('''
            UPDATE users 
            SET failed_login_attempts = failed_login_attempts + 1,
                last_login_attempt = ?
            WHERE username = ?
        ''', (now.isoformat(), username))
        
        # Sprawdź czy przekroczono limit prób
        c.execute('SELECT failed_login_attempts FROM users WHERE username = ?', (username,))
        attempts = c.fetchone()[0]
        
        if attempts >= 5:
            # Zablokuj konto na 30 minut
            locked_until = now + timedelta(minutes=30)
            c.execute('''
                UPDATE users 
                SET account_locked_until = ?
                WHERE username = ?
            ''', (locked_until.isoformat(), username))
    
    conn.commit() 