import sqlite3
import os
from datetime import datetime

DB_NAME = "peucar_data.db"

class OrdersManager:
    def __init__(self):
        self.conn = sqlite3.connect(DB_NAME, check_same_thread=False)
        self._create_tables()

    def _create_tables(self):
        cursor = self.conn.cursor()
        
        # Table: Pedidos
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pedidos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT,
                proveedor TEXT,
                estado TEXT DEFAULT 'Pendiente'
            )
        ''')
        
        # Table: Items
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pedido_id INTEGER,
                codigo TEXT,
                cantidad_pedida REAL,
                cantidad_entregada REAL DEFAULT 0,
                FOREIGN KEY (pedido_id) REFERENCES pedidos (id)
            )
        ''')
        
        # Table: Estado (as requested, though we use a column in pedidos too)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS estados (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT UNIQUE
            )
        ''')
        
        # Seed basic states
        for state in ['Pendiente', 'Parcial', 'Completado']:
            cursor.execute('INSERT OR IGNORE INTO estados (nombre) VALUES (?)', (state,))
            
        self.conn.commit()

    def add_order(self, fecha: str, proveedor: str, items: list):
        """
        items should be a list of tuples: (codigo, cantidad)
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute('INSERT INTO pedidos (fecha, proveedor) VALUES (?, ?)', (fecha, proveedor))
            pedido_id = cursor.lastrowid
            
            for codigo, cantidad in items:
                cursor.execute('''
                    INSERT INTO items (pedido_id, codigo, cantidad_pedida)
                    VALUES (?, ?, ?)
                ''', (pedido_id, codigo, cantidad))
            
            self.conn.commit()
            return pedido_id
        except Exception as e:
            self.conn.rollback()
            raise e

    def get_orders(self):
        """Returns all orders with their items."""
        cursor = self.conn.cursor()
        cursor.execute('SELECT id, fecha, proveedor, estado FROM pedidos ORDER BY id DESC')
        orders = cursor.fetchall()
        
        detailed_orders = []
        for o in orders:
            order_id = o[0]
            cursor.execute('SELECT id, codigo, cantidad_pedida, cantidad_entregada FROM items WHERE pedido_id = ?', (order_id,))
            items = cursor.fetchall()
            detailed_orders.append({
                "id": o[0],
                "fecha": o[1],
                "proveedor": o[2],
                "estado": o[3],
                "items": items
            })
        return detailed_orders

    def update_order_status(self, proveedor: str, codigo: str, cantidad: float):
        """
        Busca el pedido pendiente más antiguo de ese proveedor y código,
        y suma la cantidad a cantidad_entregada.
        """
        from main import normalize_id # We use the same normalization
        
        cursor = self.conn.cursor()
        # Find all pending/partial orders for this provider
        cursor.execute('''
            SELECT p.id, i.id, i.cantidad_pedida, i.cantidad_entregada, i.codigo
            FROM pedidos p
            JOIN items i ON p.id = i.pedido_id
            WHERE p.proveedor LIKE ? AND p.estado != 'Completado'
            ORDER BY p.id ASC
        ''', (f"%{proveedor}%",))
        
        rows = cursor.fetchall()
        remaining_to_add = cantidad
        
        for p_id, i_id, q_pedida, q_entregada, item_code in rows:
            if remaining_to_add <= 0:
                break
            
            # Use normalization to match codes (flexible matching)
            if normalize_id(item_code) == normalize_id(codigo):
                still_needed = q_pedida - q_entregada
                if still_needed > 0:
                    add_now = min(remaining_to_add, still_needed)
                    new_delivered = q_entregada + add_now
                    cursor.execute('UPDATE items SET cantidad_entregada = ? WHERE id = ?', (new_delivered, i_id))
                    remaining_to_add -= add_now
                    
                    # Update order status if all items are delivered
                    self._check_and_update_order_state(p_id)

        self.conn.commit()
        return remaining_to_add == 0 # True if fully fulfilled

    def _check_and_update_order_state(self, pedido_id: int):
        cursor = self.conn.cursor()
        cursor.execute('SELECT cantidad_pedida, cantidad_entregada FROM items WHERE pedido_id = ?', (pedido_id,))
        items = cursor.fetchall()
        
        total_items = len(items)
        completed_items = sum(1 for p, d in items if d >= p)
        delivered_anything = sum(1 for p, d in items if d > 0)
        
        if completed_items == total_items:
            new_state = "Completado"
        elif delivered_anything > 0:
            new_state = "Parcial"
        else:
            new_state = "Pendiente"
            
        cursor.execute('UPDATE pedidos SET estado = ? WHERE id = ?', (new_state, pedido_id))

    def delete_order(self, pedido_id: int):
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM items WHERE pedido_id = ?', (pedido_id,))
        cursor.execute('DELETE FROM pedidos WHERE id = ?', (pedido_id,))
        self.conn.commit()

    def update_order(self, pedido_id: int, fecha: str, proveedor: str, items: list):
        """
        Updates an order's header and completely replaces its items.
        items: list of tuples (codigo, cantidad_pedida, cantidad_entregada)
        """
        cursor = self.conn.cursor()
        try:
            # Update header
            cursor.execute('''
                UPDATE pedidos SET fecha = ?, proveedor = ? WHERE id = ?
            ''', (fecha, proveedor, pedido_id))
            
            # Replace items: simplest way is to delete and re-insert 
            # (assuming we want to keep current delivered counts if passed in items)
            cursor.execute('DELETE FROM items WHERE pedido_id = ?', (pedido_id,))
            
            for codigo, q_pedida, q_entregada in items:
                cursor.execute('''
                    INSERT INTO items (pedido_id, codigo, cantidad_pedida, cantidad_entregada)
                    VALUES (?, ?, ?, ?)
                ''', (pedido_id, codigo, q_pedida, q_entregada))
            
            # Re-check state 
            self._check_and_update_order_state(pedido_id)
            
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            raise e
