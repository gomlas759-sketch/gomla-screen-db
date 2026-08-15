from flask import Flask, render_template, request, jsonify, redirect, url_for
import sqlite3, csv, io, json
from pathlib import Path

BASE = Path(__file__).resolve().parent
DB = BASE / 'screens.db'
app = Flask(__name__)

SCHEMA = '''
CREATE TABLE IF NOT EXISTS screens (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 screen_name TEXT NOT NULL,
 brand TEXT,
 compatible_models TEXT NOT NULL DEFAULT '',
 notes TEXT DEFAULT '',
 created_at TEXT DEFAULT CURRENT_TIMESTAMP,
 updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_screen_name ON screens(screen_name);
CREATE INDEX IF NOT EXISTS idx_brand ON screens(brand);
'''

def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

with db() as c:
    c.executescript(SCHEMA)

@app.route('/')
def home():
    with db() as c:
        total = c.execute('SELECT COUNT(*) n FROM screens').fetchone()['n']
        brands = c.execute("SELECT COUNT(DISTINCT brand) n FROM screens WHERE TRIM(COALESCE(brand,''))<>''").fetchone()['n']
    return render_template('index.html', total=total, brands=brands)

@app.get('/api/search')
def search():
    q = request.args.get('q','').strip()
    with db() as c:
        if q:
            like = f'%{q}%'
            rows = c.execute('''SELECT * FROM screens
                WHERE screen_name LIKE ? OR brand LIKE ? OR compatible_models LIKE ? OR notes LIKE ?
                ORDER BY screen_name COLLATE NOCASE LIMIT 300''', (like,like,like,like)).fetchall()
        else:
            rows = c.execute('SELECT * FROM screens ORDER BY screen_name COLLATE NOCASE LIMIT 300').fetchall()
    return jsonify([dict(r) for r in rows])

@app.post('/api/screens')
def add_screen():
    data = request.get_json(force=True)
    name = str(data.get('screen_name','')).strip()
    if not name:
        return jsonify(error='اسم الاسكرينة مطلوب'), 400
    models = data.get('compatible_models','')
    if isinstance(models, list):
        models = '\n'.join(str(x).strip() for x in models if str(x).strip())
    with db() as c:
        cur = c.execute('''INSERT INTO screens(screen_name,brand,compatible_models,notes,updated_at)
                           VALUES(?,?,?,?,CURRENT_TIMESTAMP)''',
                        (name, str(data.get('brand','')).strip(), str(models), str(data.get('notes','')).strip()))
        c.commit()
        row = c.execute('SELECT * FROM screens WHERE id=?',(cur.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201

@app.put('/api/screens/<int:sid>')
def edit_screen(sid):
    data = request.get_json(force=True)
    models = data.get('compatible_models','')
    if isinstance(models, list): models='\n'.join(str(x).strip() for x in models if str(x).strip())
    with db() as c:
        c.execute('''UPDATE screens SET screen_name=?, brand=?, compatible_models=?, notes=?, updated_at=CURRENT_TIMESTAMP WHERE id=?''',
                  (str(data.get('screen_name','')).strip(),str(data.get('brand','')).strip(),str(models),str(data.get('notes','')).strip(),sid))
        c.commit()
        row = c.execute('SELECT * FROM screens WHERE id=?',(sid,)).fetchone()
    return jsonify(dict(row)) if row else (jsonify(error='غير موجود'),404)

@app.delete('/api/screens/<int:sid>')
def delete_screen(sid):
    with db() as c:
        c.execute('DELETE FROM screens WHERE id=?',(sid,)); c.commit()
    return jsonify(ok=True)

@app.post('/api/import')
def import_data():
    payload = request.get_json(force=True)
    rows = payload.get('rows', payload if isinstance(payload,list) else [])
    if not isinstance(rows,list): return jsonify(error='تنسيق الاستيراد غير صحيح'),400
    count=0
    with db() as c:
        for r in rows:
            name = str(r.get('screen_name') or r.get('name') or '').strip()
            if not name: continue
            models = r.get('compatible_models', r.get('models',''))
            if isinstance(models,list): models='\n'.join(str(x).strip() for x in models if str(x).strip())
            c.execute('INSERT INTO screens(screen_name,brand,compatible_models,notes,updated_at) VALUES(?,?,?,?,CURRENT_TIMESTAMP)',
                      (name,str(r.get('brand','')).strip(),str(models),str(r.get('notes','')).strip()))
            count += 1
        c.commit()
    return jsonify(imported=count)

@app.get('/export.csv')
def export_csv():
    with db() as c: rows = c.execute('SELECT screen_name,brand,compatible_models,notes FROM screens ORDER BY screen_name').fetchall()
    out=io.StringIO(); w=csv.writer(out); w.writerow(['screen_name','brand','compatible_models','notes'])
    for r in rows: w.writerow([r['screen_name'],r['brand'],r['compatible_models'],r['notes']])
    resp=app.response_class('\ufeff'+out.getvalue(), mimetype='text/csv; charset=utf-8')
    resp.headers['Content-Disposition']='attachment; filename=screens.csv'; return resp

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5050, debug=True)
