import os
import sys
import json
import logging
import requests
from functools import wraps
from flask import Flask, jsonify, send_from_directory, request, redirect, url_for, render_template
from flask_login import (
    LoginManager, login_user, logout_user,
    login_required, current_user, UserMixin
)
from werkzeug.security import check_password_hash, generate_password_hash

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    print("ERROR: define SECRET_KEY in the environment")
    sys.exit(1)

LOG_DIR = os.path.join(os.path.dirname(__file__), '..', 'logs')
os.makedirs(LOG_DIR, exist_ok=True)
log_file = os.path.join(LOG_DIR, 'actions.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from shared.machine import get_status, wake_machine

app = Flask(
    __name__,
    static_folder='../web',
    static_url_path='',
    template_folder='../web'
)
app.secret_key = SECRET_KEY

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

USERS_FILE = os.path.join(os.path.dirname(__file__), 'users.json')
DATA_FILE  = os.path.join(os.path.dirname(__file__), 'database.json')
DEFAULT_PORT = 5000
ROLES = ('admin', 'manager', 'viewer')

class User(UserMixin):
    def __init__(self, username, role, machines):
        self.id = username
        self.role = role
        self.machines = machines  # [] means access to all

def load_users():
    if not os.path.exists(USERS_FILE):
        default = [{
            'username': 'admin',
            'password': generate_password_hash('admin'),
            'role': 'admin',
            'machines': []
        }]
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(default, f, indent=2)
    with open(USERS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_users(users):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, indent=2, ensure_ascii=False)

@login_manager.user_loader
def load_user(user_id):
    for u in load_users():
        if u['username'] == user_id:
            return User(u['username'], u['role'], u.get('machines', []))
    return None

def roles_required(*roles):
    def decorator(fn):
        @wraps(fn)
        @login_required
        def wrapper(*args, **kwargs):
            if current_user.role not in roles:
                return jsonify({'error':'Permission refusée'}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator

def machine_access_required(fn):
    @wraps(fn)
    @login_required
    def wrapper(id, *args, **kwargs):
        allowed = current_user.machines
        if current_user.role == 'admin' or not allowed or id in allowed:
            return fn(id, *args, **kwargs)
        return jsonify({'error':'Accès machine refusé'}), 403
    return wrapper

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = next((u for u in load_users() if u['username']==username), None)
        if user and check_password_hash(user['password'], password):
            login_user(User(username, user['role'], user.get('machines', [])))
            logger.info(f"🔑 {username} connecté")
            return redirect(request.args.get('next') or url_for('index'))
        return render_template('login.html', error='Identifiants invalides')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    uname = current_user.id
    logout_user()
    logger.info(f"🚪 {uname} déconnecté")
    return redirect(url_for('login'))

@app.route('/me')
@login_required
def me():
    return jsonify({
        'username': current_user.id,
        'role': current_user.role,
        'machines': current_user.machines
    })

def load_machines():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_machines(machines):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(machines, f, indent=2, ensure_ascii=False)

def send_http_command(ip, endpoint, port=DEFAULT_PORT):
    try:
        url = f"http://{ip}:{port}{endpoint}"
        r = requests.get(url, timeout=5)
        r.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Erreur HTTP {endpoint} sur {ip}:{port}: {e}")
        return False

@app.route('/')
@login_required
def index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/machines', methods=['GET'])
@login_required
def list_machines():
    machines = load_machines()
    for m in machines:
        m['online'] = get_status(m['ip'])
    return jsonify(machines)

@app.route('/machine/<int:id>/<cmd>', methods=['POST'])
@machine_access_required
def action(id, cmd):
    machines = load_machines()
    m = machines[id]
    if cmd == 'on':
        wake_machine(m['mac']); status='Allumage envoyé'
    elif cmd == 'sleep':
        ok = send_http_command(m['ip'], '/sleep', m.get('port', DEFAULT_PORT))
        status = 'Mise en veille envoyée' if ok else 'Erreur veille'
    elif cmd == 'off':
        ok = send_http_command(m['ip'], '/shutdown', m.get('port', DEFAULT_PORT))
        status = 'Arrêt envoyé' if ok else 'Erreur arrêt'
    elif cmd == 'restart':
        ok = send_http_command(m['ip'], '/restart', m.get('port', DEFAULT_PORT))
        status = 'Redémarrage envoyé' if ok else 'Erreur redémarrage'
    else:
        return jsonify({'error':'Commande inconnue'}), 400
    logger.info(f"🎮 {current_user.id} a exécuté {cmd} sur machine {id} ({m['name']})")
    return jsonify({'status':status})

@app.route('/machines', methods=['POST'])
@roles_required('admin','manager')
def add_machine():
    data = request.get_json() or {}
    if not all(k in data for k in ('name','ip','mac','port')):
        return jsonify({'error':'name, ip, mac et port requis'}), 400
    machines = load_machines()
    machines.append({
        'name': data['name'],
        'ip':   data['ip'],
        'mac':  data['mac'],
        'port': int(data['port'])
    })
    save_machines(machines)
    logger.info(f"➕ {current_user.id} a ajouté {data['name']} (IP {data['ip']}:{data['port']})")
    return jsonify({'status':'Machine ajoutée','id':len(machines)-1})

@app.route('/machine/<int:id>', methods=['DELETE'])
@roles_required('admin')
@machine_access_required
def delete_machine(id):
    machines = load_machines()
    rem = machines.pop(id)
    save_machines(machines)
    logger.info(f"➖ {current_user.id} a supprimé {rem['name']} (IP {rem['ip']}:{rem.get('port', DEFAULT_PORT)})")
    return jsonify({'status':'Machine supprimée'})

@app.route('/users', methods=['GET'])
@roles_required('admin')
def list_users():
    users = load_users()
    return jsonify([{
        'username': u['username'],
        'role':     u['role'],
        'machines': u.get('machines', [])
    } for u in users])

@app.route('/user', methods=['POST'])
@roles_required('admin')
def add_user():
    data = request.get_json() or {}
    if not all(k in data for k in ('username','password','role')):
        return jsonify({'error':'username,password,role requis'}), 400
    if data['role'] not in ROLES:
        return jsonify({'error':'Role invalide'}), 400
    users = load_users()
    if any(u['username']==data['username'] for u in users):
        return jsonify({'error':'Utilisateur existe déjà'}), 400
    users.append({
        'username': data['username'],
        'password': generate_password_hash(data['password']),
        'role':     data['role'],
        'machines': data.get('machines', [])
    })
    save_users(users)
    logger.info(f"👤 {current_user.id} a créé {data['username']} rôle {data['role']}")
    return jsonify({'status':'Utilisateur ajouté'})

@app.route('/user/<username>', methods=['DELETE'])
@roles_required('admin')
def delete_user(username):
    users = load_users()
    if username == current_user.id:
        return jsonify({'error':'Impossible de supprimer connecté'}), 400
    new = [u for u in users if u['username'] != username]
    save_users(new)
    logger.info(f"🗑️ {current_user.id} a supprimé {username}")
    return jsonify({'status':'Utilisateur supprimé'})

@app.route('/user/<username>/role', methods=['PUT'])
@roles_required('admin')
def change_role(username):
    data = request.get_json() or {}
    if data.get('role') not in ROLES:
        return jsonify({'error':'Role invalide'}), 400
    users = load_users()
    for u in users:
        if u['username']==username:
            u['role']=data['role']
            save_users(users)
            logger.info(f"🔄 {current_user.id} a changé rôle de {username} en {u['role']}")
            return jsonify({'status':'Rôle mis à jour'})
    return jsonify({'error':'Utilisateur non trouvé'}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
