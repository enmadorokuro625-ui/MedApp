import sqlite3
import hashlib
import os
import json
import requests as http_requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime

app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "users.db")
GROQ_KEY_PATH = os.path.join(BASE_DIR, os.environ.get("GROQ_KEY_FILE", "groqkey.txt"))
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
# Модель по умолчанию и запасные при 403 (нет доступа к конкретной модели в консоли Groq)
GROQ_MODEL = os.environ.get("GROQ_MODEL", "").strip() or "llama-3.1-8b-instant"
GROQ_MODEL_FALLBACKS = [
    m.strip()
    for m in os.environ.get(
        "GROQ_MODEL_FALLBACKS",
        "llama-3.1-8b-instant,llama-3.3-70b-versatile,openai/gpt-oss-20b",
    ).split(",")
    if m.strip()
]

# Прокси для запросов к Groq (можно переопределить GROQ_PROXY_URL или отключить пустой строкой)
GROQ_PROXY_URL = os.environ.get(
    "GROQ_PROXY_URL",
    "http://EbLgV4:SP2GyS@134.195.152.45:9256",
).strip()
GROQ_PROXIES = (
    {"http": GROQ_PROXY_URL, "https": GROQ_PROXY_URL}
    if GROQ_PROXY_URL
    else None
)

AVAILABLE_EXERCISES = {
    "push_ups":       "Отжимания",
    "squats":         "Приседания",
    "bicep_curls":    "Сгибание на бицепс",
    "shoulder_press": "Жим над головой",
    "lunges":         "Выпады",
    "jumping_jacks":  "Джампинг Джек",
    "sit_ups":        "Скручивания",
    "high_knees":     "Высокие колени",
}


def load_groq_key():
    """Читает ключ рядом с site_api.py; убирает BOM, кавычки, лишние строки."""
    if not os.path.isfile(GROQ_KEY_PATH):
        return ""
    raw = open(GROQ_KEY_PATH, "r", encoding="utf-8-sig").read()
    for line in raw.replace("\r\n", "\n").split("\n"):
        k = line.strip().strip('"').strip("'")
        if k and not k.startswith("#"):
            return k
    return ""


def _groq_models_to_try():
    seen = set()
    out = []
    for m in [GROQ_MODEL] + GROQ_MODEL_FALLBACKS:
        if m and m not in seen:
            seen.add(m)
            out.append(m)
    return out


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        full_name TEXT NOT NULL,
        birth_date DATE NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('Пациент', 'Врач')),
        password TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('CREATE INDEX IF NOT EXISTS idx_username ON users(username)')
    c.execute('''CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id),
        name TEXT NOT NULL,
        start_time TEXT,
        end_time TEXT,
        data_points INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS workout_plans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id),
        plan_json TEXT NOT NULL,
        difficulty TEXT NOT NULL,
        goal TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS exercise_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id),
        plan_id INTEGER REFERENCES workout_plans(id),
        exercise_id TEXT NOT NULL,
        exercise_name TEXT NOT NULL,
        reps INTEGER NOT NULL DEFAULT 0,
        difficulty TEXT NOT NULL,
        duration_sec INTEGER DEFAULT 0,
        completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS user_goals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id),
        goal_text TEXT NOT NULL,
        target_reps INTEGER,
        target_exercise TEXT,
        achieved INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS sensor_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        bpm REAL DEFAULT 0,
        stress REAL DEFAULT 0,
        muscle REAL DEFAULT 0,
        alpha REAL DEFAULT 0,
        beta REAL DEFAULT 0,
        state TEXT DEFAULT 'Ожидание',
        recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('CREATE INDEX IF NOT EXISTS idx_sensor_username ON sensor_history(username)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_sensor_time ON sensor_history(recorded_at)')
    _migrate_sessions_meta(conn)
    conn.commit()
    conn.close()


def _migrate_sessions_meta(conn):
    """Добавляет meta_json к таблице sessions (детализация записи на клиенте)."""
    cols = [row[1] for row in conn.execute('PRAGMA table_info(sessions)').fetchall()]
    if 'meta_json' not in cols:
        conn.execute('ALTER TABLE sessions ADD COLUMN meta_json TEXT')


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# ═══════════════════════════════════════════════
# AUTH & PROFILE (БЕЗ ИЗМЕНЕНИЙ)
# ═══════════════════════════════════════════════

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        hashed = hash_password(data['password'])
        cursor.execute('''
            INSERT INTO users (username, email, full_name, birth_date, role, password)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (data['username'], data['email'], data['fullName'],
              data['birthDate'], data['role'], hashed))
        conn.commit()
        return jsonify({"success": True, "message": "Регистрация успешна"}), 201
    except sqlite3.IntegrityError:
        return jsonify({"success": False, "message": "Пользователь уже существует"}), 409
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    conn = get_db_connection()
    hashed = hash_password(data['password'])
    user = conn.execute('''
        SELECT id, username, email, full_name, role, created_at
        FROM users WHERE username = ? AND password = ?
    ''', (data['username'], hashed)).fetchone()
    conn.close()
    if user:
        return jsonify({"success": True, "user": dict(user)})
    return jsonify({"success": False, "message": "Неверные данные"}), 401

@app.route('/api/profile', methods=['POST'])
def update_profile():
    data = request.json
    try:
        conn = get_db_connection()
        if data.get('password'):
            hashed = hash_password(data['password'])
            conn.execute(
                'UPDATE users SET full_name=?, email=?, role=?, password=? WHERE id=?',
                (data['fullName'], data['email'], data['role'], hashed, data['id'])
            )
        else:
            conn.execute(
                'UPDATE users SET full_name=?, email=?, role=? WHERE id=?',
                (data['fullName'], data['email'], data['role'], data['id'])
            )
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Профиль обновлён"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# ═══════════════════════════════════════════════
# WORKOUT — AI Generation via Groq
# ═══════════════════════════════════════════════

@app.route('/api/workout/generate', methods=['POST'])
def generate_workout():
    data = request.json
    user_id = data.get('user_id')
    goal = data.get('goal', 'Общий тонус')
    difficulty = data.get('difficulty', 'medium')
    limitations = data.get('limitations', '')

    ex_list = "\n".join([f"- {eid}: {name}" for eid, name in AVAILABLE_EXERCISES.items()])
    diff_labels = {"easy": "Лёгкий", "medium": "Средний", "hard": "Сложный"}
    diff_label = diff_labels.get(difficulty, difficulty)

    system_prompt = (
        "Ты — профессиональный фитнес-тренер. Составь программу тренировки.\n"
        f"Доступные упражнения (используй ТОЛЬКО их ID из списка):\n{ex_list}\n\n"
        "Верни ответ СТРОГО в формате JSON без markdown-обёрток:\n"
        '{"name":"...","description":"...","exercises":['
        '{"id":"exercise_id","name":"Название","sets":N,"reps":N,"rest_sec":N,"tips":"..."}]}\n\n'
        f"Выбери 4-6 упражнений. Уровень: {diff_label}."
    )

    user_prompt = f"Цель: {goal}. Ограничения: {limitations}. Уровень: {diff_label}."

    try:
        api_key = load_groq_key()
        if not api_key:
            return jsonify({
                "success": False,
                "message": (
                    f"Нет API-ключа Groq. Создайте файл groqkey.txt в папке с site_api.py "
                    f"({BASE_DIR}) и вставьте в него одну строку с ключом (начинается с gsk_)."
                ),
            }), 503
        if not api_key.startswith("gsk_"):
            return jsonify({
                "success": False,
                "message": "Ключ в groqkey.txt должен начинаться с gsk_. Создайте ключ на console.groq.com → API Keys.",
            }), 503

        last_resp = None
        used_model = None
        for model in _groq_models_to_try():
            post_kw = {
                "headers": {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                "json": {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.7,
                },
                "timeout": 30,
            }
            if GROQ_PROXIES:
                post_kw["proxies"] = GROQ_PROXIES
            resp = http_requests.post(GROQ_API_URL, **post_kw)
            last_resp = resp
            if resp.status_code == 200:
                used_model = model
                break
            if resp.status_code != 403:
                break

        if last_resp is None or last_resp.status_code != 200:
            resp = last_resp
            hint = ""
            if resp is not None and resp.status_code == 403:
                hint = (
                    " Ключ отклонён (403). Создайте новый ключ на https://console.groq.com → API Keys, "
                    "убедитесь что нет лишних пробелов/BOM в groqkey.txt, проверьте VPN/сеть. "
                    f"Пробовали модели: {', '.join(_groq_models_to_try())}."
                )
            code = 502 if resp is not None else 502
            return jsonify({
                "success": False,
                "message": f"Groq API Error {getattr(resp, 'status_code', '?')}: {getattr(resp, 'text', 'no response')}{hint}",
            }), code

        if used_model and used_model != GROQ_MODEL:
            print(f"[Groq] OK с запасной моделью: {used_model} (основная {GROQ_MODEL} вернула ошибку)")

        resp = last_resp
        content = resp.json()["choices"][0]["message"]["content"].strip()

        if content.startswith("```"):
            content = content.replace("```json", "").replace("```", "").strip()

        plan = json.loads(content)

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            'INSERT INTO workout_plans (user_id, plan_json, difficulty, goal) VALUES (?,?,?,?)',
            (user_id, json.dumps(plan, ensure_ascii=False), difficulty, goal)
        )
        plan_id = cur.lastrowid
        conn.commit()
        conn.close()

        return jsonify({"success": True, "plan_id": plan_id, "plan": plan})

    except Exception as e:
        print(f"Error in generate_workout: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# ═══════════════════════════════════════════════
# ОСТАЛЬНЫЕ МЕТОДЫ (БЕЗ ИЗМЕНЕНИЙ)
# ═══════════════════════════════════════════════

@app.route('/api/sessions', methods=['GET', 'POST', 'DELETE'])
def manage_sessions():
    if request.method == 'GET':
        user_id = request.args.get('user_id')
        conn = get_db_connection()
        _migrate_sessions_meta(conn)
        rows = conn.execute('SELECT * FROM sessions WHERE user_id=? ORDER BY id DESC', (user_id,)).fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])
    
    elif request.method == 'POST':
        data = request.json
        conn = get_db_connection()
        _migrate_sessions_meta(conn)
        meta = data.get('meta')
        meta_json = json.dumps(meta, ensure_ascii=False) if isinstance(meta, dict) else data.get('meta_json')
        conn.execute(
            'INSERT INTO sessions (user_id, name, start_time, end_time, data_points, meta_json) VALUES (?,?,?,?,?,?)',
            (data['user_id'], data['name'], data.get('start'), data.get('end'), data.get('pts', 0), meta_json)
        )
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    
    elif request.method == 'DELETE':
        data = request.json
        conn = get_db_connection()
        conn.execute('DELETE FROM sessions WHERE id=? AND user_id=?', (data['id'], data['user_id']))
        conn.commit()
        conn.close()
        return jsonify({"success": True})

@app.route('/api/workout/logs', methods=['GET'])
def get_logs():
    user_id = request.args.get('user_id')
    conn = get_db_connection()
    rows = conn.execute('SELECT * FROM exercise_logs WHERE user_id=? ORDER BY id DESC', (user_id,)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/workout/log', methods=['POST'])
def log_ex():
    data = request.json
    conn = get_db_connection()
    conn.execute('INSERT INTO exercise_logs (user_id, plan_id, exercise_id, exercise_name, reps, difficulty) VALUES (?,?,?,?,?,?)',
                 (data['user_id'], data.get('plan_id'), data['exercise_id'], data['exercise_name'], data['reps'], data['difficulty']))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

# Мониторинг данных ESP32
_last_esp_data = {}   # username -> last data dict (per-user)
_last_db_write = {}   # username -> timestamp, чтобы не спамить БД
_active_esp_user = None  # Какому пользователю привязывать данные ESP
# Пользователи, у которых на сайте включена «Запись» — только тогда принимаем и пишем данные ESP
_sensor_recording_users = set()

_DEFAULT_ESP = {"success": True, "bpm": 0, "stress": 0, "muscle": 0, "alpha": 0, "beta": 0, "state": "Ожидание"}


@app.route('/api/esp/bind', methods=['POST'])
def bind_esp():
    """Привязать входящие данные ESP к текущему пользователю."""
    global _active_esp_user
    data = request.json
    _active_esp_user = data.get('username')
    print(f"[ESP BIND] Данные ESP привязаны к пользователю: {_active_esp_user}")
    return jsonify({"success": True, "bound_to": _active_esp_user})


@app.route('/api/sensor_recording', methods=['POST'])
def sensor_recording():
    """Вкл/выкл приём данных с датчиков для пользователя (кнопка «Запись» на сайте)."""
    global _sensor_recording_users
    data = request.json or {}
    username = data.get('username')
    if not username:
        return jsonify({"success": False, "message": "username required"}), 400
    active = bool(data.get('active'))
    if active:
        _sensor_recording_users.add(username)
    else:
        _sensor_recording_users.discard(username)
    return jsonify({"success": True, "active": active})


@app.route('/api/update_data', methods=['POST'])
def update_data():
    data = request.json
    if data:
        # Если есть привязанный пользователь — записываем данные под его именем
        if _active_esp_user:
            username = _active_esp_user
        else:
            username = data.get('username', 'unknown')

        # Данные принимаем в кэш и в БД только пока на сайте включена «Запись»
        if username not in _sensor_recording_users:
            return jsonify({"success": True, "ignored": True})

        entry = dict(data)
        entry["success"] = True
        entry["username"] = username
        _last_esp_data[username] = entry

        # Записываем в БД не чаще 1 раза в секунду на пользователя
        now = datetime.now().timestamp()
        if now - _last_db_write.get(username, 0) >= 1.0:
            _last_db_write[username] = now
            try:
                conn = get_db_connection()
                conn.execute(
                    '''INSERT INTO sensor_history
                       (username, bpm, stress, muscle, alpha, beta, state)
                       VALUES (?, ?, ?, ?, ?, ?, ?)''',
                    (username,
                     data.get('bpm', 0),
                     data.get('stress', 0),
                     data.get('muscle', 0),
                     data.get('alpha', 0),
                     data.get('beta', 0),
                     data.get('state', 'Ожидание'))
                )
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"sensor_history write error: {e}")

        return jsonify({"success": True})
    return jsonify({"success": False}), 400

@app.route('/api/last_data', methods=['GET'])
def get_last_esp_data():
    username = request.args.get('username')
    if username and username in _last_esp_data:
        return jsonify(_last_esp_data[username])
    # Если username не указан или нет данных — пробуем отдать любые последние данные
    if _last_esp_data:
        return jsonify(list(_last_esp_data.values())[-1])
    return jsonify(_DEFAULT_ESP)

@app.route('/api/sensor_history', methods=['GET'])
def get_sensor_history():
    """Возвращает историю показателей датчиков.
    Query params:
        username — обязательный
        limit    — макс. записей (по умолч. 100, макс. 1000)
        offset   — смещение для пагинации
    """
    username = request.args.get('username')
    if not username:
        return jsonify({"success": False, "message": "username required"}), 400

    limit  = min(int(request.args.get('limit', 100)), 1000)
    offset = int(request.args.get('offset', 0))

    conn = get_db_connection()
    rows = conn.execute(
        '''SELECT id, username, bpm, stress, muscle, alpha, beta, state, recorded_at
           FROM sensor_history
           WHERE username = ?
           ORDER BY recorded_at DESC
           LIMIT ? OFFSET ?''',
        (username, limit, offset)
    ).fetchall()

    total = conn.execute(
        'SELECT COUNT(*) as cnt FROM sensor_history WHERE username = ?',
        (username,)
    ).fetchone()['cnt']

    conn.close()
    return jsonify({
        "success": True,
        "total": total,
        "data": [dict(r) for r in rows]
    })

# ═══════════════════════════════════════════════
# USER PROFILE
# ═══════════════════════════════════════════════

@app.route('/api/user/<username>', methods=['GET'])
def get_user(username):
    conn = get_db_connection()
    user = conn.execute(
        '''SELECT id, username, email, full_name, birth_date, role, created_at
           FROM users WHERE username = ?''',
        (username,)
    ).fetchone()
    conn.close()
    if not user:
        return jsonify({"success": False, "message": "Пользователь не найден"}), 404
    u = dict(user)
    # Rename keys for frontend camelCase compatibility
    u['fullName'] = u.pop('full_name')
    u['birthDate'] = u.pop('birth_date')
    u['createdAt'] = u.pop('created_at')
    return jsonify(u)


# ═══════════════════════════════════════════════
# WORKOUT PLANS LIST
# ═══════════════════════════════════════════════

@app.route('/api/workout/plans', methods=['GET'])
def get_plans():
    user_id = request.args.get('user_id')
    conn = get_db_connection()
    rows = conn.execute(
        'SELECT * FROM workout_plans WHERE user_id=? ORDER BY id DESC', (user_id,)
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d['plan'] = json.loads(d.pop('plan_json'))
        except Exception:
            d['plan'] = {}
        result.append(d)
    return jsonify(result)


# ═══════════════════════════════════════════════
# WORKOUT STATS
# ═══════════════════════════════════════════════

@app.route('/api/workout/stats', methods=['GET'])
def workout_stats():
    user_id = request.args.get('user_id')
    conn = get_db_connection()

    total_reps = conn.execute(
        'SELECT COALESCE(SUM(reps),0) as s FROM exercise_logs WHERE user_id=?', (user_id,)
    ).fetchone()['s']

    total_exercises = conn.execute(
        'SELECT COUNT(*) as c FROM exercise_logs WHERE user_id=?', (user_id,)
    ).fetchone()['c']

    total_plans = conn.execute(
        'SELECT COUNT(*) as c FROM workout_plans WHERE user_id=?', (user_id,)
    ).fetchone()['c']

    by_exercise = [dict(r) for r in conn.execute(
        '''SELECT exercise_name, SUM(reps) as total_reps, COUNT(*) as sessions
           FROM exercise_logs WHERE user_id=?
           GROUP BY exercise_name ORDER BY total_reps DESC''', (user_id,)
    ).fetchall()]

    by_day = [dict(r) for r in conn.execute(
        '''SELECT DATE(completed_at) as day, SUM(reps) as total_reps
           FROM exercise_logs WHERE user_id=?
           GROUP BY DATE(completed_at) ORDER BY day DESC''', (user_id,)
    ).fetchall()]

    conn.close()
    return jsonify({
        "total_reps": total_reps,
        "total_exercises": total_exercises,
        "total_plans": total_plans,
        "by_exercise": by_exercise,
        "by_day": by_day
    })


# ═══════════════════════════════════════════════
# GOALS
# ═══════════════════════════════════════════════

@app.route('/api/goals', methods=['GET', 'POST'])
def manage_goals():
    if request.method == 'GET':
        user_id = request.args.get('user_id')
        conn = get_db_connection()
        rows = conn.execute(
            'SELECT * FROM user_goals WHERE user_id=? ORDER BY id DESC', (user_id,)
        ).fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])

    # POST
    data = request.json
    conn = get_db_connection()
    conn.execute(
        'INSERT INTO user_goals (user_id, goal_text, target_reps, target_exercise) VALUES (?,?,?,?)',
        (data['user_id'], data['goal_text'],
         data.get('target_reps'), data.get('target_exercise'))
    )
    conn.commit()
    conn.close()
    return jsonify({"success": True}), 201


@app.route('/api/goals/<int:goal_id>', methods=['PUT'])
def update_goal(goal_id):
    data = request.json
    conn = get_db_connection()
    conn.execute(
        'UPDATE user_goals SET achieved=? WHERE id=?',
        (data.get('achieved', 1), goal_id)
    )
    conn.commit()
    conn.close()
    return jsonify({"success": True})


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)