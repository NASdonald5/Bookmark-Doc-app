from flask import Flask, render_template, request, redirect, url_for, send_file
import sqlite3
import os
from bs4 import BeautifulSoup
import json

app = Flask(__name__)
DB_PATH = '/app/data/bookmarks.db'

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  
    return conn

def init_db():
    if not os.path.exists('/app/data'):
        os.makedirs('/app/data')
    conn = get_db()
    conn.execute('''CREATE TABLE IF NOT EXISTS bookmarks 
        (id INTEGER PRIMARY KEY, title TEXT, url TEXT, tags TEXT, 
         category TEXT, custom_fields TEXT)''')
    conn.close()

@app.route('/')
def index():
    search_query = request.args.get('q', '')
    cat_filter = request.args.get('category', '')
    conn = get_db()
    
    categories = conn.execute('SELECT DISTINCT category FROM bookmarks WHERE category IS NOT NULL AND category != ""').fetchall()
    
    query = 'SELECT * FROM bookmarks WHERE 1=1'
    params = []
    
    if search_query:
        query += ' AND (title LIKE ? OR url LIKE ? OR tags LIKE ?)'
        params.extend([f'%{search_query}%', f'%{search_query}%', f'%{search_query}%'])
    
    if cat_filter:
        query += ' AND category = ?'
        params.append(cat_filter)
        
    bookmarks = conn.execute(query, params).fetchall()
    conn.close()
    return render_template('index.html', bookmarks=bookmarks, categories=categories, search_query=search_query, current_cat=cat_filter)

@app.route('/add', methods=['POST'])
def add():
    title = request.form.get('title')
    url = request.form.get('url')
    tags = request.form.get('tags', '')
    category = request.form.get('category', 'Uncategorized')
    if title and url:
        conn = get_db()
        conn.execute('INSERT INTO bookmarks (title, url, tags, category, custom_fields) VALUES (?, ?, ?, ?, ?)', 
                     (title, url, tags, category, '{}'))
        conn.commit()
        conn.close()
    return redirect(url_for('index'))

@app.route('/edit/<int:id>', methods=['POST'])
def edit(id):
    title = request.form.get('title')
    url = request.form.get('url')
    category = request.form.get('category')
    tags = request.form.get('tags')
    conn = get_db()
    conn.execute('UPDATE bookmarks SET title=?, url=?, category=?, tags=? WHERE id=?', 
                 (title, url, category, tags, id))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/bulk_update', methods=['POST'])
def bulk_update():
    ids = request.form.getlist('selected_ids')
    new_tag = request.form.get('new_tag')
    new_cat = request.form.get('new_category')
    if ids:
        conn = get_db()
        for b_id in ids:
            if new_tag:
                conn.execute("UPDATE bookmarks SET tags = CASE WHEN tags = '' THEN ? ELSE tags || ? END WHERE id = ?", 
                             (new_tag, f",{new_tag}", b_id))
            if new_cat:
                conn.execute("UPDATE bookmarks SET category = ? WHERE id = ?", (new_cat, b_id))
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
                conn.execute('INSERT INTO bookmarks (title, url, tags, category, custom_fields) VALUES (?, ?, ?, ?, ?)', 
                             (title, url, '', 'Imported', '{}'))
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
    return "No database found", 404

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)
