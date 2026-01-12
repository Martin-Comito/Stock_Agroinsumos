import streamlit as st
import pandas as pd
import qrcode
from io import BytesIO
from datetime import datetime

from database.queries import (
    supabase, registrar_ingreso, crear_producto, editar_producto,
    crear_orden_pendiente, confirmar_despacho_real, mover_pallet,
    corregir_movimiento
)

st.set_page_config(page_title="AgroCheck Pro V2", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&family=Inter:wght@400;600&display=swap');
    .stApp { background: linear-gradient(180deg, #020617 0%, #0f172a 100%); color: #f1f5f9; font-family: 'Inter', sans-serif; }
    h1, h2, h3 { font-family: 'Poppins', sans-serif; color: #fbbf24 !important; text-align: center; }
    div[data-testid="stVerticalBlockBorderWrapper"] > div { background-color: rgba(30, 41, 59, 0.5); border: 1px solid #334155; border-radius: 16px; padding: 20px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
    .card-icon { font-size: 40px; display: block; margin-bottom: 10px; }
    .card-title { font-size: 18px; font-weight: bold; color: white; display: block; margin-bottom: 5px; }
    .card-desc { font-size: 12px; color: #94a3b8; display: block; margin-bottom: 15px; }
    div[data-testid="stColumn"] button[kind="primary"] { width: 100%; background-color: #fbbf24 !important; color: #0f172a !important; font-weight: 800; border-radius: 8px; border: none; height: 45px; white-space: nowrap; }
    div[data-testid="stColumn"] button[kind="primary"]:hover { background-color: #f59e0b !important; color: white !important; transform: scale(1.02); }
    div[data-baseweb="input"] input, div[data-baseweb="select"] { background-color: #ffffff !important; color: #000000 !important; text-transform: uppercase; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

if 'vista' not in st.session_state: st.session_state.vista = "Menu Principal"
if 'carrito' not in st.session_state: st.session_state.carrito = []

def navegar_a(v): st.session_state.vista = v; st.rerun()
def tarjeta(icono, titulo, desc): st.markdown(f"""<span class="card-icon">{icono}</span><span class="card-title">{titulo}</span><span class="card-desc">{desc}</span>""", unsafe_allow_html=True)
def fmt(num): return f"{float(num):g}"

#  MENÚ
if st.session_state.vista == "Menu Principal":
    st.title("🚜 AgroCheck Pro V2")
    st.subheader(f"Depósito: Areco Semillas | {datetime.now().strftime('%d/%m/%Y')}")
    st.write("---")
    c1, c2, c3 = st.columns(3)
    with c1:
        with st.container(border=True):
            tarjeta("📥", "INGRESOS", "Alta de mercadería")
            if st.button("INGRESAR", key="b1", type="primary"): navegar_a("Ingresos")
    with c2:
        with st.container(border=True):
            tarjeta("📝", "ÓRDENES", "Generar pedidos")
            if st.button("CREAR ORDEN", key="b2", type="primary"): navegar_a("Ordenes")
    with c3:
        with st.container(border=True):
            tarjeta("📦", "VALIDACIÓN", "Control de carga")
            if st.button("VALIDAR", key="b3", type="primary"): navegar_a("Validacion")
    st.write("")
    c4, c5, c6 = st.columns(3)
    with c4:
        with st.container(border=True):
            tarjeta("📊", "STOCK", "Semáforo")
            if st.button("VER STOCK", key="b4", type="primary"): navegar_a("Stock")
    with c5:
        with st.container(border=True):
            tarjeta("🏗️", "ZAMPING", "Movimiento interno")
            if st.button("REUBICAR", key="b5", type="primary"): navegar_a("Zamping")
    with c6:
        with st.container(border=True):
            tarjeta("📜", "HISTORIAL", "Auditoría & Edición")
            if st.button("VER HISTORIAL", key="b6", type="primary"): navegar_a("Historial")
    st.write("---")
    cq, _ = st.columns([1,5])
    with cq:
        qr = qrcode.make("https://agroinsumostock.streamlit.app")
        buf = BytesIO(); qr.save(buf, format="PNG")
        st.image(buf.getvalue(), caption="Acceso Móvil", width=120)

#  INGRESOS
elif st.session_state.vista == "Ingresos":
    c_h, c_b = st.columns([4, 1])
    c_h.header("📥 Ingreso")
    if c_b.button("VOLVER", type="secondary"): navegar_a("Menu Principal")

    prods = supabase.table("productos").select("id, nombre_comercial, categoria").order("nombre_comercial").execute()
    p_map = {p['nombre_comercial']: {'id': p['id'], 'cat': p.get('categoria', '')} for p in prods.data} if prods.data else {}
    ubics = supabase.table("ubicaciones_internas").select("id, nombre_sector").order("nombre_sector").execute()
    u_map = {u['nombre_sector']: u['id'] for u in ubics.data} if ubics.data else {}

    with st.container(border=True):
        c_tipo, _ = st.columns([1,1])
        motivo = c_tipo.selectbox("📋 Tipo de Operación", ["COMPRA PROVEEDOR", "DEVOLUCIÓN CLIENTE", "TRANSFERENCIA SUCURSAL"])
        st.write("---")

        es_nuevo = st.checkbox("🆕 ¿Es Producto Nuevo?")
        c1, c2, c3 = st.columns(3)
        prod_id = None
        if es_nuevo:
            nom = c1.text_input("Nombre Nuevo").upper(); cat = c1.text_input("Categoría").upper()
        else:
            if p_map: p_sel = c1.selectbox("Producto", list(p_map.keys())); prod_id = p_map[p_sel]['id']
            else: es_nuevo = True

        lote = c1.text_input("Lote").upper()
        senasa = c2.text_input("SENASA").upper()
        gtin = c2.text_input("GTIN").upper()
        venc = c3.date_input("Vencimiento")
        ubic_id = u_map[c3.selectbox("Ubicación", list(u_map.keys()))] if u_map else None

        st.markdown("Calculadora")
        cc1, cc2 = st.columns(2)
        bultos = cc1.number_input("Bultos", min_value=0.0)
        cont = cc2.number_input("Contenido Unitario", min_value=0.0)
        total = bultos * cont
        st.metric("Total a Ingresar", f"{fmt(total)}")

        if st.button("GUARDAR INGRESO", type="primary"):
            if lote and total > 0 and ubic_id:
                if es_nuevo and nom: prod_id = crear_producto(nom, cat)
                if prod_id:
                    if registrar_ingreso(prod_id, lote, total, ubic_id, "Martin", venc, senasa, gtin, motivo):
                        st.success(f"✅ Ingreso por {motivo} guardado"); navegar_a("Menu Principal")
            else: st.error("Datos incompletos")

# ÓRDENES
elif st.session_state.vista == "Ordenes":
    c_h, c_b = st.columns([4, 1])
    c_h.header("📝 Generar Orden")
    if c_b.button("VOLVER", type="secondary"): navegar_a("Menu Principal")

    prods = supabase.table("productos").select("id, nombre_comercial").execute()
    p_map = {p['nombre_comercial']: p['id'] for p in prods.data}

    with st.container(border=True):
        cli = st.text_input("Cliente / Destino").upper()
        if p_map:
            p_sel = st.selectbox("Buscar Producto", list(p_map.keys()))
            lotes = supabase.table("lotes_stock").select("id, numero_lote, cantidad_actual, ubicaciones_internas(nombre_sector)").eq("producto_id", p_map[p_sel]).gt("cantidad_actual", 0).execute()
            
            if lotes.data:
                l_opts = {f"Lote: {l['numero_lote']} | {l['ubicaciones_internas']['nombre_sector']} ({fmt(l['cantidad_actual'])})": l['id'] for l in lotes.data}
                l_pick = st.selectbox("Lote Sugerido", list(l_opts.keys()))
                
                st.markdown("Cantidad a Pedir")
                kc1, kc2 = st.columns(2)
                bultos = kc1.number_input("Bultos Pedidos", min_value=0.0, step=1.0)
                cont = kc2.number_input("Contenido Unitario", min_value=0.0)
                cant_total = bultos * cont
                st.info(f"👉 Pedirás: **{fmt(cant_total)}** ({fmt(bultos)} x {fmt(cont)})")

                if st.button("AGREGAR AL PEDIDO"):
                    if cant_total > 0:
                        st.session_state.carrito.append({
                            "producto_id": p_map[p_sel], "nombre": p_sel, "cantidad": cant_total,
                            "lote_id": l_opts[l_pick], "detalle_bultos": f"Ped: {fmt(bultos)} x {fmt(cont)}"
                        })
            else: st.warning("⚠️ Sin Stock")

    if st.session_state.carrito:
        st.write("---")
        st.table(st.session_state.carrito)
        if st.button("ENVIAR A GALPÓN", type="primary"):
            if crear_orden_pendiente(st.session_state.carrito, cli, "Martin"):
                st.success("Enviado"); st.session_state.carrito = []; st.rerun()

# VALIDACIÓN
elif st.session_state.vista == "Validacion":
    c_h, c_b = st.columns([4, 1])
    c_h.header("📦 Validación")
    if c_b.button("VOLVER", type="secondary"): navegar_a("Menu Principal")

    pend = supabase.table("historial_movimientos").select("*, productos(nombre_comercial), lotes_stock(numero_lote)").eq("estado_confirmacion", "PENDIENTE").execute()
    
    if not pend.data: st.info("✅ Nada pendiente.")
    else:
        ped_id = st.selectbox("Pedido", list(set([i['id_pedido_referencia'] for i in pend.data])))
        items = [i for i in pend.data if i['id_pedido_referencia'] == ped_id]
        
        for item in items:
            with st.container(border=True):
                st.subheader(item['productos']['nombre_comercial'])
                cant_ped = abs(item['cantidad_afectada'])
                st.info(f"Sacar **{fmt(cant_ped)}** del Lote **{item['lotes_stock']['numero_lote']}**")
                
                c1, c2 = st.columns(2)
                l_real = c1.text_input("LOTE FÍSICO", key=f"lr_{item['id']}").upper()
                c_real = c2.number_input("CANTIDAD REAL", key=f"cr_{item['id']}", value=None)
                
                if st.button("VALIDAR", key=f"v_{item['id']}", type="primary"):
                    l_esp = item['lotes_stock']['numero_lote'].upper()
                    if l_real == l_esp and c_real == cant_ped:
                        confirmar_despacho_real(item['id'], item['lote_id'], c_real, "Martin")
                        st.success("✅ OK"); st.rerun()
                    elif l_real == l_esp and c_real < cant_ped:
                         st.session_state[f"parcial_{item['id']}"] = True 
                    elif l_real == l_esp and c_real > cant_ped:
                        st.error(f"⛔ Error: Sacas MÁS de lo pedido.")
                    elif l_real != l_esp:
                        st.session_state[f"cruce_{item['id']}"] = True

                if st.session_state.get(f"parcial_{item['id']}", False):
                    st.warning(f"⚠️ Despacho Parcial: {fmt(c_real)} de {fmt(cant_ped)}.")
                    if st.button("CONFIRMAR PARCIAL", key=f"si_p_{item['id']}"):
                         confirmar_despacho_real(item['id'], item['lote_id'], c_real, "Martin", es_parcial=True, cant_original=cant_ped)
                         st.success("✅ Parcial OK"); st.rerun()

                if st.session_state.get(f"cruce_{item['id']}", False):
                    st.warning(f"⚠️ Lote Distinto: Leíste {l_real}, se pedía {l_esp}.")
                    if st.button("CONFIRMAR CRUCE", key=f"si_c_{item['id']}"):
                        res_alt = supabase.table("lotes_stock").select("id").eq("producto_id", item['producto_id']).eq("numero_lote", l_real).execute()
                        if res_alt.data:
                            confirmar_despacho_real(item['id'], res_alt.data[0]['id'], c_real, "Martin", es_cruce=True)
                            st.success("🔄 Cruce OK"); st.rerun()
                        else: st.error("Lote inexistente.")

#  STOCK
elif st.session_state.vista == "Stock":
    c_h, c_b = st.columns([4, 1])
    c_h.header("📊 Stock")
    if c_b.button("VOLVER", type="secondary"): navegar_a("Menu Principal")

    filtro = st.text_input("🔍 Buscar...").upper()
    res = supabase.table("lotes_stock").select("*, productos(nombre_comercial), ubicaciones_internas(nombre_sector)").gt("cantidad_actual", 0).execute()
    
    if res.data:
        data = []
        hoy = datetime.now().date()
        for i in res.data:
            nom = i['productos']['nombre_comercial'].upper()
            lot = i['numero_lote'].upper()
            if filtro in nom or filtro in lot:
                venc_str = i['fecha_vencimiento']
                venc = datetime.strptime(venc_str, '%Y-%m-%d').date() if venc_str else None
                dias = (venc - hoy).days if venc else 999
                est = "🟢 OK"
                if dias < 30: est = "🔴 CRÍTICO"
                elif dias < 90: est = "🟡 ALERTA"
                data.append({
                    "UBIC": i['ubicaciones_internas']['nombre_sector'],
                    "PROD": nom, "LOTE": lot,
                    "CANT": fmt(i['cantidad_actual']), "VENC": venc_str, "EST": est
                })
        st.dataframe(pd.DataFrame(data), use_container_width=True)

# ZAMPING
elif st.session_state.vista == "Zamping":
    c_h, c_b = st.columns([4, 1])
    c_h.header("🏗️ Reubicación")
    if c_b.button("VOLVER", type="secondary"): navegar_a("Menu Principal")
    
    stk = supabase.table("lotes_stock").select("id, numero_lote, cantidad_actual, productos(nombre_comercial), ubicaciones_internas(nombre_sector)").gt("cantidad_actual", 0).execute()
    ub = supabase.table("ubicaciones_internas").select("id, nombre_sector").order("nombre_sector").execute()
    u_map = {u['nombre_sector']: u['id'] for u in ub.data} if ub.data else {}
    
    if stk.data:
        opts = {f"{s['productos']['nombre_comercial']} | {s['numero_lote']} | {s['ubicaciones_internas']['nombre_sector']}": s['id'] for s in stk.data}
        sel = st.selectbox("Pallet", list(opts.keys()))
        dest = st.selectbox("Destino", list(u_map.keys()))
        if st.button("MOVER", type="primary"):
            if mover_pallet(opts[sel], u_map[dest], "Martin"): st.success("✅ Hecho"); st.rerun()

# 📜 HISTORIAL & EDICIÓN TOTAL
elif st.session_state.vista == "Historial":
    c_h, c_b = st.columns([4, 1])
    c_h.header("📜 Centro de Historial")
    if c_b.button("VOLVER", type="secondary"): navegar_a("Menu Principal")

    # 1. GESTIÓN MAESTRO
    with st.expander("Gestión de Productos (Corregir Nombres/Categorías)"):
        st.caption("Corrección global de nombres de productos.")
        all_prods = supabase.table("productos").select("id, nombre_comercial, categoria").order("nombre_comercial").execute()
        if all_prods.data:
            p_dict = {p['nombre_comercial']: p for p in all_prods.data}
            p_sel_edit = st.selectbox("Seleccionar Producto", list(p_dict.keys()), key="master_edit_sel")
            ce1, ce2 = st.columns(2)
            new_name = ce1.text_input("Nuevo Nombre", value=p_sel_edit).upper()
            new_cat = ce2.text_input("Nueva Categoría", value=p_dict[p_sel_edit].get('categoria', '') or "").upper()
            if st.button("GUARDAR CAMBIOS EN MAESTRO", type="primary"):
                if editar_producto(p_dict[p_sel_edit]['id'], new_name, new_cat):
                    st.success(f"✅ Producto actualizado"); st.rerun()
        else: st.info("Sin productos.")

    st.write("---")

    # 2. BUSCADOR & EDICIÓN DE TRANSACCIÓN
    busqueda = st.text_input("🔍 Buscar en Historial", placeholder="Producto, Lote, Ingreso...").upper()

    h = supabase.table("historial_movimientos").select("id, fecha_hora, tipo_movimiento, cantidad_afectada, origen_destino, observaciones, lote_id, productos(nombre_comercial), lotes_stock(numero_lote, fecha_vencimiento, senasa_codigo, gtin_codigo)").order("fecha_hora", desc=True).limit(100).execute()
    
    if h.data:
        flat_data = []
        for x in h.data:
            flat_data.append({
                "ID": x['id'],
                "FECHA": pd.to_datetime(x['fecha_hora']).strftime('%d/%m %H:%M'),
                "PRODUCTO": x['productos']['nombre_comercial'],
                "MOVIMIENTO": x['tipo_movimiento'],
                "CANTIDAD": fmt(x['cantidad_afectada']),
                "LOTE": x['lotes_stock']['numero_lote'] if x['lotes_stock'] else "N/A",
                "RAW_DATA": x
            })
        
        df = pd.DataFrame(flat_data)
        if busqueda:
            df = df[df.apply(lambda row: row.astype(str).str.contains(busqueda, case=False).any(), axis=1)]

        st.dataframe(df.drop(columns=["ID", "RAW_DATA"]), use_container_width=True)

        st.write("---")
        st.subheader("✏️ Corregir Transacción (Stock y Datos)")
        
        # Filtra solo ingresos
        opciones = {f"{r['PRODUCTO']} | Lote: {r['LOTE']} | {r['CANTIDAD']}": r['RAW_DATA'] 
                    for index, r in df.iterrows() if r['MOVIMIENTO'] == 'INGRESO'}
        
        if opciones:
            seleccion = st.selectbox("Seleccionar Movimiento a Corregir", list(opciones.keys()))
            dato = opciones[seleccion]
            
            with st.form("form_correccion_hist"):
                st.caption(f"Editando Ingreso de {dato['productos']['nombre_comercial']}")
                
                # Fila 1: Cantidad y Lote
                c1, c2 = st.columns(2)
                lote_actual = dato['lotes_stock']['numero_lote'] if dato['lotes_stock'] else ""
                nuevo_lote = c1.text_input("Corregir Lote", value=lote_actual).upper()
                
                cant_actual = float(dato['cantidad_afectada'])
                nueva_cant = c2.number_input("Corregir Cantidad Real", value=cant_actual)
                
                # Fila 2: Vencimiento
                c3, c4 = st.columns(2)
                venc_actual = dato['lotes_stock'].get('fecha_vencimiento') if dato['lotes_stock'] else None
                try: f_obj = datetime.strptime(venc_actual, '%Y-%m-%d').date() if venc_actual else datetime.now().date()
                except: f_obj = datetime.now().date()
                nueva_venc = c3.date_input("Corregir Vencimiento", value=f_obj)
                
                # Fila 3: SENASA y GTIN
                sen_actual = dato['lotes_stock'].get('senasa_codigo', '') if dato['lotes_stock'] else ""
                gtin_actual = dato['lotes_stock'].get('gtin_codigo', '') if dato['lotes_stock'] else ""
                
                nuevo_senasa = c3.text_input("Corregir SENASA", value=sen_actual).upper()
                nuevo_gtin = c4.text_input("Corregir GTIN", value=gtin_actual).upper()

                if st.form_submit_button("GUARDAR CORRECCIÓN TOTAL", type="primary"):
                    # Llama a la función actualizada con todos los parámetros
                    if corregir_movimiento(dato['id'], dato['lote_id'], nuevo_lote, nueva_cant, nueva_venc, nuevo_senasa, nuevo_gtin, "Martin"):
                        st.success("✅ Todo actualizado (Stock, Lote, SENASA, GTIN)."); st.rerun()
        else:
            st.info("No hay ingresos seleccionables en la búsqueda.")
    else:
        st.info("Historial vacío.")