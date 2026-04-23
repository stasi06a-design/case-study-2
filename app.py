from flask import Flask, request, jsonify
import logging
import os
from datetime import datetime

app = Flask(__name__)

os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    filename='logs/app.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

DB_BACKEND = os.getenv('DB_BACKEND', 'sqlite')
SQL_SERVER = os.getenv('SQL_SERVER', '')
SQL_DATABASE = os.getenv('SQL_DATABASE', '')
SQL_USERNAME = os.getenv('SQL_USERNAME', '')
SQL_PASSWORD = os.getenv('SQL_PASSWORD', '')

VALID_METRICS = ["cpu", "memory", "disk", "network_sent", "network_recv", "boot_time"]

def get_connection():
    if DB_BACKEND == 'azure_sql':
        import pyodbc
        conn_str = (
            f"DRIVER={{ODBC Driver 18 for SQL Server}};"
            f"SERVER={SQL_SERVER};"
            f"DATABASE={SQL_DATABASE};"
            f"UID={SQL_USERNAME};"
            f"PWD={SQL_PASSWORD};"
            f"Encrypt=yes;"
            f"TrustServerCertificate=no;"
        )
        return pyodbc.connect(conn_str)
    else:
        import sqlite3
        conn = sqlite3.connect('metrics.db')
        conn.row_factory = sqlite3.Row
        return conn

def init_db():
    conn = get_connection()
    if DB_BACKEND == 'azure_sql':
        cursor = conn.cursor()
        cursor.execute("""
            IF NOT EXISTS (
                SELECT * FROM sysobjects WHERE name='measurements' AND xtype='U'
            )
            CREATE TABLE measurements (
                id        INT IDENTITY(1,1) PRIMARY KEY,
                timestamp TEXT    NOT NULL,
                hostname  TEXT    NOT NULL,
                metric    TEXT    NOT NULL,
                value     FLOAT   NOT NULL,
                unit      TEXT    NOT NULL
            )
        """)
        conn.commit()
    else:
        import sqlite3
        conn.execute("""
            CREATE TABLE IF NOT EXISTS measurements (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT    NOT NULL,
                hostname  TEXT    NOT NULL,
                metric    TEXT    NOT NULL,
                value     REAL    NOT NULL,
                unit      TEXT    NOT NULL
            )
        """)
        conn.commit()
    conn.close()
    logging.info("Database initialised")

@app.route('/health', methods=['GET'])
def health():
    logging.info("Health check requested")
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.utcnow().isoformat()
    }), 200

@app.route('/metrics', methods=['POST'])
def receive_metrics():
    try:
        data = request.get_json()

        if not data:
            logging.warning("POST /metrics received empty or invalid JSON")
            return jsonify({'error': 'No JSON data provided'}), 400

        if not isinstance(data, list):
            logging.warning("POST /metrics expected a list of metric rows")
            return jsonify({'error': 'Expected a list of metric readings'}), 400

        required_fields = ['hostname', 'metric', 'value', 'unit']
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        conn = get_connection()
        cursor = conn.cursor()
        stored = 0

        for row in data:
            missing = [f for f in required_fields if f not in row]
            if missing:
                logging.warning(f"Skipping row missing fields: {missing}")
                continue

            if row['metric'] not in VALID_METRICS:
                logging.warning(f"Skipping unknown metric: {row['metric']}")
                continue

            cursor.execute(
                """INSERT INTO measurements
                   (timestamp, hostname, metric, value, unit)
                   VALUES (?, ?, ?, ?, ?)""",
                (timestamp, row['hostname'], row['metric'],
                 row['value'], row['unit'])
            )
            stored += 1

        conn.commit()
        conn.close()

        logging.info(f"Stored {stored} metric rows")
        return jsonify({
            'status': 'ok',
            'stored': stored,
            'timestamp': timestamp
        }), 201

    except Exception as e:
        logging.error(f"Error storing metrics: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/metrics', methods=['GET'])
def get_metrics():
    try:
        hostname = request.args.get('hostname')
        metric = request.args.get('metric')
        limit = request.args.get('limit', 100)

        query = """SELECT timestamp, hostname, metric, value, unit
                   FROM measurements WHERE 1=1"""
        params = []

        if hostname:
            query += " AND hostname = ?"
            params.append(hostname)
        if metric:
            if metric not in VALID_METRICS:
                return jsonify({'error': f'Unknown metric: {metric}'}), 400
            query += " AND metric = ?"
            params.append(metric)

        if DB_BACKEND == 'azure_sql':
            query = query.replace("SELECT", f"SELECT TOP {limit}")
            query += " ORDER BY timestamp DESC"
        else:
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        results = []
        for row in rows:
            results.append({
                'timestamp': row[0],
                'hostname': row[1],
                'metric': row[2],
                'value': row[3],
                'unit': row[4]
            })

        logging.info(f"GET /metrics returned {len(results)} records")
        return jsonify({'count': len(results), 'measurements': results}), 200

    except Exception as e:
        logging.error(f"Error retrieving metrics: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    init_db()
    logging.info("Starting KH Monitoring API")
    app.run(host='0.0.0.0', port=8000, debug=False)