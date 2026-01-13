import streamlit as st
import pandas as pd
import qrcode
from io import BytesIO
from datetime import datetime, timedelta
import pytz
import extra_streamlit_components as stx 
import time

from database.queries import (
    supabase, registrar_ingreso, crear_producto, editar_producto,
    crear_orden_pendiente, confirmar_despacho_real, mover_pallet,
    corregir_movimiento, verificar_login
)

st.set_page_config(page_title="AgroCheck Pro V2", page_icon="🚜", layout="wide", initial_sidebar_state="collapsed")

# CSS 
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&family=Inter:wght@400;600&display=swap');
    .stApp { background: #0f172a; color: #ffffff; font-family: 'Inter', sans-serif; }
    h1, h2, h3 { font-family: 'Poppins', sans-serif; color: #fbbf24 !important; text-align: center; text-shadow: 0px 0px 10px rgba(0,0,0,0.5); }
    label, .stMarkdown p, .stText, .stCheckbox label, div[data-testid="stMetricValue"] { color: #ffffff !important; font-weight: 600 !important; font-size: 1.1rem !important; }
    
    /* Estilo de Tarjetas (Contenedores con borde) */
    div[data-testid="stVerticalBlockBorderWrapper"] > div { 
        background-color: #1e293b; 
        border: 2px solid #475569; 
        border-radius: 12px; 
    }
    
    /* Iconos y Textos */
    .card-icon { font-size: 40px; display: block; margin-bottom: 10px; }
    .card-title { font-size: 18px; font-weight: bold; color: white; display: block; margin-bottom: 5px; }
    .card-desc { font-size: 14px; color: #cbd5e1; display: block; margin-bottom: 15px; }
    
    /* Botones PC (Default) */
    div[data-testid="stColumn"] button[kind="primary"] { width: 100%; background-color: #fbbf24 !important; color: #000000 !important; font-weight: 800; font-size: 16px; border: 2px solid #f59e0b; }
    div[data-testid="stColumn"] button[kind="secondary"] { background-color: #ffffff !important; color: #dc2626 !important; font-weight: 800; border: 2px solid #dc2626 !important; }
    
    /* Inputs */
    div[data-baseweb="input"] input, div[data-baseweb="select"] { background-color: #ffffff !important; color: #000000 !important; font-weight: bold; font-size: 16px; }
    
    /* --- AJUSTE AGRESIVO PARA CELULARES --- */
    @media only screen and (max-width: 768px) {
        
        /* 1. Centrar texto dentro de las tarjetas */
        div[data-testid="stVerticalBlockBorderWrapper"] {
            text-align: center !important;
            align-items: center !important;
        }
        
        /* 2. Forzar alineación de iconos y títulos */
        .card-icon, .card-title, .card-desc {
            margin-left: auto !important;
            margin-right: auto !important;
            text-align: center !important;
            display: block !important;
        }

        /* 3. BOTONES EN MÓVIL: ANCHO TOTAL Y CENTRADOS */
        div[data-testid="stVerticalBlockBorderWrapper"] button {
            width: 100% !important;
            display: block !important;
            margin-left: auto !important;
            margin-right: auto !important;
        }
        
        /* 4. Ajuste del contenedor principal del botón */
        .stButton {
            width: 100% !important;
            display: flex !important;
            justify-content: center !important;
        }
    }
    </style>
    """, unsafe_allow_html=True)

# GESTOR DE COOKIES
cookie_manager = stx.CookieManager()

# VARIABLES DE SESIÓN
if 'usuario_id' not in st.session_state: st.session_state.usuario_id = None
if 'usuario_nombre' not in st.session_state: st.session_state.usuario_nombre = None
if 'usuario_sucursal' not in st.session_state: st.session_state.usuario_sucursal = None
if 'vista' not in st.session_state: st.session_state.vista = "Menu Principal"
if 'carrito' not in st.session_state: st.session_state.carrito = []
if 'logout_triggered' not in st.session_state: st.session_state.logout_triggered = False 

# LÓGICA DE AUTO-LOGIN
if st.session_state.usuario_id is None and not st.session_state.logout_triggered:
    time.sleep(0.2)
    cookie_user = cookie_manager.get('agro_user')
    if cookie_user:
        try:
            res = supabase.table("usuarios").select("*").eq("username", cookie_user).execute()
            if res.data:
                user_data = res.data[0]
                st.session_state.usuario_id = user_data['id']
                st.session_state.usuario_nombre = user_data['nombre_completo']
                st.session_state.usuario_sucursal = user_data.get('sucursal_asignada', 'CARMEN')
                st.rerun()
        except: pass

def navegar_a(v): st.session_state.vista = v; st.rerun()
def tarjeta(icono, titulo, desc): st.markdown(f"""<span class="card-icon">{icono}</span><span class="card-title">{titulo}</span><span class="card-desc">{desc}</span>""", unsafe_allow_html=True)
def fmt(num): return f"{float(num):g}"

# HELPER: CALCULADORA UNIFICADA
def calculadora_stock(key_prefix):
    st.markdown("Calculadora de Unidades")
    c1, c2, c3 = st.columns([1,1,1])
    cant_bultos = c1.number_input("Cantidad (Bultos/Cajas)", min_value=0.0, step=1.0, key=f"{key_prefix}_bultos")
    contenido = c2.number_input("Contenido Unitario (Lts/Kgs)", min_value=0.0, step=0.1, key=f"{key_prefix}_cont")
    total = cant_bultos * contenido
    c3.metric("Total Real", f"{fmt(total)}")
    return total, cant_bultos, contenido

#  PANTALLA DE LOGIN
if st.session_state.usuario_id is None:
    c_log1, c_log2, c_log3 = st.columns([1,2,1])
    with c_log2:
        st.write(""); st.write("")
        st.markdown("<h1 style='font-size: 60px;'>🚜</h1>", unsafe_allow_html=True)
        st.title("AgroCheck Pro")
        with st.container(border=True):
            user_input = st.text_input("Usuario", placeholder="Ej: admin")
            pass_input = st.text_input("Contraseña", type="password")
            
            if st.button("INGRESAR AL SISTEMA", type="primary"):
                user = verificar_login(user_input, pass_input)
                if user:
                    st.session_state.usuario_id = user['id']
                    st.session_state.usuario_nombre = user['nombre_completo']
                    st.session_state.usuario_sucursal = user.get('sucursal_asignada', 'CARMEN')
                    st.session_state.logout_triggered = False 
                    
                    cookie_manager.set('agro_user', user['username'], key="set_cookie", expires_at=datetime.now() + timedelta(days=30))
                    st.toast(f"Hola {user['nombre_completo']}", icon="👋")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ Credenciales inválidas")

#  APLICACIÓN PRINCIPAL
else:
    U_NOMBRE = st.session_state.usuario_nombre
    U_SUCURSAL = st.session_state.usuario_sucursal

    # SIDEBAR
    with st.sidebar:
        st.title("🚜")
        st.write(f"👤 **{U_NOMBRE}**")
        st.info(f"**{U_SUCURSAL}**")
        if st.button("Cerrar Sesión", type="secondary"):
            try: cookie_manager.delete('agro_user')
            except: pass
            
            st.session_state.logout_triggered = True 
            st.session_state.usuario_id = None
            st.session_state.usuario_nombre = None
            st.session_state.vista = "Menu Principal"
            
            st.toast("Cerrando sesión...", icon="🔒")
            time.sleep(1) 
            st.rerun()

    # MENÚ PRINCIPAL
    if st.session_state.vista == "Menu Principal":
        fecha_arg = datetime.now(pytz.timezone('America/Argentina/Buenos_Aires')).strftime('%d/%m/%Y')
        st.title("🚜 AgroCheck Pro V2")
        st.subheader(f"Depósito: {U_SUCURSAL} | {fecha_arg}")
        st.write("---")
        c1, c2, c3 = st.columns(3)
        with c1:
            with st.container(border=True):
                tarjeta("📥", "INGRESOS", "Alta")
                if st.button("INGRESAR", key="b1", type="primary"): navegar_a("Ingresos")
        with c2:
            with st.container(border=True):
                tarjeta("📝", "ÓRDENES", "Pedidos")
                if st.button("CREAR ORDEN", key="b2", type="primary"): navegar_a("Ordenes")
        with c3:
            with st.container(border=True):
                tarjeta("📦", "VALIDACIÓN", "Control")
                if st.button("VALIDAR", key="b3", type="primary"): navegar_a("Validacion")
        st.write("")
        c4, c5, c6 = st.columns(3)
        with c4:
            with st.container(border=True):
                tarjeta("📊", "STOCK", "Semáforo")
                if st.button("VER STOCK", key="b4", type="primary"): navegar_a("Stock")
        with c5:
            with st.container(border=True):
                tarjeta("🏗️", "ZAMPING", "Mover")
                if st.button("REUBICAR", key="b5", type="primary"): navegar_a("Zamping")
        with c6:
            with st.container(border=True):
                tarjeta("📜", "HISTORIAL", "Auditoría")
                if st.button("VER HISTORIAL", key="b6", type="primary"): navegar_a("Historial")
        st.write("---")
        cq, _ = st.columns([1,5])
        with cq:
            qr = qrcode.make("https://stockagroinsumos2.streamlit.app")
            buf = BytesIO(); qr.save(buf, format="PNG")
            st.image(buf.getvalue(), caption="Acceso Móvil", width=120)

    # INGRESOS
    elif st.session_state.vista == "Ingresos":
        c_h, c_b = st.columns([4, 1])
        c_h.header("📥 Ingreso")
        if c_b.button("VOLVER", type="secondary"): navegar_a("Menu Principal")

        prods = supabase.table("productos").select("id, nombre_comercial, categoria").order("nombre_comercial").execute()
        p_map = {p['nombre_comercial']: {'id': p['id'], 'cat': p.get('categoria', '')} for p in prods.data} if prods.data else {}
        ubics = supabase.table("ubicaciones_internas").select("id, nombre_sector").order("nombre_sector").execute()
        u_map = {u['nombre_sector']: u['id'] for u in ubics.data} if ubics.data else {}

        with st.container(border=True):
            col_mot, col_det = st.columns(2)
            motivo_base = col_mot.selectbox("📋 Motivo", ["COMPRA PROVEEDOR", "DEVOLUCIÓN CLIENTE", "TRANSFERENCIA SUCURSAL"])
            
            detalle_origen = ""
            if motivo_base == "DEVOLUCIÓN CLIENTE":
                detalle_origen = col_det.text_input("👤 Nombre del Cliente (Devolución)").upper()
            elif motivo_base == "TRANSFERENCIA SUCURSAL":
                detalle_origen = col_det.text_input("🏢 Sucursal de Origen").upper()
            elif motivo_base == "COMPRA PROVEEDOR":
                detalle_origen = col_det.text_input("🏭 Proveedor (Opcional)").upper()

            st.write("---")
            es_nuevo = st.checkbox("🆕 ¿Es Producto Nuevo?")
            c1, c2, c3 = st.columns(3)
            prod_id = None
            if es_nuevo:
                nom = c1.text_input("Nombre Nuevo").upper(); cat = c1.text_input("Categoría").upper()
            else:
                if p_map: p_sel = c1.selectbox("Producto", list(p_map.keys())); prod_id = p_map[p_sel]['id']
                else: es_nuevo = True
            
            lote_input = c1.text_input("Lote").upper()
            senasa_input = c2.text_input("SENASA").upper()
            gtin_input = c2.text_input("GTIN").upper()
            venc = c3.date_input("Vencimiento")
            ubic_id = u_map[c3.selectbox("Ubicación", list(u_map.keys()))] if u_map else None
            
            st.write("---")
            total_ingreso, bultos, unitario = calculadora_stock("ing")
            
            if st.button("GUARDAR INGRESO", type="primary"):
                if lote_input and total_ingreso > 0 and ubic_id:
                    motivo_final = f"{motivo_base}"
                    if detalle_origen: motivo_final += f" | {detalle_origen}"

                    if es_nuevo and nom: prod_id = crear_producto(nom, cat)
                    if prod_id:
                        if registrar_ingreso(prod_id, lote_input, total_ingreso, ubic_id, U_NOMBRE, venc, senasa_input, gtin_input, motivo_final, U_SUCURSAL):
                            st.success(f"✅ Ingreso OK: {motivo_final}"); time.sleep(1); navegar_a("Menu Principal")
                else: st.error("Faltan datos obligatorios")

    # ÓRDENES
    elif st.session_state.vista == "Ordenes":
        c_h, c_b = st.columns([4, 1])
        c_h.header("📝 Armar Pedido")
        if c_b.button("VOLVER", type="secondary"): navegar_a("Menu Principal")

        prods = supabase.table("productos").select("id, nombre_comercial").execute()
        p_map = {p['nombre_comercial']: p['id'] for p in prods.data}

        with st.container(border=True):
            cli = st.text_input("Cliente / Destino").upper()
            if p_map:
                p_sel = st.selectbox("Buscar Producto", list(p_map.keys()))
                lotes = supabase.table("lotes_stock").select("id, numero_lote, cantidad_actual, ubicaciones_internas(nombre_sector)").eq("producto_id", p_map[p_sel]).eq("sucursal_id", U_SUCURSAL).gt("cantidad_actual", 0).execute()
                
                if lotes.data:
                    l_opts = {f"{l['ubicaciones_internas']['nombre_sector']} | Lote: {l['numero_lote']} | Disp: {fmt(l['cantidad_actual'])}": l['id'] for l in lotes.data}
                    l_pick = st.selectbox("Seleccionar Lote y Ubicación", list(l_opts.keys()))
                    total_pedir, bultos, unitario = calculadora_stock("ord")
                    
                    if st.button("AGREGAR AL PEDIDO"):
                        if total_pedir > 0:
                            st.session_state.carrito.append({
                                "producto_id": p_map[p_sel], "nombre": p_sel, 
                                "cantidad": total_pedir, "lote_id": l_opts[l_pick], 
                                "detalle_bultos": f"Ped: {fmt(bultos)} x {fmt(unitario)}"
                            })
                            st.rerun()
                else: st.warning("⚠️ Sin Stock")

        if st.session_state.carrito:
            st.write("---")
            st.subheader("🛒 Carrito")
            for i, item in enumerate(st.session_state.carrito):
                c_txt, c_del = st.columns([5,1])
                c_txt.info(f"{item['nombre']} | {item['detalle_bultos']} | Total: {fmt(item['cantidad'])}")
                if c_del.button("🗑️", key=f"del_{i}"):
                    st.session_state.carrito.pop(i)
                    st.rerun()

            if st.button("CONFIRMAR Y ENVIAR", type="primary"):
                if crear_orden_pendiente(st.session_state.carrito, cli, U_NOMBRE, U_SUCURSAL):
                    st.success("Pedido Enviado"); st.session_state.carrito = []; time.sleep(1); st.rerun()

    # VALIDACIÓN
    elif st.session_state.vista == "Validacion":
        c_h, c_b = st.columns([4, 1])
        c_h.header("📦 Validación")
        if c_b.button("VOLVER", type="secondary"): navegar_a("Menu Principal")

        pend = supabase.table("historial_movimientos").select("*, productos(nombre_comercial), lotes_stock(numero_lote, ubicaciones_internas(nombre_sector))").eq("estado_confirmacion", "PENDIENTE").eq("sucursal_id", U_SUCURSAL).execute()
        if not pend.data: st.info("✅ Nada pendiente.")
        else:
            ped_id = st.selectbox("Pedido", list(set([i['id_pedido_referencia'] for i in pend.data])))
            items = [i for i in pend.data if i['id_pedido_referencia'] == ped_id]
            for item in items:
                nombre_prod = item['productos']['nombre_comercial']
                lote_txt = item['lotes_stock']['numero_lote']
                
                ubic_txt = "SIN UBICACIÓN"
                if item['lotes_stock'] and item['lotes_stock'].get('ubicaciones_internas'):
                    ubic_txt = item['lotes_stock']['ubicaciones_internas']['nombre_sector']

                cant_ped = abs(item['cantidad_afectada'])

                with st.container(border=True):
                    st.markdown(f"IR A: {ubic_txt}")
                    st.markdown(f"**Producto:** {nombre_prod}")
                    st.info(f"👉 Sacar **{fmt(cant_ped)}** | Lote: **{lote_txt}**")
                    
                    c1, c2 = st.columns(2)
                    l_real = c1.text_input("Confirmar Lote Físico", key=f"lr_{item['id']}").upper()
                    
                    st.caption("Validar Cantidad Real:")
                    total_real_calc, b, u = calculadora_stock(f"val_{item['id']}")
                    
                    if st.button("VALIDAR", key=f"v_{item['id']}", type="primary"):
                        l_esp = lote_txt.upper()
                        c_real = total_real_calc
                        
                        if l_real == l_esp and c_real == cant_ped:
                            confirmar_despacho_real(item['id'], item['lote_id'], c_real, U_NOMBRE)
                            st.success("✅ OK"); st.rerun()
                        elif l_real == l_esp and c_real < cant_ped: st.session_state[f"parcial_{item['id']}"] = True 
                        elif l_real == l_esp and c_real > cant_ped: st.error(f"⛔ Error: Exceso")
                        elif l_real != l_esp: st.session_state[f"cruce_{item['id']}"] = True
                    
                    if st.session_state.get(f"parcial_{item['id']}", False):
                        st.warning(f"⚠️ Parcial: {fmt(total_real_calc)} de {fmt(cant_ped)}.")
                        if st.button("CONFIRMAR PARCIAL", key=f"si_p_{item['id']}"):
                             confirmar_despacho_real(item['id'], item['lote_id'], total_real_calc, U_NOMBRE, es_parcial=True, cant_original=cant_ped)
                             st.success("✅ Parcial OK"); st.rerun()
                    if st.session_state.get(f"cruce_{item['id']}", False):
                        st.warning(f"⚠️ Lote Distinto: Leíste {l_real}, se pedía {l_esp}.")
                        if st.button("CONFIRMAR CRUCE", key=f"si_c_{item['id']}"):
                            res_alt = supabase.table("lotes_stock").select("id").eq("producto_id", item['producto_id']).eq("numero_lote", l_real).execute()
                            if res_alt.data:
                                confirmar_despacho_real(item['id'], res_alt.data[0]['id'], total_real_calc, U_NOMBRE, es_cruce=True)
                                st.success("🔄 Cruce OK"); st.rerun()
                            else: st.error("Lote inexistente.")

    # STOCK
    elif st.session_state.vista == "Stock":
        c_h, c_b = st.columns([4, 1])
        c_h.header("📊 Stock")
        if c_b.button("VOLVER", type="secondary"): navegar_a("Menu Principal")
        filtro = st.text_input("🔍 Buscar...").upper()
        res = supabase.table("lotes_stock").select("*, productos(nombre_comercial), ubicaciones_internas(nombre_sector)").eq("sucursal_id", U_SUCURSAL).gt("cantidad_actual", 0).execute()
        if res.data:
            data = []
            hoy = datetime.now().date()
            for i in res.data:
                nom = i['productos']['nombre_comercial'].upper(); lot = i['numero_lote'].upper()
                if filtro in nom or filtro in lot:
                    venc_str = i['fecha_vencimiento']; venc = datetime.strptime(venc_str, '%Y-%m-%d').date() if venc_str else None
                    dias = (venc - hoy).days if venc else 999
                    est = "🟢 OK"
                    if dias < 30: est = "🔴 CRÍTICO"
                    elif dias < 90: est = "🟡 ALERTA"
                    data.append({"UBIC": i['ubicaciones_internas']['nombre_sector'], "PROD": nom, "LOTE": lot, "CANT": fmt(i['cantidad_actual']), "VENC": venc_str, "EST": est})
            st.dataframe(pd.DataFrame(data), use_container_width=True)

    # ZAMPING
    elif st.session_state.vista == "Zamping":
        c_h, c_b = st.columns([4, 1])
        c_h.header("🏗️ Reubicación")
        if c_b.button("VOLVER", type="secondary"): navegar_a("Menu Principal")
        stk = supabase.table("lotes_stock").select("id, numero_lote, cantidad_actual, productos(nombre_comercial), ubicaciones_internas(nombre_sector)").eq("sucursal_id", U_SUCURSAL).gt("cantidad_actual", 0).execute()
        ub = supabase.table("ubicaciones_internas").select("id, nombre_sector").order("nombre_sector").execute()
        u_map = {u['nombre_sector']: u['id'] for u in ub.data} if ub.data else {}
        if stk.data:
            opts = {f"{s['productos']['nombre_comercial']} | {s['numero_lote']} | {s['ubicaciones_internas']['nombre_sector']}": s['id'] for s in stk.data}
            sel = st.selectbox("Pallet", list(opts.keys()))
            dest = st.selectbox("Destino", list(u_map.keys()))
            if st.button("MOVER", type="primary"):
                if mover_pallet(opts[sel], u_map[dest], U_NOMBRE): st.success("✅ Hecho"); st.rerun()

    # HISTORIAL 
    elif st.session_state.vista == "Historial":
        c_h, c_b = st.columns([4, 1])
        c_h.header("📜 Centro de Historial")
        if c_b.button("VOLVER", type="secondary"): navegar_a("Menu Principal")
        with st.expander("🛠️ Gestión de Productos (Maestro)"):
            all_prods = supabase.table("productos").select("id, nombre_comercial, categoria").order("nombre_comercial").execute()
            if all_prods.data:
                p_dict = {p['nombre_comercial']: p for p in all_prods.data}
                p_sel_edit = st.selectbox("Seleccionar Producto", list(p_dict.keys()), key="master_edit_sel")
                ce1, ce2 = st.columns(2)
                new_name = ce1.text_input("Nuevo Nombre", value=p_sel_edit).upper()
                new_cat = ce2.text_input("Nueva Categoría", value=p_dict[p_sel_edit].get('categoria', '') or "").upper()
                if st.button("GUARDAR CAMBIOS EN MAESTRO", type="primary"):
                    if editar_producto(p_dict[p_sel_edit]['id'], new_name, new_cat): st.success(f"✅ Producto actualizado"); st.rerun()
        st.write("---")
        busqueda = st.text_input("🔍 Buscar en Historial", placeholder="Producto, Lote...").upper()
        h = supabase.table("historial_movimientos").select("id, fecha_hora, tipo_movimiento, cantidad_afectada, origen_destino, observaciones, lote_id, productos(nombre_comercial), lotes_stock(numero_lote, fecha_vencimiento, senasa_codigo, gtin_codigo)").eq("sucursal_id", U_SUCURSAL).order("fecha_hora", desc=True).limit(100).execute()
        if h.data:
            flat_data = []
            arg_tz = pytz.timezone('America/Argentina/Buenos_Aires')
            for x in h.data:
                try:
                    dt_utc = datetime.fromisoformat(x['fecha_hora'].replace('Z', '+00:00'))
                    fecha_str = dt_utc.astimezone(arg_tz).strftime('%d/%m %H:%M')
                except: fecha_str = x['fecha_hora']
                flat_data.append({"ID": x['id'], "FECHA": fecha_str, "PRODUCTO": x['productos']['nombre_comercial'], "MOVIMIENTO": x['tipo_movimiento'], "CANTIDAD": fmt(x['cantidad_afectada']), "LOTE": x['lotes_stock']['numero_lote'] if x['lotes_stock'] else "N/A", "RAW_DATA": x})
            df = pd.DataFrame(flat_data)
            if busqueda: df = df[df.apply(lambda row: row.astype(str).str.contains(busqueda, case=False).any(), axis=1)]
            st.dataframe(df.drop(columns=["ID", "RAW_DATA"]), use_container_width=True)
            st.write("---")
            st.subheader("✏️ Corregir Transacción")
            opciones = {f"{r['PRODUCTO']} | Lote: {r['LOTE']} | {r['CANTIDAD']}": r['RAW_DATA'] for index, r in df.iterrows() if r['MOVIMIENTO'] == 'INGRESO'}
            if opciones:
                seleccion = st.selectbox("Seleccionar Movimiento", list(opciones.keys()))
                dato = opciones[seleccion]
                with st.form("form_correccion_hist"):
                    c1, c2 = st.columns(2)
                    lote_actual = dato['lotes_stock']['numero_lote'] if dato['lotes_stock'] else ""
                    nuevo_lote = c1.text_input("Corregir Lote", value=lote_actual).upper()
                    cant_actual = float(dato['cantidad_afectada'])
                    nueva_cant = c2.number_input("Corregir Cantidad Real", value=cant_actual)
                    if st.form_submit_button("GUARDAR CORRECCIÓN TOTAL", type="primary"):
                        if corregir_movimiento(dato['id'], dato['lote_id'], nuevo_lote, nueva_cant, dato['lotes_stock']['fecha_vencimiento'], dato['lotes_stock']['senasa_codigo'], dato['lotes_stock']['gtin_codigo'], U_NOMBRE): st.success("✅ Todo actualizado."); st.rerun()
            else: st.info("No hay ingresos editables.")
        else: st.info("Historial vacío.")
