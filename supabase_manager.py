import os
import re
from supabase import create_client, Client
from datetime import datetime

class SupabaseManager:
    """
    Mirror of OrdersManager but using Supabase as the backend.
    """
    def __init__(self):
        # Load from mobile-app/.env.local if present
        env_path = os.path.join(os.path.dirname(__file__), "mobile-app", ".env.local")
        url, key = None, None
        if os.path.exists(env_path):
            try:
                with open(env_path, "r") as f:
                    for line in f:
                        if '=' in line:
                            k, v = line.split('=', 1)
                            if 'URL' in k: url = v.strip().strip("'").strip('"')
                            if 'KEY' in k: key = v.strip().strip("'").strip('"')
            except Exception as e:
                print(f"[ERROR] Leyendo .env.local: {e}")

        # Fallback to env vars
        url = url or os.environ.get("SUPABASE_URL")
        key = key or os.environ.get("SUPABASE_KEY")
        
        if not url or not key:
            print("[WARN] Supabase credentials missing. Cloud sync disabled.")
            self.client = None
            return
        
        try:
            self.client: Client = create_client(url, key)
            print(f"[STATUS] Conectado a Supabase: {url}")
        except Exception as e:
            print(f"[ERROR] Falló conexión a Supabase: {e}")
            self.client = None

    def add_order(self, fecha: str, proveedor: str, items: list):
        """
        items should be a list of tuples: (codigo, q_pedida, [q_entregada])
        """
        if not self.client: return None
        
        try:
            # 1. Insert Order
            res = self.client.table("pedidos").insert({
                "fecha": fecha,
                "proveedor": proveedor,
                "repuesto": proveedor # Satisfacer restricción NOT NULL
            }).execute()
            
            pedido_id = res.data[0]['id']
            
            # 2. Insert Items
            items_to_insert = []
            for item in items:
                code = str(item[0]).upper()
                qp = item[1]
                qe = item[2] if len(item) > 2 else 0
                items_to_insert.append({
                    "pedido_id": pedido_id,
                    "codigo": code,
                    "cantidad_pedida": qp,
                    "cantidad_entregada": qe
                })
            
            self.client.table("items").insert(items_to_insert).execute()
            
            # 3. Update status if some items arrived
            self._check_and_update_state(pedido_id)
            
            return pedido_id
        except Exception as e:
            print(f"[ERROR] Supabase add_order: {e}")
            raise e

    def get_orders(self):
        if not self.client: return []
        
        try:
            # Get all orders with items
            res = self.client.table("pedidos").select("*, items(*)").order("id", desc=True).execute()
            
            orders = []
            for o in res.data:
                orders.append({
                    "id": o['id'],
                    "fecha": o['fecha'],
                    "proveedor": o['proveedor'],
                    "repuesto": o.get('repuesto', ''), # New field
                    "estado": o['estado'],
                    "items": [(i['id'], i['codigo'], i['cantidad_pedida'], i['cantidad_entregada']) for i in o['items']]
                })
            return orders
        except Exception as e:
            print(f"[ERROR] Supabase get_orders: {e}")
            return []

    def update_order_status(self, proveedor: str, item_desc_or_code: str, cantidad: float):
        """
        Mirror logic: finds pending orders of the provider and updates delivered quantity.
        """
        if not self.client: return False
        
        try:
            # Find candidate orders
            res = self.client.table("pedidos").select("*, items(*)").ilike("proveedor", f"%{proveedor}%").neq("estado", "Completado").order("id", desc=False).execute()
            
            remaining = cantidad
            for order in res.data:
                if remaining <= 0: break
                
                updated_anything = False
                for item in order['items']:
                    # Simple matching for now
                    if item_desc_or_code.upper() in item['codigo'].upper():
                        still_needed = item['cantidad_pedida'] - item['cantidad_entregada']
                        if still_needed > 0:
                            add_now = min(remaining, still_needed)
                            new_delivered = item['cantidad_entregada'] + add_now
                            
                            self.client.table("items").update({"cantidad_entregada": new_delivered}).eq("id", item['id']).execute()
                            remaining -= add_now
                            updated_anything = True
                
                if updated_anything:
                    self._check_and_update_state(order['id'])
            
            return remaining == 0
        except Exception as e:
            print(f"[ERROR] Supabase update_order_status: {e}")
            return False

    def _check_and_update_state(self, pedido_id: int):
        # Obtain current state to preserve 'Enviado'
        res_ped = self.client.table("pedidos").select("estado").eq("id", pedido_id).execute()
        current_state = res_ped.data[0]["estado"] if res_ped.data else "Pendiente"

        res = self.client.table("items").select("cantidad_pedida, cantidad_entregada").eq("pedido_id", pedido_id).execute()
        items = res.data
        
        total = len(items)
        completed = sum(1 for i in items if i['cantidad_entregada'] >= i['cantidad_pedida'])
        any_delivered = sum(1 for i in items if i['cantidad_entregada'] > 0)
        
        new_state = "Completado" if completed == total else ("Parcial" if any_delivered > 0 else "Pendiente")
        
        if new_state == "Pendiente" and current_state.capitalize() == "Enviado":
            new_state = "Enviado"

        self.client.table("pedidos").update({"estado": new_state}).eq("id", pedido_id).execute()

    def update_order(self, pedido_id: int, fecha: str, proveedor: str, items: list):
        """
        updates order header and replaces items.
        items: list of (codigo, q_pedida, [q_entregada])
        """
        if not self.client: return
        
        try:
            # 1. Update Header
            self.client.table("pedidos").update({
                "fecha": fecha,
                "proveedor": proveedor,
                "repuesto": proveedor # Satisfacer restricción NOT NULL
            }).eq("id", pedido_id).execute()
            
            # 2. Delete existing items
            self.client.table("items").delete().eq("pedido_id", pedido_id).execute()
            
            # 3. Insert new items
            items_to_insert = []
            for item in items:
                # Si el item viene de la UI del PC puede tener 3 o 4 elementos
                # (id, codigo, qp, qe)
                code = item[1] if isinstance(item[0], int) else item[0]
                qp = item[2] if isinstance(item[0], int) else item[1]
                qe = item[3] if isinstance(item[0], int) else (item[2] if len(item) > 2 else 0)
                
                items_to_insert.append({
                    "pedido_id": pedido_id,
                    "codigo": str(code).upper(),
                    "cantidad_pedida": qp,
                    "cantidad_entregada": qe
                })
            
            if items_to_insert:
                self.client.table("items").insert(items_to_insert).execute()
            
            # 4. Refresh State
            self._check_and_update_state(pedido_id)
        except Exception as e:
            print(f"[ERROR] Supabase update_order: {e}")
            raise e

    def delete_order(self, pedido_id: int):
        if self.client:
            self.client.table("pedidos").delete().eq("id", pedido_id).execute()

    # History Sync
    def save_history_record(self, record_tuple, items_json, totals_json):
        if not self.client: return
        prov, nro, fec, monto, estado, is_remito, link_id = record_tuple
        try:
            self.client.table("documentos_historia").insert({
                "proveedor": prov,
                "documento_id": nro,
                "fecha": fec,
                "monto": monto,
                "estado": estado,
                "is_remito": is_remito,
                "remito_vinculado": link_id,
                "items_json": items_json,
                "totals_json": totals_json
            }).execute()
        except Exception as e:
            print(f"[ERROR] Supabase sync history: {e}")

    def get_history(self):
        if not self.client: return [], {}, {}
        res = self.client.table("documentos_historia").select("*").order("created_at", desc=True).execute()
        history = []
        items_dict = {}
        totals_dict = {}
        for r in res.data:
            record = (r['proveedor'], r['documento_id'], r['fecha'], r['monto'], r['estado'], r['is_remito'], r['remito_vinculado'])
            history.append(record)
            items_dict[r['documento_id']] = r['items_json']
            totals_dict[r['documento_id']] = r['totals_json']
        return history, items_dict, totals_dict

    # OCR Tasks Bridge
    def get_pending_ocr_tasks(self):
        if not self.client: return []
        try:
            res = self.client.table("ocr_tasks").select("*").eq("status", "pending").execute()
            return res.data
        except Exception as e:
            print(f"[ERROR] Supabase get_pending_ocr_tasks: {e}")
            return []

    def update_ocr_task(self, task_id: str, status: str, result_json: dict = None, error_msg: str = None):
        if not self.client: return
        try:
            update_data = {"status": status}
            if result_json: update_data["result_json"] = result_json
            if error_msg: update_data["error_msg"] = error_msg
            self.client.table("ocr_tasks").update(update_data).eq("id", task_id).execute()
        except Exception as e:
            print(f"[ERROR] Supabase update_ocr_task: {e}")

    def get_completed_ocr_tasks(self):
        """Fetches tasks that are completed but not yet imported/archived."""
        if not self.client: return []
        try:
            res = self.client.table("ocr_tasks").select("*").eq("status", "completed").execute()
            return res.data
        except Exception as e:
            print(f"[ERROR] Supabase get_completed_ocr_tasks: {e}")
            return []

    def delete_ocr_task(self, task_id: str):
        if not self.client: return
        try:
            self.client.table("ocr_tasks").delete().eq("id", task_id).execute()
        except Exception as e:
            print(f"[ERROR] Supabase delete_ocr_task: {e}")

    def download_scan_image(self, storage_path: str, local_dest: str):
        if not self.client: return
        try:
            # storage_path is the relative path in the 'scans' bucket
            with open(local_dest, 'wb+') as f:
                res = self.client.storage.from_('scans').download(storage_path)
                f.write(res)
            return True
        except Exception as e:
            print(f"[ERROR] Supabase download image: {e}")
            return False
