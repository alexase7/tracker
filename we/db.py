import sqlite3
from .config import DB_FILE


class DB:
    def __init__(self, path=DB_FILE):
        self.conn = sqlite3.connect(path)
        self.conn.execute("PRAGMA foreign_keys = ON;")
        self.init_db()

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass

    def init_db(self):
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS ingredients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                unit TEXT NOT NULL,
                pack_qty REAL NOT NULL,
                pack_price REAL NOT NULL
            );
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            );
            """
        )
        cur.execute("PRAGMA table_info(products);")
        cols = [r[1] for r in cur.fetchall()]
        if "sale_price" not in cols:
            cur.execute("ALTER TABLE products ADD COLUMN sale_price REAL;")

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS product_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                ingredient_id INTEGER NOT NULL,
                qty REAL NOT NULL,
                FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE,
                FOREIGN KEY(ingredient_id) REFERENCES ingredients(id) ON DELETE RESTRICT
            );
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS product_slot_lines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                slot_name TEXT NOT NULL,
                qty REAL NOT NULL,
                FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE
            );
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS product_slot_selection (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                slot_name TEXT NOT NULL,
                ingredient_id INTEGER NOT NULL,
                UNIQUE(product_id, slot_name),
                FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE,
                FOREIGN KEY(ingredient_id) REFERENCES ingredients(id) ON DELETE RESTRICT
            );
            """
        )
        self.conn.commit()

    # ---------- Ingredients ----------
    def list_ingredients(self):
        cur = self.conn.cursor()
        cur.execute("SELECT id, name, unit, pack_qty, pack_price FROM ingredients ORDER BY name;")
        return cur.fetchall()

    def upsert_ingredient(self, name, unit, pack_qty, pack_price):
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO ingredients(name, unit, pack_qty, pack_price)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET unit=excluded.unit, pack_qty=excluded.pack_qty, pack_price=excluded.pack_price;
            """,
            (name, unit, pack_qty, pack_price),
        )
        self.conn.commit()

    def delete_ingredient(self, ing_id: int):
        cur = self.conn.cursor()
        cur.execute("DELETE FROM ingredients WHERE id=?;", (ing_id,))
        self.conn.commit()

    def ingredient_is_used(self, ing_id: int):
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM product_items WHERE ingredient_id=?;", (ing_id,))
        used_items = cur.fetchone()[0] > 0
        cur.execute("SELECT COUNT(*) FROM product_slot_selection WHERE ingredient_id=?;", (ing_id,))
        used_slots = cur.fetchone()[0] > 0
        return used_items or used_slots

    def get_ingredient_unit_by_name(self, name: str):
        cur = self.conn.cursor()
        cur.execute("SELECT unit FROM ingredients WHERE name=?;", (name,))
        r = cur.fetchone()
        return r[0] if r else None

    def get_ingredient_id_by_name(self, name: str):
        cur = self.conn.cursor()
        cur.execute("SELECT id FROM ingredients WHERE name=?;", (name,))
        r = cur.fetchone()
        return int(r[0]) if r else None

    def list_ingredient_names(self):
        cur = self.conn.cursor()
        cur.execute("SELECT name FROM ingredients ORDER BY name;")
        return [r[0] for r in cur.fetchall()]

    # ---------- Products ----------
    def list_products(self):
        cur = self.conn.cursor()
        cur.execute("SELECT id, name, sale_price FROM products;")
        return cur.fetchall()

    def upsert_product(self, name: str):
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO products(name)
            VALUES (?)
            ON CONFLICT(name) DO UPDATE SET name=excluded.name;
            """,
            (name,),
        )
        self.conn.commit()

    def delete_product(self, pid: int):
        self.conn.execute("DELETE FROM products WHERE id=?;", (pid,))
        self.conn.commit()

    def get_product_name(self, pid: int):
        cur = self.conn.cursor()
        cur.execute("SELECT name FROM products WHERE id=?;", (pid,))
        r = cur.fetchone()
        return r[0] if r else None

    def set_sale_price(self, pid: int, price_or_none):
        self.conn.execute("UPDATE products SET sale_price=? WHERE id=?;", (price_or_none, pid))
        self.conn.commit()

    def get_sale_price(self, pid: int):
        cur = self.conn.cursor()
        cur.execute("SELECT sale_price FROM products WHERE id=?;", (pid,))
        r = cur.fetchone()
        return (float(r[0]) if (r and r[0] is not None) else None)

    # ---------- Recipe Items ----------
    def add_product_item(self, pid: int, ing_id: int, qty: float):
        self.conn.execute(
            "INSERT INTO product_items(product_id, ingredient_id, qty) VALUES (?, ?, ?);",
            (pid, ing_id, qty),
        )
        self.conn.commit()

    def delete_product_item(self, item_id: int):
        self.conn.execute("DELETE FROM product_items WHERE id=?;", (item_id,))
        self.conn.commit()

    def list_product_items(self, pid: int):
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT pi.id, i.name, pi.qty, i.unit, i.pack_qty, i.pack_price
            FROM product_items pi
            JOIN ingredients i ON i.id = pi.ingredient_id
            WHERE pi.product_id = ?
            ORDER BY i.name;
            """,
            (pid,),
        )
        return cur.fetchall()

    # ---------- Slot templates ----------
    def add_slot_line(self, pid: int, slot_name: str, qty: float):
        self.conn.execute(
            "INSERT INTO product_slot_lines(product_id, slot_name, qty) VALUES (?, ?, ?);",
            (pid, slot_name, qty),
        )
        self.conn.commit()

    def delete_slot_line(self, line_id: int):
        self.conn.execute("DELETE FROM product_slot_lines WHERE id=?;", (line_id,))
        self.conn.commit()

    def list_slot_lines(self, pid: int):
        cur = self.conn.cursor()
        cur.execute(
            "SELECT id, slot_name, qty FROM product_slot_lines WHERE product_id=? ORDER BY slot_name;",
            (pid,),
        )
        return cur.fetchall()

    def list_distinct_slots(self, pid: int):
        cur = self.conn.cursor()
        cur.execute("SELECT DISTINCT slot_name FROM product_slot_lines WHERE product_id=? ORDER BY slot_name;", (pid,))
        return [r[0] for r in cur.fetchall()]

    def set_slot_selection(self, pid: int, slot_name: str, ing_id: int):
        self.conn.execute(
            """
            INSERT INTO product_slot_selection(product_id, slot_name, ingredient_id)
            VALUES (?, ?, ?)
            ON CONFLICT(product_id, slot_name) DO UPDATE SET ingredient_id=excluded.ingredient_id;
            """,
            (pid, slot_name, ing_id),
        )
        self.conn.commit()

    def get_slot_selection_name(self, pid: int, slot_name: str):
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT i.name
            FROM product_slot_selection s
            JOIN ingredients i ON i.id = s.ingredient_id
            WHERE s.product_id=? AND s.slot_name=?;
            """,
            (pid, slot_name),
        )
        r = cur.fetchone()
        return r[0] if r else None

    def get_slot_selection_price_unit(self, pid: int, slot_name: str):
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT i.name, i.unit, i.pack_qty, i.pack_price
            FROM product_slot_selection s
            JOIN ingredients i ON i.id = s.ingredient_id
            WHERE s.product_id=? AND s.slot_name=?;
            """,
            (pid, slot_name),
        )
        return cur.fetchone()

    # ---------- Cost computation ----------
    def compute_product_cost(self, pid: int):
        cur = self.conn.cursor()
        total = 0.0

        cur.execute(
            """
            SELECT pi.qty, i.pack_qty, i.pack_price
            FROM product_items pi
            JOIN ingredients i ON i.id = pi.ingredient_id
            WHERE pi.product_id = ?;
            """,
            (pid,),
        )
        for qty, pack_qty, pack_price in cur.fetchall():
            unit_price = (pack_price / pack_qty) if pack_qty else 0.0
            total += unit_price * qty

        for _line_id, slot_name, qty in self.list_slot_lines(pid):
            r = self.get_slot_selection_price_unit(pid, slot_name)
            if not r:
                continue
            _name, _unit, pack_qty, pack_price = r
            unit_price = (pack_price / pack_qty) if pack_qty else 0.0
            total += unit_price * qty

        return total