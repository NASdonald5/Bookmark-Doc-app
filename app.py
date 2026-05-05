import os
import requests
import pandas as pd
from datetime import datetime
from bs4 import BeautifulSoup
from flask import Flask, render_template, request, redirect, send_file, url_for, jsonify, make_response
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import extract
from concurrent.futures import ThreadPoolExecutor

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
    is_dead = db.Column(db.Boolean, default=False)
    date_added = db.Column(db.DateTime, default=datetime.utcnow)

def get_metadata(url):
    try:
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=3)
        soup = BeautifulSoup(r.text, 'html.parser')
        title = soup.title.string if soup.title else url
        paras = " ".join([p.get_text() for p in soup.find_all('p')[:3]])
        return title.strip(), paras.strip()
    except:
        return url, ""

# FAST DEAD LINK LOGIC
def check_single_link(bookmark_id):
    with app.app_context():
        b = Bookmark.query.get(bookmark_id)
        try:
            # Using HEAD request is faster than GET
            response = requests.head(b.url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=3, allow_redirects=True)
            b.is_dead = response.status_code >= 400
        except:
            b.is_dead = True
        db.session.commit()

@app.route('/')
def index():
    q = request.args.get('q', '')
    cat = request.args.get('category', '')
    tag = request.args.get('tag', '')
    sort = request.args.get('sort', 'id')
    month = request.args.get('month', '')

    query = Bookmark.query
    if q:
        query = query.filter(Bookmark.title.contains(q) | Bookmark.url.contains(q) | Bookmark.content.contains(q) | Bookmark.tags.contains(q))
    if cat: query = query.filter(Bookmark.category == cat)
    if tag: query = query.filter(Bookmark.tags.contains(tag))
    if month:
        try:
            m_dt = datetime.strptime(month, '%Y-%m')
            query = query.filter(extract('year', Bookmark.date_added) == m_dt.year, extract('month', Bookmark.date_added) == m_dt.month)
        except ValueError: pass

    if sort == 'clicks': query = query.order_by(Bookmark.clicks.desc())
    elif sort == 'title': query = query.order_by(Bookmark.title.asc())
    elif sort == 'dead': query = query.order_by(Bookmark.is_dead.desc())
    else: query = query.order_by(Bookmark.date_added.desc())

    categories = db.session.query(Bookmark.category, db.func.count(Bookmark.id)).group_by(Bookmark.category).all()
    all_tags = sorted(list(set([t.strip() for r in db.session.query(Bookmark.tags).all() for t in r[0].split(',') if t.strip()])))
    months_raw = db.session.query(Bookmark.date_added).order_by(Bookmark.date_added.desc()).all()
    unique_months = sorted(list(set([d[0].strftime('%Y-%m') for d in months_raw])), reverse=True)

    return render_template('index.html', 
        bookmarks=query.all(), 
        categories=categories, 
        tags=all_tags, 
        months=unique_months,
        total=Bookmark.query.count(), 
        top_links=Bookmark.query.order_by(Bookmark.clicks.desc()).limit(5).all(),
        search_query=q, current_cat=cat, current_tag=tag)

@app.route('/move_bookmark', methods=['POST'])
def move_bookmark():
    data = request.json
    b = Bookmark.query.get(data['id'])
    if b:
        b.category = data['category']
        db.session.commit()
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 400

@app.route('/add', methods=['POST'])
def add():
    url = request.form['url']
    title, content = get_metadata(url)
    user_title = request.form.get('title')
    db.session.add(Bookmark(
        title=user_title if user_title else title, 
        url=url, 
        category=request.form.get('category', 'General'), 
        tags=request.form.get('tags', ''),
        content=content
    ))
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
                href = a.get('href')
                if href:
                    # Update if exists, else create
                    existing = Bookmark.query.filter_by(url=href).first()
                    if existing:
                        existing.title = a.text or existing.title
                    else:
                        db.session.add(Bookmark(title=a.text or href, url=href, category="Imported"))
        else:
            df = pd.read_csv(file) if file.filename.endswith('.csv') else pd.read_excel(file)
            df.columns = [c.lower().strip() for c in df.columns]
            for _, r in df.iterrows():
                u = r.get('url') or r.get('link')
                if u:
                    existing = Bookmark.query.filter_by(url=str(u)).first()
                    if existing:
                        existing.category = str(r.get('category', existing.category))
                        existing.tags = str(r.get('tags', existing.tags))
                    else:
                        db.session.add(Bookmark(title=str(r.get('title', u)), url=str(u), 
                                      category=str(r.get('category', 'Imported')), tags=str(r.get('tags', ''))))
        db.session.commit()
    except Exception as e:
        return f"Import Error: {str(e)}", 500
    return redirect(url_for('index'))

@app.route('/check_links')
def check_links():
    bookmark_ids = [b.id for b in Bookmark.query.all()]
    with ThreadPoolExecutor(max_workers=20) as executor:
        executor.map(check_single_link, bookmark_ids)
    return redirect(url_for('index'))

@app.route('/export/<fmt>')
def export(fmt):
    df = pd.read_sql(db.session.query(Bookmark).statement, db.engine)
    if fmt == 'html':
        content = "<html><body><h1>Bookmarks</h1><ul>"
        for b in Bookmark.query.all():
            content += f'<li><a href="{b.url}">{b.title}</a></li>'
        content += "</ul></body></html>"
        response = make_response(content)
        response.headers["Content-Disposition"] = "attachment; filename=bookmarks.html"
        return response
    
    name = f"export.{fmt}"
    if fmt == 'csv': df.to_csv(name, index=False)
    elif fmt == 'excel': df.to_excel(name, index=False)
    return send_file(name, as_attachment=True)

@app.route('/backup')
def backup():
    return send_file(os.path.join(db_dir, 'bookmarks.db'), as_attachment=True)

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

@app.route('/clear_all', methods=['POST'])
def clear_all():
    Bookmark.query.delete()
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/bulk_update', methods=['POST'])
def bulk_update():
    ids = request.form.getlist('selected_ids')
    new_cat = request.form.get('new_category')
    new_tag = request.form.get('new_tag')
    if ids:
        targets = Bookmark.query.filter(Bookmark.id.in_(ids))
        if new_cat: targets.update({Bookmark.category: new_cat}, synchronize_session=False)
        if new_tag:
            for b in targets.all():
                b.tags = f"{b.tags},{new_tag}".strip(',')
        db.session.commit()
    return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context(): db.create_all()
    app.run(host='0.0.0.0', port=5000)