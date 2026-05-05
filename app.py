import os
import requests
import pandas as pd
from datetime import datetime
from bs4 import BeautifulSoup
from flask import Flask, render_template, request, redirect, send_file, url_for
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# Database Setup
db_dir = '/app/data'
if not os.path.exists(db_dir): os.makedirs(db_dir)
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(db_dir, 'bookmarks.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Bookmark(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    category = db.Column(db.String(100), default='General')
    tags = db.Column(db.String(200), default='')
    content = db.Column(db.Text, default='') # For Full-Text Search
    clicks = db.Column(db.Integer, default=0)
    is_dead = db.Column(db.Boolean, default=False)
    date_added = db.Column(db.DateTime, default=datetime.utcnow)

def scrape_metadata(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(r.text, 'html.parser')
        title = soup.title.string if soup.title else url
        paragraphs = [p.get_text() for p in soup.find_all('p')[:5]]
        return title.strip(), " ".join(paragraphs).strip()
    except: return url, ""

@app.route('/')
def index():
    q = request.args.get('q', '')
    cat = request.args.get('category', '')
    tag = request.args.get('tag', '')
    sort = request.args.get('sort', 'newest')
    
    query = Bookmark.query
    if q: query = query.filter(Bookmark.title.contains(q) | Bookmark.content.contains(q) | Bookmark.url.contains(q))
    if cat: query = query.filter(Bookmark.category == cat)
    if tag: query = query.filter(Bookmark.tags.contains(tag))
    
    if sort == 'clicks': query = query.order_by(Bookmark.clicks.desc())
    elif sort == 'oldest': query = query.order_by(Bookmark.date_added.asc())
    else: query = query.order_by(Bookmark.date_added.desc())

    bookmarks = query.all()
    categories = db.session.query(Bookmark.category, db.func.count(Bookmark.id)).group_by(Bookmark.category).all()
    all_tags = sorted(list(set([t.strip() for r in db.session.query(Bookmark.tags).all() for t in r[0].split(',') if t.strip()])))
    top_bookmark = Bookmark.query.order_by(Bookmark.clicks.desc()).first()

    return render_template('index.html', bookmarks=bookmarks, categories=categories, 
                           tags=all_tags, total=Bookmark.query.count(), top=top_bookmark)

@app.route('/add', methods=['POST'])
def add():
    url = request.form['url']
    scraped_t, content = scrape_metadata(url)
    title = request.form['title'] if request.form['title'] else scraped_t
    db.session.add(Bookmark(title=title, url=url, category=request.form['category'], tags=request.form['tags'], content=content))
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/import_file', methods=['POST'])
def import_file():
    file = request.files.get('file')
    if not file: return redirect(url_for('index'))
    try:
        if file.filename.lower().endswith('.html'):
            soup = BeautifulSoup(file.read(), 'html.parser')
            for a in soup.find_all('a'):
                db.session.add(Bookmark(title=a.text, url=a.get('href'), category="Imported"))
        else:
            df = pd.read_csv(file) if file.filename.endswith('.csv') else pd.read_excel(file)
            df.columns = [c.lower().strip() for c in df.columns]
            for _, r in df.iterrows():
                u = r.get('url') or r.get('link') or r.get('address')
                if u:
                    db.session.add(Bookmark(title=str(r.get('title', u)), url=str(u), 
                                  category=str(r.get('category', 'Imported')), tags=str(r.get('tags', ''))))
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return f"Import Error: {str(e)}", 500
    return redirect(url_for('index'))

@app.route('/export/<fmt>')
def export(fmt):
    df = pd.read_sql(db.session.query(Bookmark).statement, db.engine)
    name = f"bookmarks_export.{fmt}"
    if fmt == 'csv': df.to_csv(name, index=False)
    else: df.to_excel(name, index=False)
    return send_file(name, as_attachment=True)

@app.route('/backup')
def backup():
    return send_file(os.path.join(db_dir, 'bookmarks.db'), as_attachment=True)

@app.route('/bulk_edit', methods=['POST'])
def bulk_edit():
    ids = request.form.getlist('selected_ids')
    new_cat = request.form.get('new_cat')
    new_tag = request.form.get('new_tag')
    if ids:
        targets = Bookmark.query.filter(Bookmark.id.in_(ids))
        if new_cat: targets.update({Bookmark.category: new_cat}, synchronize_session=False)
        if new_tag: # Append tags
            for b in targets.all(): b.tags = f"{b.tags},{new_tag}".strip(',')
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/health')
def health():
    for b in Bookmark.query.all():
        try: b.is_dead = requests.head(b.url, timeout=2).status_code >= 400
        except: b.is_dead = True
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/visit/<int:id>')
def visit(id):
    b = Bookmark.query.get(id)
    b.clicks += 1
    db.session.commit()
    return redirect(b.url)

@app.route('/delete/<int:id>')
def delete(id):
    db.session.delete(Bookmark.query.get(id))
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/danger/clear', methods=['POST'])
def clear_db():
    Bookmark.query.delete()
    db.session.commit()
    return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context(): db.create_all()
    app.run(host='0.0.0.0', port=5000)