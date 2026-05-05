import os
import requests
import pandas as pd
from datetime import datetime
from bs4 import BeautifulSoup
from flask import Flask, render_template, request, redirect, send_file, url_for
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# Database Configuration
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
    content = db.Column(db.Text, default='') 
    clicks = db.Column(db.Integer, default=0)
    date_added = db.Column(db.DateTime, default=datetime.utcnow)

@app.route('/')
def index():
    q = request.args.get('q', '')
    cat = request.args.get('category', '')
    tag = request.args.get('tag', '')
    sort = request.args.get('sort', 'id')
    
    query = Bookmark.query
    if q: query = query.filter(Bookmark.title.contains(q) | Bookmark.url.contains(q) | Bookmark.tags.contains(q))
    if cat: query = query.filter(Bookmark.category == cat)
    if tag: query = query.filter(Bookmark.tags.contains(tag))
    
    if sort == 'clicks': query = query.order_by(Bookmark.clicks.desc())
    elif sort == 'title': query = query.order_by(Bookmark.title.asc())
    else: query = query.order_by(Bookmark.date_added.desc())

    bookmarks = query.all()
    # Categorization count for sidebar
    categories = db.session.query(Bookmark.category, db.func.count(Bookmark.id).label('count')).group_by(Bookmark.category).all()
    # Unique tags cloud
    all_tags_raw = db.session.query(Bookmark.tags).all()
    unique_tags = sorted(list(set([t.strip() for row in all_tags_raw for t in row[0].split(',') if t.strip()])))
    # Top Visited Section
    top_links = Bookmark.query.order_by(Bookmark.clicks.desc()).limit(5).all()

    return render_template('index.html', bookmarks=bookmarks, categories=categories, 
                           tags=unique_tags, total=Bookmark.query.count(), 
                           top_links=top_links, search_query=q, current_cat=cat)

@app.route('/add', methods=['POST'])
def add():
    url = request.form['url']
    title = request.form['title']
    # Minimal metadata fallback if title is missing
    if not title:
        try:
            r = requests.get(url, timeout=3)
            soup = BeautifulSoup(r.text, 'html.parser')
            title = soup.title.string if soup.title else url
        except: title = url
        
    db.session.add(Bookmark(title=title, url=url, category=request.form['category'], tags=request.form['tags']))
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
                db.session.add(Bookmark(title=a.text or a.get('href'), url=a.get('href'), category="Imported"))
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

@app.route('/bulk_update', methods=['POST'])
def bulk_update():
    ids = request.form.getlist('selected_ids')
    new_cat = request.form.get('new_category')
    if ids and new_cat:
        Bookmark.query.filter(Bookmark.id.in_(ids)).update({Bookmark.category: new_cat}, synchronize_session=False)
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/export/excel')
def export_excel():
    df = pd.read_sql(db.session.query(Bookmark).statement, db.engine)
    path = "bookmarks_export.xlsx"
    df.to_excel(path, index=False)
    return send_file(path, as_attachment=True)

@app.route('/backup')
def backup():
    return send_file(os.path.join(db_dir, 'bookmarks.db'), as_attachment=True)

@app.route('/visit/<int:id>')
def visit(id):
    b = Bookmark.query.get_or_404(id)
    b.clicks += 1
    db.session.commit()
    return redirect(b.url)

@app.route('/delete/<int:id>')
def delete(id):
    b = Bookmark.query.get_or_404(id)
    db.session.delete(b)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/clear_all', methods=['POST'])
def clear_all():
    Bookmark.query.delete()
    db.session.commit()
    return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context(): db.create_all()
    app.run(host='0.0.0.0', port=5000)