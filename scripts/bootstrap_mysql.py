"""One-time local MySQL bootstrap; never prints credentials."""
from pathlib import Path
import json
import secrets
from urllib.parse import quote
import pymysql

ROOT = Path(__file__).resolve().parents[1]
secrets_path = ROOT / 'data' / 'mysql-credentials.json'
if secrets_path.exists():
    raise SystemExit('Credentials already initialized; no changes made.')
conn = pymysql.connect(host='127.0.0.1', port=3306, user='root', password='', autocommit=True)
root_secret = secrets.token_urlsafe(32)
app_secret = secrets.token_urlsafe(32)
with conn.cursor() as cur:
    cur.execute("ALTER USER 'root'@'localhost' IDENTIFIED BY %s", (root_secret,))
    cur.execute('CREATE DATABASE IF NOT EXISTS studymind CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
    cur.execute("CREATE USER 'studymind'@'localhost' IDENTIFIED BY %s", (app_secret,))
    cur.execute("GRANT ALL PRIVILEGES ON studymind.* TO 'studymind'@'localhost'")
    cur.execute("CREATE USER 'studymind'@'127.0.0.1' IDENTIFIED BY %s", (app_secret,))
    cur.execute("GRANT ALL PRIVILEGES ON studymind.* TO 'studymind'@'127.0.0.1'")
secrets_path.write_text(json.dumps({'root_password': root_secret, 'app_password': app_secret}), encoding='utf-8')
url = f'mysql+pymysql://studymind:{quote(app_secret)}@127.0.0.1:3306/studymind?charset=utf8mb4'
(ROOT / 'backend' / '.env').write_text('DATABASE_URL=' + url + '\nSTUDYMIND_DATA_DIR=E:/StudyMindAI/data\n', encoding='utf-8')
conn.close()
conn = pymysql.connect(host='127.0.0.1', port=3306, user='studymind', password=app_secret, database='studymind')
with conn.cursor() as cur:
    cur.execute('SELECT VERSION(), DATABASE()')
    version, database = cur.fetchone()
    print(json.dumps({'status': 'ok', 'database': database, 'version': version, 'app_connection': True}))
conn.close()
