import http.server
import socketserver
import sqlite3
import json
import urllib.parse
import os

PORT = int(os.environ.get("PORT", 8080))
DB_FILE = "tienda.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Catalog table with image_url
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS catalog (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            categoria TEXT NOT NULL,
            precio REAL NOT NULL,
            descripcion TEXT NOT NULL,
            image_url TEXT
        )
    ''')

    # Orders table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id TEXT PRIMARY KEY,
            cliente TEXT NOT NULL,
            telefono TEXT NOT NULL,
            prenda TEXT NOT NULL,
            fecha TEXT NOT NULL,
            total REAL NOT NULL,
            adelanto REAL NOT NULL,
            estado TEXT NOT NULL,
            notas TEXT
        )
    ''')

    # Insert sample data if empty
    cursor.execute("SELECT COUNT(*) FROM catalog")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("INSERT INTO catalog (nombre, categoria, precio, descripcion, image_url) VALUES (?, ?, ?, ?, ?)", [
            ("Detente para Cargo de Honor", "detentes", 45.00, "Confeccionado en terciopelo fino, bordado con hilos metálicos dorados e hilos de seda. Ideal para mayordomías.", "https://images.unsplash.com/photo-1579783902614-a3fb3927b675?auto=format&fit=crop&w=600&q=80"),
            ("Estandarte Religioso con Flecos", "estandartes", 180.00, "Estandarte patronal con imagen bordada a alta definición, flecos dorados importados y varilla superior.", "https://images.unsplash.com/photo-1513519245088-0e12902e5a38?auto=format&fit=crop&w=600&q=80"),
            ("Ajustes, Ruedos y Entallados", "costura", 15.00, "Servicio profesional de costura para pantalones, sacos, vestidos y arreglos en general con entrega puntual.", "https://images.unsplash.com/photo-1558769132-cb1aea458c5e?auto=format&fit=crop&w=600&q=80")
        ])

    cursor.execute("SELECT COUNT(*) FROM orders")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("INSERT INTO orders (id, cliente, telefono, prenda, fecha, total, adelanto, estado, notas) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", [
            ("PED-001", "Juan Quispe", "945123456", "Detente para Cargo (Terciopelo bordado)", "2026-11-02", 45.00, 20.00, "en_proceso", "Trabajando bordado dorado."),
            ("PED-002", "Hermandad del Señor de los Milagros", "988765432", "Estandarte Institucional con Flecos", "2026-11-05", 220.00, 100.00, "pendiente", "Esperando confirmación de diseño."),
            ("PED-003", "Carmen Rosa", "912345678", "Ajuste de saco y ruedo de pantalón", "2026-10-30", 25.00, 25.00, "listo", "¡Terminado para recoger!")
        ])

    conn.commit()
    conn.close()

class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True

class TallerHTTPRequestHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query_params = urllib.parse.parse_qs(parsed_url.query)

        if path == "/" or path == "/catalogo":
            self.serve_file("templates/catalogo.html", "text/html")
        elif path == "/seguimiento":
            self.serve_file("templates/seguimiento.html", "text/html")
        elif path == "/admin":
            self.serve_file("templates/admin.html", "text/html")

        # API Endpoints
        elif path == "/api/catalog":
            self.send_json(self.get_catalog())
        elif path == "/api/orders":
            self.send_json(self.get_orders())
        elif path == "/api/search":
            q = query_params.get("q", [""])[0]
            self.send_json(self.search_orders(q))
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"404 Not Found")

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode('utf-8')) if content_length > 0 else {}

        path = self.path
        if path == "/api/catalog":
            self.add_catalog(data)
        elif path == "/api/orders":
            self.add_order(data)
        elif path == "/api/orders/status":
            self.update_order_status(data)
        else:
            self.send_response(404)
            self.end_headers()

    def do_DELETE(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query_params = urllib.parse.parse_qs(parsed_url.query)

        if path == "/api/catalog":
            item_id = query_params.get("id", [None])[0]
            if item_id:
                self.delete_catalog(int(item_id))
            else:
                self.send_response(400)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def serve_file(self, filepath, content_type):
        if os.path.exists(filepath):
            self.send_response(200)
            self.send_header("Content-Type", content_type + "; charset=utf-8")
            self.end_headers()
            with open(filepath, "rb") as f:
                self.wfile.write(f.read())
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(f"File {filepath} not found".encode('utf-8'))

    def send_json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    # DB Operations
    def get_catalog(self):
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM catalog")
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows

    def add_catalog(self, data):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO catalog (nombre, categoria, precio, descripcion, image_url) VALUES (?, ?, ?, ?, ?)",
                       (data.get("nombre"), data.get("categoria"), data.get("precio"), data.get("descripcion"), data.get("image_url", "")))
        conn.commit()
        conn.close()
        self.send_json({"success": True})

    def delete_catalog(self, item_id):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM catalog WHERE id = ?", (item_id,))
        conn.commit()
        conn.close()
        self.send_json({"success": True})

    def get_orders(self):
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orders")
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows

    def add_order(self, data):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM orders")
        count = cursor.fetchone()[0] + 1
        new_id = f"PED-{count:03d}"

        cursor.execute("INSERT INTO orders (id, cliente, telefono, prenda, fecha, total, adelanto, estado, notas) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                       (new_id, data.get("cliente"), data.get("telefono"), data.get("prenda"), data.get("fecha"), data.get("total"), data.get("adelanto"), "pendiente", data.get("notas", "")))
        conn.commit()
        conn.close()
        self.send_json({"success": True, "id": new_id})

    def update_order_status(self, data):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("UPDATE orders SET estado = ? WHERE id = ?", (data.get("estado"), data.get("id")))
        conn.commit()
        conn.close()
        self.send_json({"success": True})

    def search_orders(self, q):
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orders WHERE cliente LIKE ? OR telefono LIKE ? OR id LIKE ?", (f"%{q}%", f"%{q}%", f"%{q}%"))
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows

if __name__ == "__main__":
    init_db()
    server = ThreadingHTTPServer(("0.0.0.0", PORT), TallerHTTPRequestHandler)
    print(f"Servidor iniciado en el puerto {PORT}")
    server.serve_forever()
