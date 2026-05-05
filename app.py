import os
import random
import requests
import pandas as pd
from datetime import datetime
from bs4 import BeautifulSoup
from flask import Flask, render_template, request, redirect, send_file, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

app = Flask(__name__)

# Persistence Handling
db_dir = '/app/data'
if not os.path.exists(db_dir):
    os.makedirs(db_dir)
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(db_dir, 'bookmarks.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Database Model
class Bookmark(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    category = db.Column(db.String(100), default='General')
    tags = db.Column(db.String(200), default='')
    content = db.Column(db.Text, default='') # Full-text storage
    clicks = db.Column(db.Integer, default=0)
    is_dead = db.Column(db.Boolean, default=False)
    date_added = db.Column(db.DateTime, default=datetime.utcnow)

def scrape_metadata(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(r.text, 'html.parser')
        title = soup.title.string if soup.title else url
        # Collect paragraphs for full-text search
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

    # Filters
    if q:
        query = query.filter(Bookmark.title.contains(q) | Bookmark.url.contains(q) | Bookmark.content.contains(q))
    if cat:
        query = query.filter(Bookmark.category == cat)
    if tag:
        query = query.filter(Bookmark.tags.contains(tag))
    if month and year:
        query = query.filter(db.extract('month', Bookmark.date_added) == month)
        query = query.filter(db.extract('year', Bookmark.date_added) == year)

    # Sorting
    if sort == 'clicks': query = query.order_by(Bookmark.clicks.desc())
    elif sort == 'oldest': query = query.order_by(Bookmark.date_added.asc())
    else: query = query.order_by(Bookmark.date_added.desc())

    bookmarks = query.all()
    
    # Sidebar stats
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

@app.route('/visit/<int:id>')
def visit(id):
    bm = Bookmark.query.get_or_404(id)
    bm.clicks += 1
    db.session.commit()
    return redirect(bm.url)

@app.route('/random')
def random_bm():
    all_ids = [b.id for b in Bookmark.query.all()]
    if all_ids:
        return redirect(url_for('visit', id=random.choice(all_ids)))
    return redirect(url_for('index'))

@app.route('/health_check')
def health_check():
    for bm in Bookmark.query.all():
        try:
            r = requests.head(bm.url, timeout=3)
            bm.is_dead = (r.status_code >= 400)
        except:
            bm.is_dead = True
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/delete/<int:id>')
def delete(id):
    bm = Bookmark.query.get_or_404(id)
    db.session.delete(bm)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/export/excel')
def export_excel():
    df = pd.read_sql(db.session.query(Bookmark).statement, db.engine)
    path = "bookmarks_export.xlsx"
    df.to_excel(path, index=False)
    return send_file(path, as_attachment=True)

@app.route('/clear_all', methods=['POST'])
def clear_all():
    Bookmark.query.delete()
    db.session.commit()
    return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000)