import os
import random
import requests
import pandas as pd
from datetime import datetime
from bs4 import BeautifulSoup
from flask import Flask, render_template, request, redirect, send_file, url_for
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# Database Persistence Configuration
db_dir = '/app/data'
if not os.path.exists(db_dir):
    os.makedirs(db_dir)
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(db_dir, 'bookmarks.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Database Model
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
    """Intelligence Feature: Automated Metadata Scraping"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(r.text, 'html.parser')
        title = soup.title.string if soup.title else url
        paragraphs = [p.get_text() for p in soup.find_all('p')[:5]]
        content = " ".join(paragraphs)
        return title.strip(), content.strip()
    except:
        return url, ""

@app.route('/')
def index():
    q = request.args.get('q', '')
    cat = request.args.get('category', '')
    tag = request.args.get('tag', '')
    month = request.args.get('month')
    year = request.args.get('year')
    sort = request.args.get('sort', 'newest')

    query = Bookmark.query

    # Search & Filtering Logic (Full-Text Search)
    if q:
        query = query.filter(Bookmark.title.contains(q) | Bookmark.url.contains(q) | Bookmark.content.contains(q))
    if cat:
        query = query.filter(Bookmark.category == cat)
    if tag:
        query = query.filter(Bookmark.tags.contains(tag))
    if month and year: # Time Machine Filter
        query = query.filter(db.extract('month', Bookmark.date_added) == month)
        query = query.filter(db.extract('year', Bookmark.date_added) == year)

    # Sorting
    if sort == 'clicks': query = query.order_by(Bookmark.clicks.desc())
    elif sort == 'oldest': query = query.order_by(Bookmark.date_added.asc())
    else: query = query.order_by(Bookmark.date_added.desc())

    bookmarks = query.all()
    categories = db.session.query(Bookmark.category, db.func.count(Bookmark.id)).group_by(Bookmark.category).all()
    total = Bookmark.query.count()
    top_links = Bookmark.query.order_by(Bookmark.clicks.desc()).limit(5).all()
    
    # Tag Cloud calculation
    all_tags_raw = db.session.query(Bookmark.tags).all()
    unique_tags = sorted(list(set([t.strip() for row in all_tags_raw for t in row[0].split(',') if t.strip()])))

    return render_template('index.html', bookmarks=bookmarks, categories=categories, 
                           total=total, tags=unique_tags, top_links=top_links,
                           search_query=q, current_cat=cat)

@app.route('/add', methods=['POST'])
def add():
    url = request.form['url']
    scraped_title, content = scrape_metadata(url)
    title = request.form['title'] if request.form['title'] else scraped_title
    
    new_bm = Bookmark(title=title, url=url, category=request.form['category'], 
                      tags=request.form['tags'], content=content)
    db.session.add(new_bm)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/import_file', methods=['POST'])
def import_file():
    file = request.files['file']
    filename = file.filename
    if filename.endswith('.html'):
        soup = BeautifulSoup(file.read(), 'html.parser')
        for link in soup.find_all('a'):
            db.session.add(Bookmark(title=link.text, url=link.get('href'), category="Imported"))
    elif filename.endswith(('.csv', '.xlsx')):
        df = pd.read_csv(file) if filename.endswith('.csv') else pd.read_excel(file)
        for _, row in df.iterrows():
            db.session.add(Bookmark(title=row.get('title'), url=row.get('url'), 
                                    category=row.get('category'), tags=row.get('tags')))
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/bulk_update', methods=['POST'])
def bulk_update():
    ids = request.form.getlist('selected_ids')
    new_cat = request.form.get('new_category')
    if ids and new_cat:
        Bookmark.query.filter(Bookmark.id.in_(ids)).update({Bookmark.category: new_cat}, synchronize_session=False)
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/health_check')
def health_check():
    """Intelligence Feature: Dead Link Detection"""
    for bm in Bookmark.query.all():
        try:
            r = requests.head(bm.url, timeout=3, allow_redirects=True)
            bm.is_dead = (r.status_code >= 400)
        except:
            bm.is_dead = True
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/export/<fmt>')
def export(fmt):
    df = pd.read_sql(db.session.query(Bookmark).statement, db.engine)
    path = f"export.{fmt}"
    if fmt == 'csv': df.to_csv(path, index=False)
    else: df.to_excel(path, index=False)
    return send_file(path, as_attachment=True)

@app.route('/backup')
def backup_db():
    return send_file(os.path.join(db_dir, 'bookmarks.db'), as_attachment=True)

@app.route('/visit/<int:id>')
def visit(id):
    bm = Bookmark.query.get_or_404(id)
    bm.clicks += 1
    db.session.commit()
    return redirect(bm.url)

@app.route('/delete/<int:id>')
def delete(id):
    bm = Bookmark.query.get_or_404(id)
    db.session.delete(bm)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/clear_all', methods=['POST'])
def clear_all():
    Bookmark.query.delete()
    db.session.commit()
    return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000)