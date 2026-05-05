import os
import sqlite3
import pandas as pd
from flask import Flask, render_template, request, redirect, send_file, url_for
from bs4 import BeautifulSoup

app = Flask(__name__)
DB_PATH = '/app/data/bookmarks.db' if os.path.exists('/app/data') else 'bookmarks.db'

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('''CREATE TABLE IF NOT EXISTS bookmarks 
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                     title TEXT, url TEXT, category TEXT, tags TEXT, clicks INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()

@app.route('/')
def index():
    q = request.args.get('q', '')
    cat = request.args.get('category', '')
    tag = request.args.get('tag', '')
    sort = request.args.get('sort', 'id')

    conn = get_db_connection()
    query = "SELECT * FROM bookmarks WHERE (title LIKE ? OR url LIKE ? OR tags LIKE ?)"
    params = [f'%{q}%', f'%{q}%', f'%{q}%']

    if cat:
        query += " AND category = ?"
        params.append(cat)
    if tag:
        query += " AND tags LIKE ?"
        params.append(f'%{tag}%')
    
    query += f" ORDER BY {sort} DESC"
    
    bookmarks = conn.execute(query, params).fetchall()
    categories = conn.execute("SELECT category, COUNT(*) as count FROM bookmarks GROUP BY category").fetchall()
    total = conn.execute("SELECT COUNT(*) FROM bookmarks").fetchone()[0]
    top_links = conn.execute("SELECT * FROM bookmarks ORDER BY clicks DESC LIMIT 5").fetchall()
    
    # Extract unique tags for the tag cloud
    all_tags = conn.execute("SELECT tags FROM bookmarks").fetchall()
    unique_tags = set()
    for row in all_tags:
        if row['tags']:
            unique_tags.update([t.strip() for t in row['tags'].split(',') if t.strip()])

    conn.close()
    return render_template('index.html', bookmarks=bookmarks, categories=categories, 
                           total=total, tags=sorted(list(unique_tags)), top_links=top_links, 
                           search_query=q, current_cat=cat, current_tag=tag)

@app.route('/add', methods=['POST'])
def add():
    conn = get_db_connection()
    conn.execute("INSERT INTO bookmarks (title, url, category, tags) VALUES (?, ?, ?, ?)",
                 (request.form['title'], request.form['url'], request.form['category'], request.form['tags']))
    conn.commit()
    conn.close()
    return redirect('/')

@app.route('/visit/<int:id>')
def visit(id):
    conn = get_db_connection()
    bookmark = conn.execute("SELECT * FROM bookmarks WHERE id = ?", (id,)).fetchone()
    conn.execute("UPDATE bookmarks SET clicks = clicks + 1 WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return redirect(bookmark['url'])

@app.route('/edit/<int:id>', methods=['POST'])
def edit(id):
    conn = get_db_connection()
    conn.execute("UPDATE bookmarks SET title=?, url=?, category=?, tags=? WHERE id=?",
                 (request.form['title'], request.form['url'], request.form['category'], request.form['tags'], id))
    conn.commit()
    conn.close()
    return redirect('/')

@app.route('/bulk_update', methods=['POST'])
def bulk_update():
    ids = request.form.getlist('selected_ids')
    new_cat = request.form.get('new_category')
    if ids and new_cat:
        conn = get_db_connection()
        conn.execute(f"UPDATE bookmarks SET category=? WHERE id IN ({','.join(['?']*len(ids))})", [new_cat] + ids)
        conn.commit()
        conn.close()
    return redirect('/')

@app.route('/delete/<int:id>')
def delete(id):
    conn = get_db_connection()
    conn.execute("DELETE FROM bookmarks WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return redirect('/')

@app.route('/import_file', methods=['POST'])
def import_file():
    file = request.files['file']
    filename = file.filename
    conn = get_db_connection()
    
    if filename.endswith('.html'):
        soup = BeautifulSoup(file.read(), 'html.parser')
        for link in soup.find_all('a'):
            conn.execute("INSERT INTO bookmarks (title, url, category) VALUES (?, ?, ?)",
                         (link.text, link.get('href'), "Imported"))
    elif filename.endswith('.csv'):
        df = pd.read_csv(file)
        df.to_sql('bookmarks', conn, if_exists='append', index=False)
    elif filename.endswith('.xlsx'):
        df = pd.read_excel(file)
        df.to_sql('bookmarks', conn, if_exists='append', index=False)
    
    conn.commit()
    conn.close()
    return redirect('/')

@app.route('/export/<fmt>')
def export(fmt):
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT title, url, category, tags, clicks FROM bookmarks", conn)
    conn.close()
    
    path = f"export.{fmt}"
    if fmt == 'csv': df.to_csv(path, index=False)
    elif fmt == 'excel' or fmt == 'xlsx': 
        path = "export.xlsx"
        df.to_excel(path, index=False)
    
    return send_file(path, as_attachment=True)

@app.route('/backup')
def backup():
    return send_file(DB_PATH, as_attachment=True)

@app.route('/clear_all', methods=['POST'])
def clear_all():
    conn = get_db_connection()
    conn.execute("DELETE FROM bookmarks")
    conn.commit()
    conn.close()
    return redirect('/')

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)