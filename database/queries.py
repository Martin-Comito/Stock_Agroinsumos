import streamlit as st
from supabase import create_client, Client
from datetime import datetime
import pytz 

# Configuración de Zona Horaria ARGENTINA
ARG = pytz.timezone('America/Argentina/Buenos_Aires')

@st.cache_resource
def get_supabase() -> Client:
    try:
        return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])
    except: return None

supabase = get_supabase()

def ahora_arg():
    return datetime.now(ARG).isoformat()

# LOGIN & SEGURIDAD
def verificar_login(usuario, password):
    """Devuelve el usuario si coincide pass y user"""
    try:
        # Traemos todos los campos, incluido 'rol'
        res = supabase.table("usuarios").select("*").eq("username", usuario.strip()).eq("password", password.strip()).execute()
        if res.data: return res.data[0]
        return None
    except: return None

# PRODUCTOS 
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

# MOVIMIENTOS 

def registrar_ingreso(producto_id, lote, cantidad, ubicacion_id, usuario, fecha_venc, senasa, gtin, motivo_ingreso, sucursal):
    try:
        lote_upper = lote.strip().upper()
        # Busca lote SOLO en la sucursal del usuario
        res = supabase.table("lotes_stock").select("*").eq("producto_id", producto_id).eq("numero_lote", lote_upper).eq("ubicacion_id", ubicacion_id).eq("sucursal_id", sucursal).execute()
        
        lote_id_final = None
        if res.data:
            lote_id_final = res.data[0]['id']
            nueva_cant = float(res.data[0]['cantidad_actual']) + cantidad
            supabase.table("lotes_stock").update({
                "cantidad_actual": nueva_cant, "senasa_codigo": senasa, "gtin_codigo": gtin,
                "ultima_actualizacion": ahora_arg()
            }).eq("id", lote_id_final).execute()
        else:
            datos_lote = {
                "producto_id": producto_id, "ubicacion_id": ubicacion_id,
                "numero_lote": lote_upper, "cantidad_actual": cantidad,
                "fecha_vencimiento": str(fecha_venc), "senasa_codigo": senasa.upper(),
                "gtin_codigo": gtin.upper(), "estado_calidad": "DISPONIBLE",
                "ultima_actualizacion": ahora_arg(),
                "sucursal_id": sucursal 
            }
            res_insert = supabase.table("lotes_stock").insert(datos_lote).execute()
            if res_insert.data: lote_id_final = res_insert.data[0]['id']

        if lote_id_final:
            supabase.table("historial_movimientos").insert({
                "producto_id": producto_id, "lote_id": lote_id_final, "tipo_movimiento": "INGRESO",
                "cantidad_afectada": cantidad, "origen_destino": motivo_ingreso.upper(),
                "usuario_operador": usuario, "estado_confirmacion": "TERMINADO",
                "observaciones": f"SENASA: {senasa} | GTIN: {gtin}",
                "fecha_hora": ahora_arg(),
                "sucursal_id": sucursal
            }).execute()
            return True
        return False
    except: return False

def crear_orden_pendiente(items_carrito, destino, usuario, sucursal):
    try:
        pedido_id = f"PED-{int(datetime.now().timestamp())}"
        for item in items_carrito:
            supabase.table("historial_movimientos").insert({
                "id_pedido_referencia": pedido_id, "producto_id": item['producto_id'], "lote_id": item['lote_id'],
                "tipo_movimiento": "EGRESO_VENTA", "cantidad_afectada": item['cantidad'] * -1,
                "origen_destino": destino.upper(), "usuario_operador": usuario, "estado_confirmacion": "PENDIENTE",
                "observaciones": item['detalle_bultos'], "fecha_hora": ahora_arg(), "sucursal_id": sucursal
            }).execute()
        return pedido_id
    except: return None

def confirmar_despacho_real(movimiento_id, lote_real_id, cantidad_real, usuario, es_cruce=False, es_parcial=False, cant_original=0):
    try:
        obs = "Validado OK"
        if es_cruce: obs = "⚠️ CRUCE DE PARTIDA"
        if es_parcial: obs += " | DESPACHO PARCIAL"

        supabase.table("historial_movimientos").update({
            "lote_id": lote_real_id, "cantidad_afectada": cantidad_real * -1,
            "estado_confirmacion": "TERMINADO", "observaciones": obs, 
            "fecha_hora": ahora_arg()
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
                "estado_confirmacion": "PENDIENTE", "observaciones": "SALDO RESTANTE (Split)",
                "fecha_hora": ahora_arg(), "sucursal_id": mov_orig['sucursal_id']
            }).execute()
        return True
    except: return False

def mover_pallet(lote_id, nueva_u, usuario):
    try:
        supabase.table("lotes_stock").update({"ubicacion_id": nueva_u, "ultima_actualizacion": ahora_arg()}).eq("id", lote_id).execute()
        return True
    except: return False

def corregir_movimiento(movimiento_id, lote_id, nuevo_lote, nueva_cantidad, nueva_venc, nuevo_senasa, nuevo_gtin, usuario):
    try:
        mov_viejo = supabase.table("historial_movimientos").select("cantidad_afectada").eq("id", movimiento_id).execute()
        cant_vieja = float(mov_viejo.data[0]['cantidad_afectada'])
        supabase.table("historial_movimientos").update({
            "cantidad_afectada": nueva_cantidad, "observaciones": f"Corregido por {usuario} (Antes: {cant_vieja})",
            "fecha_hora": ahora_arg()
        }).eq("id", movimiento_id).execute()
        diferencia = nueva_cantidad - cant_vieja
        stock_res = supabase.table("lotes_stock").select("cantidad_actual").eq("id", lote_id).execute()
        if stock_res.data:
            stock_actual = float(stock_res.data[0]['cantidad_actual'])
            supabase.table("lotes_stock").update({
                "numero_lote": nuevo_lote.upper().strip(), "fecha_vencimiento": str(nueva_venc),
                "cantidad_actual": stock_actual + diferencia, "senasa_codigo": nuevo_senasa.upper().strip(), "gtin_codigo": nuevo_gtin.upper().strip()
            }).eq("id", lote_id).execute()
        return True
    except: return False

def mover_a_guarda(lote_origen_id, cantidad_rotura, usuario):
    """
    Resta cantidad del lote original (DISPONIBLE) y crea/suma a un lote en estado GUARDA.
    """
    try:
        # 1. Obtener datos del lote original
        origen = supabase.table("lotes_stock").select("*").eq("id", lote_origen_id).execute()
        if not origen.data: return False
        lote_data = origen.data[0]
        
        cant_actual = float(lote_data['cantidad_actual'])
        if cantidad_rotura > cant_actual: return False # Seguridad extra

        # 2. Restar del lote original (Disponible)
        supabase.table("lotes_stock").update({
            "cantidad_actual": cant_actual - cantidad_rotura,
            "ultima_actualizacion": ahora_arg()
        }).eq("id", lote_origen_id).execute()

        # 3. Buscar si ya existe ese lote en GUARDA para esa sucursal
        existe_guarda = supabase.table("lotes_stock").select("*")\
            .eq("producto_id", lote_data['producto_id'])\
            .eq("numero_lote", lote_data['numero_lote'])\
            .eq("sucursal_id", lote_data['sucursal_id'])\
            .eq("estado_calidad", "GUARDA").execute()

        lote_guarda_id = None

        if existe_guarda.data:
            # Si existe, suma
            lote_guarda_id = existe_guarda.data[0]['id']
            nueva_cant_guarda = float(existe_guarda.data[0]['cantidad_actual']) + cantidad_rotura
            supabase.table("lotes_stock").update({
                "cantidad_actual": nueva_cant_guarda,
                "ultima_actualizacion": ahora_arg()
            }).eq("id", lote_guarda_id).execute()
        else:
            # Si no existe, crea el registro en GUARDA
            nuevo_lote = lote_data.copy()
            del nuevo_lote['id'] 
            del nuevo_lote['created_at'] 
            nuevo_lote['cantidad_actual'] = cantidad_rotura
            nuevo_lote['estado_calidad'] = "GUARDA"
            nuevo_lote['ultima_actualizacion'] = ahora_arg()
            
            res = supabase.table("lotes_stock").insert(nuevo_lote).execute()
            if res.data: lote_guarda_id = res.data[0]['id']

        # 4. Registrar en historial
        if lote_guarda_id:
            supabase.table("historial_movimientos").insert({
                "producto_id": lote_data['producto_id'],
                "lote_id": lote_guarda_id,
                "tipo_movimiento": "ROTURA_A_GUARDA",
                "cantidad_afectada": cantidad_rotura, 
                "origen_destino": "MOVIMIENTO INTERNO",
                "usuario_operador": usuario,
                "estado_confirmacion": "TERMINADO",
                "observaciones": f"Rotura reportada desde lote {lote_data['numero_lote']}",
                "fecha_hora": ahora_arg(),
                "sucursal_id": lote_data['sucursal_id']
            }).execute()
            return True
        return False
    except Exception as e:
        print(e)
        return False

def baja_uso_interno(lote_guarda_id, cantidad, motivo, usuario):
    try:
        lote = supabase.table("lotes_stock").select("cantidad_actual, producto_id, sucursal_id").eq("id", lote_guarda_id).execute()
        if not lote.data: return False
        
        cant_actual = float(lote.data[0]['cantidad_actual'])
        nuevo_saldo = cant_actual - cantidad
        
        # Actualizar stock guarda
        supabase.table("lotes_stock").update({
            "cantidad_actual": nuevo_saldo,
            "ultima_actualizacion": ahora_arg()
        }).eq("id", lote_guarda_id).execute()

        # Historial de baja
        supabase.table("historial_movimientos").insert({
            "producto_id": lote.data[0]['producto_id'],
            "lote_id": lote_guarda_id,
            "tipo_movimiento": "EGRESO_BAJA",
            "cantidad_afectada": cantidad * -1,
            "origen_destino": "USO INTERNO / DESCARTE",
            "usuario_operador": usuario,
            "estado_confirmacion": "TERMINADO",
            "observaciones": f"Baja desde Guarda: {motivo}",
            "fecha_hora": ahora_arg(),
            "sucursal_id": lote.data[0]['sucursal_id']
        }).execute()
        return True
    except: return False

# FUNCIONES PARA AUDITORIA/RECONTEO

def registrar_reconteo(producto_id, lote_id, cant_sistema, cant_fisica, motivo, usuario, sucursal):
    try:
        diferencia = cant_fisica - cant_sistema
        supabase.table("reconteos").insert({
            "producto_id": producto_id,
            "lote_id": lote_id,
            "sucursal_id": sucursal,
            "usuario_solicitante": usuario,
            "cantidad_sistema": cant_sistema,
            "cantidad_fisica": cant_fisica,
            "diferencia": diferencia,
            "motivo": motivo,
            "estado": "PENDIENTE",
            "created_at": ahora_arg()
        }).execute()
        return True
    except: return False

def editar_reconteo_pendiente(reconteo_id, nueva_cant_fisica, cant_sistema, nuevo_motivo):
    try:
        nueva_diferencia = nueva_cant_fisica - cant_sistema
        supabase.table("reconteos").update({
            "cantidad_fisica": nueva_cant_fisica,
            "diferencia": nueva_diferencia,
            "motivo": nuevo_motivo,
            "created_at": ahora_arg()
        }).eq("id", reconteo_id).eq("estado", "PENDIENTE").execute()
        return True
    except: return False

def aprobar_ajuste_stock(reconteo_id, admin_user):
    try:
        # 1. Obtener datos del reconteo
        rec_res = supabase.table("reconteos").select("*").eq("id", reconteo_id).execute()
        if not rec_res.data: return False
        rec = rec_res.data[0]
        
        # 2. Actualizar Lote
        supabase.table("lotes_stock").update({
            "cantidad_actual": rec['cantidad_fisica'],
            "ultima_actualizacion": ahora_arg()
        }).eq("id", rec['lote_id']).execute()

        # 3. Insertar Historial (Auditoría)
        tipo = "AJUSTE_POSITIVO" if rec['diferencia'] > 0 else "AJUSTE_NEGATIVO"
        supabase.table("historial_movimientos").insert({
            "producto_id": rec['producto_id'],
            "lote_id": rec['lote_id'],
            "tipo_movimiento": tipo,
            "cantidad_afectada": rec['diferencia'],
            "origen_destino": "AUDITORIA INTERNA",
            "usuario_operador": admin_user,
            "estado_confirmacion": "TERMINADO",
            "observaciones": f"Aprobado por {admin_user}. Solicitado por: {rec['usuario_solicitante']}. Motivo: {rec['motivo']}",
            "fecha_hora": ahora_arg(),
            "sucursal_id": rec['sucursal_id']
        }).execute()

        # 4. Cerrar Reconteo
        supabase.table("reconteos").update({
            "estado": "APROBADO",
            "fecha_auditoria": ahora_arg()
        }).eq("id", reconteo_id).execute()
        
        return True
    except Exception as e:
        print(e)
        return False

def rechazar_reconteo(reconteo_id):
    try:
        supabase.table("reconteos").update({"estado": "RECHAZADO"}).eq("id", reconteo_id).execute()
        return True
    except: return False
