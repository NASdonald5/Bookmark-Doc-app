from flask import Flask, render_template, request, redirect, url_for, send_file
import sqlite3
import os
from bs4 import BeautifulSoup

app = Flask(__name__)
DB_PATH = '/app/data/bookmarks.db'

# --- DATABASE UTILITIES ---

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  
    return conn
# init_db function in app.py
def init_db():
    if not os.path.exists('/app/data'):
        os.makedirs('/app/data')
    conn = get_db()
    # Added 'tags' column
    conn.execute('CREATE TABLE IF NOT EXISTS bookmarks (id INTEGER PRIMARY KEY, title TEXT, url TEXT, tags TEXT)')
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

# Updated the /add route to accept tags
@app.route('/add', methods=['POST'])
def add():
    title = request.form.get('title')
    url = request.form.get('url')
    tags = request.form.get('tags', '') # Get tags from form
    if title and url:
        conn = get_db()
        conn.execute('INSERT INTO bookmarks (title, url, tags) VALUES (?, ?, ?)', (title, url, tags))
        conn.commit()
        conn.close()
    return redirect(url_for('index'))

@app.route('/import', methods=['POST'])
def import_bookmarks():
    file = request.files.get('file')
    if file:
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

@app.route('/backup')
def backup():
    if os.path.exists(DB_PATH):
        return send_file(DB_PATH, as_attachment=True)
    return "No database found to backup", 404

# --- START APP ---

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)
