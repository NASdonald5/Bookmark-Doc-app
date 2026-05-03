from flask import Flask, render_template, request, redirect, url_for, send_file
import sqlite3
import os
import pandas as pd
import io
from bs4 import BeautifulSoup

app = Flask(__name__)
DB_PATH = '/app/data/bookmarks.db'

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  
    return conn

def init_db():
    if not os.path.exists('/app/data'): os.makedirs('/app/data')
    conn = get_db()
    conn.execute('''CREATE TABLE IF NOT EXISTS bookmarks 
        (id INTEGER PRIMARY KEY, title TEXT, url TEXT, tags TEXT, 
         category TEXT, clicks INTEGER DEFAULT 0)''')
    conn.close()

@app.route('/')
def index():
    q = request.args.get('q', '')
    cat_filter = request.args.get('category', '')
    conn = get_db()
    
    total = conn.execute('SELECT COUNT(*) as count FROM bookmarks').fetchone()['count']
    categories = conn.execute('''SELECT category, COUNT(*) as count FROM bookmarks 
                                 WHERE category != "" GROUP BY category''').fetchall()
    top_links = conn.execute('SELECT * FROM bookmarks ORDER BY clicks DESC LIMIT 5').fetchall()
    
    query = 'SELECT * FROM bookmarks WHERE 1=1'
    params = []
    if q:
        query += ' AND (title LIKE ? OR url LIKE ? OR tags LIKE ?)'
        params.extend([f'%{q}%', f'%{q}%', f'%{q}%'])
    if cat_filter:
        query += ' AND category = ?'
        params.append(cat_filter)
        
    bookmarks = conn.execute(query, params).fetchall()
    conn.close()
    return render_template('index.html', bookmarks=bookmarks, categories=categories, 
                           total=total, search_query=q, current_cat=cat_filter, top_links=top_links)

@app.route('/visit/<int:id>')
def visit(id):
    conn = get_db()
    conn.execute('UPDATE bookmarks SET clicks = clicks + 1 WHERE id = ?', (id,))
    row = conn.execute('SELECT url FROM bookmarks WHERE id = ?', (id,)).fetchone()
    conn.commit(); conn.close()
    return redirect(row['url'])

@app.route('/add', methods=['POST'])
def add():
    conn = get_db()
    conn.execute('INSERT INTO bookmarks (title, url, tags, category) VALUES (?, ?, ?, ?)', 
                 (request.form['title'], request.form['url'], request.form['tags'], request.form.get('category', 'General')))
    conn.commit(); conn.close()
    return redirect(url_for('index'))

@app.route('/edit/<int:id>', methods=['POST'])
def edit(id):
    conn = get_db()
    conn.execute('UPDATE bookmarks SET title=?, url=?, category=?, tags=? WHERE id=?', 
                 (request.form['title'], request.form['url'], request.form['category'], request.form['tags'], id))
    conn.commit(); conn.close()
    return redirect(url_for('index'))

@app.route('/bulk_update', methods=['POST'])
def bulk_update():
    ids = request.form.getlist('selected_ids')
    new_cat = request.form.get('new_category')
    if ids and new_cat:
        conn = get_db()
        for b_id in ids:
            conn.execute("UPDATE bookmarks SET category = ? WHERE id = ?", (new_cat, b_id))
        conn.commit(); conn.close()
    return redirect(url_for('index'))

@app.route('/export/<fmt>')
def export_data(fmt):
    conn = get_db()
    df = pd.read_sql_query("SELECT id, title, url, category, tags, clicks FROM bookmarks", conn)
    conn.close()
    output = io.BytesIO()
    if fmt == 'csv':
        df.to_csv(output, index=False)
        mimetype = 'text/csv'
    else:
        df.to_excel(output, index=False, engine='openpyxl')
        mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    output.seek(0)
    return send_file(output, mimetype=mimetype, as_attachment=True, download_name=f'bookmarks_export.{fmt}')

@app.route('/import_file', methods=['POST'])
def import_file():
    file = request.files.get('file')
    if file:
        filename = file.filename.lower()
        if filename.endswith('.html'):
            soup = BeautifulSoup(file.read(), 'html.parser')
            conn = get_db()
            for link in soup.find_all('a'):
                conn.execute('INSERT INTO bookmarks (title, url, tags, category) VALUES (?,?,?,?)',
                             (link.text or "Untitled", link.get('href'), '', 'Imported'))
            conn.commit(); conn.close()
        else:
            df = pd.read_csv(file) if filename.endswith('.csv') else pd.read_excel(file)
            conn = get_db()
            for _, row in df.iterrows():
                conn.execute('''INSERT INTO bookmarks (id, title, url, category, tags) VALUES (?,?,?,?,?)
                                ON CONFLICT(id) DO UPDATE SET 
                                title=excluded.title, url=excluded.url, category=excluded.category, tags=excluded.tags''',
                             (row.get('id'), row['title'], row['url'], row.get('category', 'General'), row.get('tags', '')))
            conn.commit(); conn.close()
    return redirect(url_for('index'))

@app.route('/clear_all', methods=['POST'])
def clear_all():
    conn = get_db(); conn.execute('DELETE FROM bookmarks'); conn.commit(); conn.close()
    return redirect(url_for('index'))

@app.route('/delete/<int:id>')
def delete(id):
    conn = get_db(); conn.execute('DELETE FROM bookmarks WHERE id = ?', (id,)); conn.commit(); conn.close()
    return redirect(url_for('index'))

@app.route('/backup')
def backup(): return send_file(DB_PATH, as_attachment=True)

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)
