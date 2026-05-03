from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import os
from bs4 import BeautifulSoup

app = Flask(__name__)
DB_PATH = '/app/data/bookmarks.db'

# --- DATABASE UTILITIES ---

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Crucial for the b['url'] syntax in HTML
    return conn

def init_db():
    if not os.path.exists('/app/data'):
        os.makedirs('/app/data')
    conn = get_db()
    conn.execute('CREATE TABLE IF NOT EXISTS bookmarks (id INTEGER PRIMARY KEY, title TEXT, url TEXT)')
    conn.close()

# --- ROUTES ---

@app.route('/')
def index():
    search_query = request.args.get('q', '')
    conn = get_db()
    if search_query:
        bookmarks = conn.execute(
            'SELECT * FROM bookmarks WHERE title LIKE ? OR url LIKE ?', 
            (f'%{search_query}%', f'%{search_query}%')
        ).fetchall()
    else:
        bookmarks = conn.execute('SELECT * FROM bookmarks').fetchall()
    conn.close()
    return render_template('index.html', bookmarks=bookmarks, search_query=search_query)

@app.route('/add', methods=['POST'])
def add():
    title, url = request.form.get('title'), request.form.get('url')
    if title and url:
        conn = get_db()
        conn.execute('INSERT INTO bookmarks (title, url) VALUES (?, ?)', (title, url))
        conn.commit()
        conn.close()
    return redirect(url_for('index'))

@app.route('/import', methods=['POST'])
def import_bookmarks():
    file = request.files.get('file')
    if file:
        # Read file and parse with BeautifulSoup
        soup = BeautifulSoup(file.read(), 'html.parser')
        conn = get_db()
        for link in soup.find_all('a'):
            title = link.text or "Untitled"
            url = link.get('href')
            if url and url.startswith('http'):
                conn.execute('INSERT INTO bookmarks (title, url) VALUES (?, ?)', (title, url))
        conn.commit()
        conn.close()
    return redirect(url_for('index'))

@app.route('/delete/<int:id>')
def delete(id):
    conn = get_db()
    conn.execute('DELETE FROM bookmarks WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/clear_all', methods=['POST'])
def clear_all():
    conn = get_db()
    conn.execute('DELETE FROM bookmarks')
    conn.commit()
    conn.close()
    return redirect(url_for('index'))



# --- START APP ---

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)
