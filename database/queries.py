import streamlit as st
from supabase import create_client, Client
from datetime import datetime

@st.cache_resource
def get_supabase() -> Client:
    try:
        return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])
    except Exception as e:
        return None

supabase = get_supabase()

# FUNCIONES AUXILIARES 

def crear_producto(nombre, categoria):
    try:
        sku_auto = f"NEW-{int(datetime.now().timestamp())}"
        res = supabase.table("productos").insert({
            "sku_codigo": sku_auto, "nombre_comercial": nombre.upper().strip(),
            "unidad_medida": "Unidad", "descripcion": f"Cat: {categoria.upper()}",
            "categoria": categoria.upper().strip()
        }).execute()
        return res.data[0]['id'] if res.data else None
    except: return None

def editar_producto(producto_id, nuevo_nombre, nueva_categoria):
    try:
        supabase.table("productos").update({
            "nombre_comercial": nuevo_nombre.upper().strip(),
            "categoria": nueva_categoria.upper().strip()
        }).eq("id", producto_id).execute()
        return True
    except: return False

# 1. INGRESOS
def registrar_ingreso(producto_id, lote, cantidad, ubicacion_id, usuario, fecha_venc, senasa, gtin, motivo_ingreso):
    try:
        lote_upper = lote.strip().upper()
        res = supabase.table("lotes_stock").select("*").eq("producto_id", producto_id).eq("numero_lote", lote_upper).eq("ubicacion_id", ubicacion_id).execute()
        
        lote_id_final = None
        if res.data:
            lote_id_final = res.data[0]['id']
            nueva_cant = float(res.data[0]['cantidad_actual']) + cantidad
            supabase.table("lotes_stock").update({
                "cantidad_actual": nueva_cant, "senasa_codigo": senasa, "gtin_codigo": gtin
            }).eq("id", lote_id_final).execute()
        else:
            datos_lote = {
                "producto_id": producto_id, "ubicacion_id": ubicacion_id,
                "numero_lote": lote_upper, "cantidad_actual": cantidad,
                "fecha_vencimiento": str(fecha_venc), "senasa_codigo": senasa.upper(),
                "gtin_codigo": gtin.upper(), "estado_calidad": "DISPONIBLE"
            }
            res_insert = supabase.table("lotes_stock").insert(datos_lote).execute()
            if res_insert.data: lote_id_final = res_insert.data[0]['id']

        if lote_id_final:
            supabase.table("historial_movimientos").insert({
                "producto_id": producto_id, "lote_id": lote_id_final, "tipo_movimiento": "INGRESO",
                "cantidad_afectada": cantidad, "origen_destino": motivo_ingreso.upper(),
                "usuario_operador": usuario, "estado_confirmacion": "TERMINADO",
                "observaciones": f"SENASA: {senasa} | GTIN: {gtin}"
            }).execute()
            return True
        return False
    except: return False

# 2. ÓRDENES
def crear_orden_pendiente(items_carrito, destino, usuario):
    try:
        pedido_id = f"PED-{int(datetime.now().timestamp())}"
        for item in items_carrito:
            supabase.table("historial_movimientos").insert({
                "id_pedido_referencia": pedido_id, "producto_id": item['producto_id'],
                "lote_id": item['lote_id'], "tipo_movimiento": "EGRESO_VENTA",
                "cantidad_afectada": item['cantidad'] * -1, "origen_destino": destino.upper(),
                "usuario_operador": usuario, "estado_confirmacion": "PENDIENTE",
                "observaciones": item['detalle_bultos']
            }).execute()
        return pedido_id
    except: return None

# 3. VALIDACIÓN
def confirmar_despacho_real(movimiento_id, lote_real_id, cantidad_real, usuario, es_cruce=False, es_parcial=False, cant_original=0):
    try:
        obs = "Validado OK"
        if es_cruce: obs = "⚠️ CRUCE DE PARTIDA"
        if es_parcial: obs += " | DESPACHO PARCIAL"

        supabase.table("historial_movimientos").update({
            "lote_id": lote_real_id, "cantidad_afectada": cantidad_real * -1,
            "estado_confirmacion": "TERMINADO", "observaciones": obs, "fecha_hora": datetime.now().isoformat()
        }).eq("id", movimiento_id).execute()

        lote_res = supabase.table("lotes_stock").select("cantidad_actual").eq("id", lote_real_id).execute()
        if lote_res.data:
            nueva = float(lote_res.data[0]['cantidad_actual']) - cantidad_real
            supabase.table("lotes_stock").update({"cantidad_actual": nueva}).eq("id", lote_real_id).execute()

        if es_parcial and cant_original > cantidad_real:
            saldo = cant_original - cantidad_real
            mov_orig = supabase.table("historial_movimientos").select("*").eq("id", movimiento_id).execute().data[0]
            supabase.table("historial_movimientos").insert({
                "id_pedido_referencia": mov_orig['id_pedido_referencia'],
                "producto_id": mov_orig['producto_id'], "lote_id": mov_orig['lote_id'],
                "tipo_movimiento": "EGRESO_VENTA", "cantidad_afectada": saldo * -1,
                "origen_destino": mov_orig['origen_destino'], "usuario_operador": usuario,
                "estado_confirmacion": "PENDIENTE", "observaciones": "SALDO RESTANTE (Split)"
            }).execute()
        return True
    except: return False

# --- 4. ZAMPING ---
def mover_pallet(lote_id, nueva_u, usuario):
    try:
        supabase.table("lotes_stock").update({"ubicacion_id": nueva_u}).eq("id", lote_id).execute()
        return True
    except: return False

# --- 5. CORRECCIÓN TOTAL ---
def corregir_movimiento(movimiento_id, lote_id, nuevo_lote, nueva_cantidad, nueva_venc, nuevo_senasa, nuevo_gtin, usuario):
    """
    Corrige TODO: Cantidad, Lote, Vencimiento, SENASA y GTIN.
    """
    try:
        # 1. Obtener datos viejos para ajustar cantidad
        mov_viejo = supabase.table("historial_movimientos").select("cantidad_afectada").eq("id", movimiento_id).execute()
        cant_vieja = float(mov_viejo.data[0]['cantidad_afectada'])
        
        # 2. Actualizar Historial
        supabase.table("historial_movimientos").update({
            "cantidad_afectada": nueva_cantidad,
            "observaciones": f"Corregido por {usuario} (Antes: {cant_vieja})",
            "fecha_hora": datetime.now().isoformat()
        }).eq("id", movimiento_id).execute()

        # 3. Actualizar Lote de Stock (Datos Críticos)
        diferencia = nueva_cantidad - cant_vieja
        
        stock_res = supabase.table("lotes_stock").select("cantidad_actual").eq("id", lote_id).execute()
        if stock_res.data:
            stock_actual = float(stock_res.data[0]['cantidad_actual'])
            supabase.table("lotes_stock").update({
                "numero_lote": nuevo_lote.upper().strip(),
                "fecha_vencimiento": str(nueva_venc),
                "cantidad_actual": stock_actual + diferencia,
                "senasa_codigo": nuevo_senasa.upper().strip(), # <--- NUEVO
                "gtin_codigo": nuevo_gtin.upper().strip()      # <--- NUEVO
            }).eq("id", lote_id).execute()
        
        return True
    except Exception as e:
        st.error(f"Error corrigiendo: {e}")
        return False
