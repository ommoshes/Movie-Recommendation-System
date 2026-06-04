import pytest
import mysql.connector
from app import app, get_db, User
from flask_login import login_user
from werkzeug.security import generate_password_hash


@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    with app.test_client() as client:
        yield client


@pytest.fixture
def db_connection():
    conn = get_db()
    yield conn
    conn.close()


@pytest.fixture
def test_user(client, db_connection):
    username = 'test_user_functional'
    password = 'test123456'
    
    c = db_connection.cursor(dictionary=True)
    
    c.execute("SELECT * FROM users WHERE username = %s", (username,))
    existing = c.fetchone()
    
    if existing:
        user_id = existing['id']
    else:
        hashed_password = generate_password_hash(password)
        c.execute(
            "INSERT INTO users (username, password) VALUES (%s, %s)",
            (username, hashed_password)
        )
        db_connection.commit()
        user_id = c.lastrowid
    
    c.close()
    
    return {
        'id': user_id,
        'username': username,
        'password': password
    }


@pytest.fixture
def logged_in_client(client, test_user):
    client.post('/login', data={
        'username': test_user['username'],
        'password': test_user['password']
    })
    return client


@pytest.fixture
def sample_movie(db_connection):
    c = db_connection.cursor(dictionary=True)
    c.execute("SELECT movieId, title, genres FROM movies LIMIT 1")
    movie = c.fetchone()
    c.close()
    return movie


@pytest.fixture
def cleanup_ratings(db_connection, test_user):
    yield
    c = db_connection.cursor()
    c.execute("DELETE FROM ratings WHERE userId = %s", (test_user['id'],))
    db_connection.commit()
    c.close()


@pytest.fixture
def cleanup_comments(db_connection, test_user):
    yield
    c = db_connection.cursor()
    c.execute("DELETE FROM movie_comments WHERE userId = %s", (test_user['id'],))
    db_connection.commit()
    c.close()
