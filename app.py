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
    tag_filter = request.args.get('tag', '')
    conn = get_db()
    
    total_row = conn.execute('SELECT COUNT(*) as count FROM bookmarks').fetchone()
    total = total_row['count'] if total_row else 0
    
    categories = conn.execute('''SELECT category, COUNT(*) as count FROM bookmarks 
                                 WHERE category != "" GROUP BY category''').fetchall()
    
    all_tags_raw = conn.execute('SELECT tags FROM bookmarks WHERE tags != ""').fetchall()
    tag_set = set()
    for row in all_tags_raw:
        if row['tags']:
            for t in row['tags'].split(','):
                if t.strip(): tag_set.add(t.strip())
    
    top_links = conn.execute('SELECT * FROM bookmarks ORDER BY clicks DESC LIMIT 5').fetchall()
    
    query = 'SELECT * FROM bookmarks WHERE 1=1'
    params = []
    if q:
        query += ' AND (title LIKE ? OR url LIKE ? OR tags LIKE ?)'
        params.extend([f'%{q}%', f'%{q}%', f'%{q}%'])
    if cat_filter:
        query += ' AND category = ?'; params.append(cat_filter)
    if tag_filter:
        query += ' AND tags LIKE ?'; params.append(f'%{tag_filter}%')
        
    bookmarks = conn.execute(query, params).fetchall()
    conn.close()
    return render_template('index.html', bookmarks=bookmarks, categories=categories, 
                           tags=sorted(list(tag_set)), total=total, search_query=q, 
                           current_cat=cat_filter, current_tag=tag_filter, top_links=top_links)

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
    # Fixed: Using .get() prevents 400 Bad Request if field is missing
    title = request.form.get('title')
    url = request.form.get('url')
    tags = request.form.get('tags', '')
    category = request.form.get('category', 'General')
    
    if title and url:
        conn.execute('INSERT INTO bookmarks (title, url, tags, category) VALUES (?, ?, ?, ?)', 
                     (title, url, tags, category))
        conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/edit/<int:id>', methods=['POST'])
def edit(id):
    conn = get_db()
    title = request.form.get('title')
    url = request.form.get('url')
    category = request.form.get('category', 'General')
    tags = request.form.get('tags', '')
    
    conn.execute('UPDATE bookmarks SET title=?, url=?, category=?, tags=? WHERE id=?', 
                 (title, url, category, tags, id))
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
        df.to_csv(output, index=False); mimetype, ext = 'text/csv', 'csv'
    elif fmt == 'excel':
        df.to_excel(output, index=False, engine='openpyxl'); mimetype, ext = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'xlsx'
    output.seek(0)
    return send_file(output, mimetype=mimetype, as_attachment=True, download_name=f'bookmarks_export.{ext}')

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
            try:
                df = pd.read_csv(file) if filename.endswith('.csv') else pd.read_excel(file)
                conn = get_db()
                for _, row in df.iterrows():
                    conn.execute('''INSERT INTO bookmarks (id, title, url, category, tags) VALUES (?,?,?,?,?)
                                    ON CONFLICT(id) DO UPDATE SET 
                                    title=excluded.title, url=excluded.url, category=excluded.category, tags=excluded.tags''',
                                 (row.get('id'), row['title'], row['url'], row.get('category', 'General'), row.get('tags', '')))
                conn.commit(); conn.close()
            except Exception:
                pass
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
def backup(): 
    if os.path.exists(DB_PATH):
        return send_file(DB_PATH, as_attachment=True)
    return "No file", 404

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)
