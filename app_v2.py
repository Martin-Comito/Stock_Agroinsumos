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
    corregir_movimiento, verificar_login, mover_a_guarda, baja_uso_interno,
    registrar_reconteo, editar_reconteo_pendiente, aprobar_ajuste_stock, rechazar_reconteo,
    obtener_ids_productos_con_movimiento,
    registrar_incidencia, resolver_incidencia
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
        div[data-testid="stVerticalBlockBorderWrapper"] { text-align: center !important; align-items: center !important; }
        .card-icon, .card-title, .card-desc { margin-left: auto !important; margin-right: auto !important; text-align: center !important; display: block !important; }
        div[data-testid="stVerticalBlockBorderWrapper"] button { width: 100% !important; display: block !important; margin-left: auto !important; margin-right: auto !important; }
        .stButton { width: 100% !important; display: flex !important; justify-content: center !important; }
    }
    </style>
    """, unsafe_allow_html=True)

# GESTOR DE COOKIES
cookie_manager = stx.CookieManager()

# VARIABLES DE SESIÓN
if 'usuario_id' not in st.session_state: st.session_state.usuario_id = None
if 'usuario_nombre' not in st.session_state: st.session_state.usuario_nombre = None
if 'usuario_sucursal' not in st.session_state: st.session_state.usuario_sucursal = None
if 'usuario_rol' not in st.session_state: st.session_state.usuario_rol = None 
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
                st.session_state.usuario_rol = user_data.get('rol', 'OPERARIO').upper()
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
                    st.session_state.usuario_rol = user.get('rol', 'OPERARIO').upper()
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
    U_ROL = st.session_state.usuario_rol

    # SIDEBAR
    with st.sidebar:
        st.title("🚜")
        st.write(f"👤 **{U_NOMBRE}**")
        st.caption(f"Rol: {U_ROL}") 
        st.info(f"**{U_SUCURSAL}**")
        if st.button("Cerrar Sesión", type="secondary"):
            try: cookie_manager.delete('agro_user')
            except: pass
            
            st.session_state.logout_triggered = True 
            st.session_state.usuario_id = None
            st.session_state.usuario_nombre = None
            st.session_state.usuario_rol = None
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
        
        if U_ROL == 'ADMIN':
            # MENU ADMIN (7 SECCIONES)
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
                    tarjeta("📦", "PEDIDOS", "Validar")
                    if st.button("VALIDAR", key="b3", type="primary"): navegar_a("Validacion")
            
            st.write("")
            c4, c5, c6, c7 = st.columns(4)
            with c4:
                with st.container(border=True):
                    tarjeta("🔍", "RECONTEO", "Control")
                    if st.button("CONTAR", key="b4", type="primary"): navegar_a("Reconteo")
            with c5:
                with st.container(border=True):
                    tarjeta("📊", "STOCK", "Ver")
                    if st.button("VER STOCK", key="b5", type="primary"): navegar_a("Stock")
            with c6:
                with st.container(border=True):
                    tarjeta("📜", "HISTORIAL", "Logs")
                    if st.button("HISTORIAL", key="b6", type="primary"): navegar_a("Historial")
            with c7:
                with st.container(border=True):
                    tarjeta("👮", "AUDITORÍA", "Aprobar")
                    if st.button("AUDITAR", key="b7", type="secondary"): navegar_a("Aprobaciones")

        else:
            # MENU OPERARIO 
            c1, c2, c3 = st.columns(3)
            with c1:
                with st.container(border=True):
                    tarjeta("📥", "INGRESOS", "Alta")
                    if st.button("INGRESAR", key="b1_op", type="primary"): navegar_a("Ingresos")
            with c2:
                with st.container(border=True):
                    tarjeta("📝", "ÓRDENES", "Pedidos")
                    if st.button("CREAR ORDEN", key="b2_op", type="primary"): navegar_a("Ordenes")
            with c3:
                # PEDIDOS (VALIDACIÓN)
                with st.container(border=True):
                    tarjeta("📦", "PEDIDOS", "Salidas")
                    if st.button("VALIDAR", key="b3_op", type="primary"): navegar_a("Validacion")

            st.write("")
            c4, c5, c6 = st.columns(3)
            with c4:
                with st.container(border=True):
                    tarjeta("🔍", "RECONTEO", "Control")
                    if st.button("CONTAR", key="b4_op", type="primary"): navegar_a("Reconteo")
            with c5:
                with st.container(border=True):
                    tarjeta("📊", "STOCK", "Semáforo")
                    if st.button("VER STOCK", key="b5_op", type="primary"): navegar_a("Stock")
            with c6:
                with st.container(border=True):
                    tarjeta("🏗️", "ZAMPING", "Mover")
                    if st.button("REUBICAR", key="b6_op", type="primary"): navegar_a("Zamping")
        
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
                detalle_origen = col_det.text_input("👤 Nombre del Cliente (Devolución)").strip().upper()
            elif motivo_base == "TRANSFERENCIA SUCURSAL":
                detalle_origen = col_det.text_input("🏢 Sucursal de Origen").strip().upper()
            elif motivo_base == "COMPRA PROVEEDOR":
                detalle_origen = col_det.text_input("🏭 Proveedor (Opcional)").strip().upper()

            st.write("---")
            es_nuevo = st.checkbox("🆕 ¿Es Producto Nuevo?")
            c1, c2, c3 = st.columns(3)
            prod_id = None
            if es_nuevo:
                nom = c1.text_input("Nombre Nuevo").strip().upper(); cat = c1.text_input("Categoría").strip().upper()
            else:
                if p_map: p_sel = c1.selectbox("Producto", list(p_map.keys())); prod_id = p_map[p_sel]['id']
                else: es_nuevo = True
            
            lote_input = c1.text_input("Lote").strip().upper()
            senasa_input = c2.text_input("SENASA").strip().upper()
            gtin_input = c2.text_input("GTIN").strip().upper()
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
            cli = st.text_input("Cliente / Destino").strip().upper()
            if p_map:
                p_sel = st.selectbox("Buscar Producto", list(p_map.keys()))
                lotes = supabase.table("lotes_stock").select("id, numero_lote, cantidad_actual, ubicaciones_internas(nombre_sector)")\
                    .eq("producto_id", p_map[p_sel]).eq("sucursal_id", U_SUCURSAL).eq("estado_calidad", "DISPONIBLE").gt("cantidad_actual", 0).execute()
                
                if lotes.data:
                    stock_real_map = {l['id']: float(l['cantidad_actual']) for l in lotes.data}
                    l_opts = {f"{l['ubicaciones_internas']['nombre_sector']} | Lote: {l['numero_lote']} | Disp: {fmt(l['cantidad_actual'])}": l['id'] for l in lotes.data}
                    l_pick_str = st.selectbox("Seleccionar Lote y Ubicación", list(l_opts.keys()))
                    lote_seleccionado_id = l_opts[l_pick_str]
                    
                    total_pedir, bultos, unitario = calculadora_stock("ord")
                    
                    disp_real = stock_real_map.get(lote_seleccionado_id, 0)
                    exceso = total_pedir > disp_real
                    confirmacion_exceso = False

                    if total_pedir > 0:
                        if exceso:
                            st.warning(f"⚠️ ATENCIÓN: Estás pidiendo {fmt(total_pedir)}, pero en sistema figuran {fmt(disp_real)}.")
                            st.caption("¿Confirmas que quieres agregarlo de todas formas? (Quedará stock negativo)")
                            confirmacion_exceso = st.checkbox("✅ Sí, agregar igual.")
                        
                        boton_habilitado = (not exceso) or (exceso and confirmacion_exceso)

                        if st.button("AGREGAR AL PEDIDO", disabled=not boton_habilitado, type="primary" if boton_habilitado else "secondary"):
                            st.session_state.carrito.append({
                                "producto_id": p_map[p_sel], "nombre": p_sel, 
                                "cantidad": total_pedir, "lote_id": lote_seleccionado_id, 
                                "detalle_bultos": f"Ped: {fmt(bultos)} x {fmt(unitario)}"
                            })
                            st.rerun()
                else: st.warning("⚠️ Sin Stock Disponible")

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
                    l_real = c1.text_input("Confirmar Lote Físico", key=f"lr_{item['id']}").strip().upper()
                    
                    # CORRECCION IMPORTANTE: Definir l_esp fuera del botón para evitar NameError
                    l_esp = lote_txt.strip().upper() 
                    
                    st.caption("Validar Cantidad Real:")
                    total_real_calc, b, u = calculadora_stock(f"val_{item['id']}")
                    
                    if st.button("VALIDAR", key=f"v_{item['id']}", type="primary"):
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
        
        filtro = st.text_input("🔍 Buscar...").strip().upper()
        # AGREGADA PESTAÑA 4: Historial de Movimientos (Para Operario)
        tab1, tab2, tab3, tab4 = st.tabs(["📋 Listado General", "🚨 Reportar Rotura/Incidencia", "🗑️ Baja Uso Interno", "📜 Historial Movimientos"])

        # TAB 1: LISTADO
        with tab1:
            res = supabase.table("lotes_stock").select("*, productos(nombre_comercial), ubicaciones_internas(nombre_sector)").eq("sucursal_id", U_SUCURSAL).gt("cantidad_actual", 0).execute()
            if res.data:
                data = []
                hoy = datetime.now().date()
                for i in res.data:
                    nom = i['productos']['nombre_comercial'].upper(); lot = i['numero_lote'].upper()
                    if filtro in nom or filtro in lot:
                        venc_str = i['fecha_vencimiento']; venc = datetime.strptime(venc_str, '%Y-%m-%d').date() if venc_str else None
                        dias = (venc - hoy).days if venc else 999
                        
                        calidad = i.get('estado_calidad', 'DISPONIBLE')
                        est = "🟢 OK"
                        if calidad == "GUARDA": est = "🟠 EN GUARDA"
                        elif dias < 30: est = "🔴 VENCE PRONTO"
                        elif dias < 90: est = "🟡 ALERTA VENC"
                        
                        data.append({
                            "UBIC": i['ubicaciones_internas']['nombre_sector'], 
                            "PROD": nom, 
                            "LOTE": lot, 
                            "CANT": fmt(i['cantidad_actual']), 
                            "ESTADO": est, 
                            "VENC": venc_str
                        })
                st.dataframe(pd.DataFrame(data), use_container_width=True)
            else: st.info("Sin stock.")

        # TAB 2: INCIDENCIA / ROTURA
        with tab2:
            st.caption("⚠️ Reportar mercadería rota o pinchada (No afecta stock hasta aprobación del Admin).")
            lotes_sanos = supabase.table("lotes_stock").select("id, numero_lote, cantidad_actual, productos(nombre_comercial)")\
                .eq("sucursal_id", U_SUCURSAL).gt("cantidad_actual", 0).execute()
            
            if lotes_sanos.data:
                opts_sanos = {f"{x['productos']['nombre_comercial']} | Lote: {x['numero_lote']} | Disp: {fmt(x['cantidad_actual'])}": x for x in lotes_sanos.data}
                sel_sano = st.selectbox("Seleccionar Producto Afectado", list(opts_sanos.keys()))
                dato_sano = opts_sanos[sel_sano]
                
                c1, c2 = st.columns(2)
                cant_rotura = c1.number_input("Cantidad Rota/Pinchada", min_value=0.0, max_value=float(dato_sano['cantidad_actual']), step=1.0)
                
                # LOGICA PARA "OTROS"
                motivo_preliminar = c2.selectbox("Motivo", ["ROTO", "PINCHADO", "VENCIDO", "HUMEDAD", "OTROS"])
                motivo_final_input = ""
                if motivo_preliminar == "OTROS":
                    motivo_final_input = c2.text_input("Especifique el motivo:").strip().upper()
                
                if st.button("🚨 REPORTAR INCIDENCIA", type="primary"):
                    # Determinar motivo final
                    motivo_a_guardar = motivo_preliminar
                    if motivo_preliminar == "OTROS":
                        if not motivo_final_input:
                            st.error("Debe especificar el motivo.")
                            st.stop()
                        motivo_a_guardar = f"OTROS: {motivo_final_input}"

                    if cant_rotura > 0:
                        if registrar_incidencia(dato_sano['id'], cant_rotura, motivo_a_guardar, U_NOMBRE, U_SUCURSAL):
                            st.success("✅ Reporte enviado al Administrador."); 
                            time.sleep(2); st.rerun()
                        else: st.error("Error al enviar el reporte. Verifique conexión.")
                    else:
                        st.warning("La cantidad debe ser mayor a 0.")
            else: st.info("No hay stock disponible para reportar.")

        # TAB 3: BAJA
        with tab3:
            st.caption("Dar de baja definitiva mercadería que está en 'Guarda'.")
            lotes_guarda = supabase.table("lotes_stock").select("id, numero_lote, cantidad_actual, productos(nombre_comercial)")\
                .eq("sucursal_id", U_SUCURSAL).eq("estado_calidad", "GUARDA").gt("cantidad_actual", 0).execute()
            
            if lotes_guarda.data:
                opts_guarda = {f"{x['productos']['nombre_comercial']} | Lote: {x['numero_lote']} | En Guarda: {fmt(x['cantidad_actual'])}": x for x in lotes_guarda.data}
                sel_guarda = st.selectbox("Seleccionar Producto en Guarda", list(opts_guarda.keys()))
                dato_guarda = opts_guarda[sel_guarda]
                
                c1, c2 = st.columns(2)
                cant_baja = c1.number_input("Cantidad a dar de Baja", min_value=0.0, max_value=float(dato_guarda['cantidad_actual']), step=1.0)
                motivo_baja = c2.text_input("Motivo (Ej: Uso en Parque)")
                
                if st.button("CONFIRMAR BAJA DEFINITIVA"):
                    if cant_baja > 0 and motivo_baja:
                        if baja_uso_interno(dato_guarda['id'], cant_baja, motivo_baja, U_NOMBRE):
                            st.success("✅ Baja realizada correctamente."); time.sleep(1.5); st.rerun()
                    else: st.error("Ingrese cantidad y motivo.")
            else: st.info("No hay mercadería en Guarda.")

        # TAB 4: HISTORIAL 
        with tab4:
            st.subheader("📜 Últimos Movimientos")
            h_op = supabase.table("historial_movimientos").select("fecha_hora, tipo_movimiento, cantidad_afectada, productos(nombre_comercial), lotes_stock(numero_lote)")\
                .eq("sucursal_id", U_SUCURSAL).order("fecha_hora", desc=True).limit(50).execute()
            
            if h_op.data:
                data_hist = []
                arg_tz = pytz.timezone('America/Argentina/Buenos_Aires')
                for x in h_op.data:
                    try:
                        dt_utc = datetime.fromisoformat(x['fecha_hora'].replace('Z', '+00:00'))
                        fecha_str = dt_utc.astimezone(arg_tz).strftime('%d/%m %H:%M')
                    except: fecha_str = x['fecha_hora']
                    
                    prod_nom = x['productos']['nombre_comercial'] if x['productos'] else "Desconocido"
                    lote_nom = x['lotes_stock']['numero_lote'] if x['lotes_stock'] else "-"
                    
                    data_hist.append({
                        "FECHA": fecha_str,
                        "PRODUCTO": prod_nom,
                        "LOTE": lote_nom,
                        "MOVIMIENTO": x['tipo_movimiento'],
                        "CANT": fmt(x['cantidad_afectada'])
                    })
                st.dataframe(pd.DataFrame(data_hist), use_container_width=True)
            else:
                st.info("No hay movimientos recientes.")

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
        
        # Solo Admin puede editar maestro
        if U_ROL == 'ADMIN':
            with st.expander("🛠️ Gestión de Productos (Maestro)"):
                all_prods = supabase.table("productos").select("id, nombre_comercial, categoria").order("nombre_comercial").execute()
                if all_prods.data:
                    p_dict = {p['nombre_comercial']: p for p in all_prods.data}
                    p_sel_edit = st.selectbox("Seleccionar Producto", list(p_dict.keys()), key="master_edit_sel")
                    ce1, ce2 = st.columns(2)
                    new_name = ce1.text_input("Nuevo Nombre", value=p_sel_edit).strip().upper()
                    new_cat = ce2.text_input("Nueva Categoría", value=p_dict[p_sel_edit].get('categoria', '') or "").strip().upper()
                    if st.button("GUARDAR CAMBIOS EN MAESTRO", type="primary"):
                        if editar_producto(p_dict[p_sel_edit]['id'], new_name, new_cat): st.success(f"✅ Producto actualizado"); st.rerun()
        
        st.write("---")
        busqueda = st.text_input("🔍 Buscar en Historial", placeholder="Producto, Lote...").strip().upper()
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
            
            # Solo Admin puede corregir transacciones
            if U_ROL == 'ADMIN':
                st.write("---")
                st.subheader("✏️ Corregir Transacción")
                opciones = {f"{r['PRODUCTO']} | Lote: {r['LOTE']} | {r['CANTIDAD']}": r['RAW_DATA'] for index, r in df.iterrows() if r['MOVIMIENTO'] == 'INGRESO'}
                if opciones:
                    seleccion = st.selectbox("Seleccionar Movimiento", list(opciones.keys()))
                    dato = opciones[seleccion]
                    with st.form("form_correccion_hist"):
                        c1, c2 = st.columns(2)
                        lote_actual = dato['lotes_stock']['numero_lote'] if dato['lotes_stock'] else ""
                        nuevo_lote = c1.text_input("Corregir Lote", value=lote_actual).strip().upper()
                        cant_actual = float(dato['cantidad_afectada'])
                        nueva_cant = c2.number_input("Corregir Cantidad Real", value=cant_actual)
                        if st.form_submit_button("GUARDAR CORRECCIÓN TOTAL", type="primary"):
                            if corregir_movimiento(dato['id'], dato['lote_id'], nuevo_lote, nueva_cant, dato['lotes_stock']['fecha_vencimiento'], dato['lotes_stock']['senasa_codigo'], dato['lotes_stock']['gtin_codigo'], U_NOMBRE): st.success("✅ Todo actualizado."); st.rerun()
                else: st.info("No hay ingresos editables.")
        else: st.info("Historial vacío.")


    # VISTA: RECONTEO (CON FILTRO DE TIEMPO)
    elif st.session_state.vista == "Reconteo":
        c_h, c_b = st.columns([4, 1])
        c_h.header("🔍 Reconteo Cíclico")
        if c_b.button("VOLVER", type="secondary"): navegar_a("Menu Principal")

        tab_nuevo, tab_pend = st.tabs(["📝 Nuevo Conteo", "✏️ Mis Pendientes"])

        with tab_nuevo:
            st.subheader("Filtrar Productos por Actividad")
            
            # 1. SELECTOR DE PERIODO
            periodo = st.radio(
                "Mostrar productos que tuvieron movimiento en:",
                ["Todo (General)", "Última Semana", "Último Mes", "Último Año"],
                horizontal=True
            )

            # 2. OBTENER PRODUCTOS (MAESTRO)
            all_prods_query = supabase.table("productos").select("id, nombre_comercial").order("nombre_comercial").execute()
            
            p_map_filtrado = {} 

            if all_prods_query.data:
                full_map = {p['nombre_comercial']: p['id'] for p in all_prods_query.data}
                
                # 3. APLICAR FILTRO
                if periodo == "Todo (General)":
                    p_map_filtrado = full_map
                else:
                    dias = 7
                    if periodo == "Último Mes": dias = 30
                    elif periodo == "Último Año": dias = 365
                    
                    with st.spinner(f"Buscando movimientos de los últimos {dias} días..."):
                        ids_activos = obtener_ids_productos_con_movimiento(U_SUCURSAL, dias)
                    
                    if ids_activos:
                        # Filtramos el mapa completo
                        p_map_filtrado = {k: v for k, v in full_map.items() if v in ids_activos}
                        st.info(f"🔍 Se encontraron **{len(p_map_filtrado)}** productos con movimiento en este periodo.")
                    else:
                        st.warning("⚠️ No hubo movimientos en este periodo.")

                # 4. DROPDOWN DE SELECCIÓN
                if p_map_filtrado:
                    p_sel = st.selectbox("Seleccionar Producto a Contar", list(p_map_filtrado.keys()))
                    
                    if p_sel:
                        pid = p_map_filtrado[p_sel]
                        # Buscar lotes de ese producto
                        lotes = supabase.table("lotes_stock").select("id, numero_lote, cantidad_actual, ubicaciones_internas(nombre_sector)")\
                            .eq("producto_id", pid).eq("sucursal_id", U_SUCURSAL).gt("cantidad_actual", 0).execute()
                        
                        if lotes.data:
                            l_opts = {f"Lote: {l['numero_lote']} | Ubic: {l['ubicaciones_internas']['nombre_sector']}": l for l in lotes.data}
                            l_sel = st.selectbox("Seleccionar Lote Físico", list(l_opts.keys()))
                            dato_lote = l_opts[l_sel]
                            
                            st.write("---")
                            st.info(f"💾 Stock en Sistema: **{fmt(dato_lote['cantidad_actual'])}**")
                            
                            c1, c2 = st.columns(2)
                            fisico = c1.number_input("🔢 Cantidad Física Real", min_value=0.0, step=1.0)
                            
                            diff = fisico - float(dato_lote['cantidad_actual'])
                            
                            motivo = ""
                            if diff != 0:
                                if diff > 0: st.success(f"📈 SOBRANTE: +{fmt(diff)}")
                                else: st.error(f"📉 FALTANTE: {fmt(diff)}")
                                
                                motivo = st.text_area("📝 Motivo de la diferencia (Obligatorio)", placeholder="Ej: Mal conteo anterior, rotura no reportada...")
                                
                                if st.button("REGISTRAR INCIDENCIA", type="primary"):
                                    if motivo:
                                        if registrar_reconteo(pid, dato_lote['id'], float(dato_lote['cantidad_actual']), fisico, motivo, U_NOMBRE, U_SUCURSAL):
                                            st.success("✅ Incidencia enviada a aprobación del Admin."); time.sleep(1.5); st.rerun()
                                        else: st.error("Error al guardar.")
                                    else:
                                        st.warning("⚠️ Debe escribir un motivo.")
                            else:
                                st.caption("✅ El stock coincide.")

                        else: st.warning("Este producto tuvo movimiento, pero actualmente figura con Stock 0 en sistema.")
                else:
                    if periodo != "Todo (General)":
                        st.info("Intenta cambiar el periodo de tiempo.")

        with tab_pend:
            # Editar incidencias propias que aun no revisó el admin
            mis_pend = supabase.table("reconteos").select("*, productos(nombre_comercial), lotes_stock(numero_lote)")\
                .eq("usuario_solicitante", U_NOMBRE).eq("estado", "PENDIENTE").execute()
            
            if mis_pend.data:
                for item in mis_pend.data:
                    with st.expander(f"{item['productos']['nombre_comercial']} | Lote: {item['lotes_stock']['numero_lote']}"):
                        st.write(f"Sistema: {item['cantidad_sistema']} | **Tú contaste: {item['cantidad_fisica']}**")
                        st.write(f"Motivo actual: {item['motivo']}")
                        
                        c_e1, c_e2 = st.columns(2)
                        new_fis = c_e1.number_input("Corregir Cantidad", value=float(item['cantidad_fisica']), key=f"nf_{item['id']}")
                        new_mot = c_e2.text_input("Corregir Motivo", value=item['motivo'], key=f"nm_{item['id']}")
                        
                        if st.button("ACTUALIZAR CONTEO", key=f"upd_{item['id']}"):
                            editar_reconteo_pendiente(item['id'], new_fis, float(item['cantidad_sistema']), new_mot)
                            st.success("Corregido."); st.rerun()
            else:
                st.info("No tienes reconteos pendientes de aprobación.")

    # VISTA: APROBACIONES 
    elif st.session_state.vista == "Aprobaciones":
        if U_ROL != 'ADMIN': navegar_a("Menu Principal")
        
        c_h, c_b = st.columns([4, 1])
        c_h.header("👮 Auditoría y Aprobaciones")
        if c_b.button("VOLVER", type="secondary"): navegar_a("Menu Principal")

        tab_ajustes, tab_roturas = st.tabs(["Ajustes de Inventario", "Bajas por Rotura"])

        # TAB 1: AJUSTES DE INVENTARIO 
        with tab_ajustes:
            pendientes = supabase.table("reconteos").select("*, productos(nombre_comercial), lotes_stock(numero_lote)")\
                .eq("sucursal_id", U_SUCURSAL).eq("estado", "PENDIENTE").order("created_at").execute()

            if pendientes.data:
                for p in pendientes.data:
                    with st.container(border=True):
                        c1, c2, c3, c4 = st.columns([2, 1, 2, 1])
                        c1.markdown(f"**{p['productos']['nombre_comercial']}**\nLote: {p['lotes_stock']['numero_lote']}")
                        c1.caption(f"👤 {p['usuario_solicitante']} | 📅 {p['created_at'][:10]}")
                        
                        c2.metric("Diferencia", f"{fmt(p['diferencia'])}", delta_color="off")
                        
                        c3.warning(f"🗣️ Motivo: {p['motivo']}")
                        c3.write(f"Sis: {fmt(p['cantidad_sistema'])} ➡️ **Fís: {fmt(p['cantidad_fisica'])}**")
                        
                        if c4.button("✅ APROBAR", key=f"apr_{p['id']}", type="primary"):
                            if aprobar_ajuste_stock(p['id'], U_NOMBRE):
                                st.toast("Ajuste realizado"); time.sleep(1); st.rerun()
                        
                        if c4.button("❌ RECHAZAR", key=f"rec_{p['id']}", type="secondary"):
                            rechazar_reconteo(p['id'])
                            st.toast("Rechazado"); time.sleep(1); st.rerun()
            else:
                st.info("✅ No hay ajustes de conteo pendientes.")

        # TAB 2: GESTIÓN DE INCIDENCIAS
        with tab_roturas:
            incidencias = supabase.table("incidencias").select("*, lotes_stock(numero_lote, productos(nombre_comercial))")\
                .eq("sucursal_id", U_SUCURSAL).eq("estado", "PENDIENTE").execute()
            
            if incidencias.data:
                for inc in incidencias.data:
                    with st.container(border=True):
                        st.markdown(f"### ⚠️ {inc['lotes_stock']['productos']['nombre_comercial']}")
                        st.caption(f"Lote: {inc['lotes_stock']['numero_lote']} | Reportado por: {inc['usuario_solicitante']} | Fecha: {inc['created_at'][:10]}")
                        
                        c_info, c_action = st.columns([3, 1])
                        with c_info:
                            st.error(f"Motivo: {inc['motivo']}")
                            st.metric("Cantidad a dar de Baja", fmt(inc['cantidad']))
                        
                        with c_action:
                            if st.button("✅ DAR DE BAJA", key=f"baja_{inc['id']}", type="primary"):
                                if resolver_incidencia(inc['id'], 'APROBAR', U_NOMBRE):
                                    st.success("Stock descontado correctamente."); time.sleep(1); st.rerun()
                                else:
                                    st.error("Error: Tal vez ya no hay stock suficiente.")
                            
                            if st.button("❌ FALSA ALARMA", key=f"fake_{inc['id']}", type="secondary"):
                                if resolver_incidencia(inc['id'], 'RECHAZAR', U_NOMBRE):
                                    st.info("Reporte descartado. Stock intacto."); time.sleep(1); st.rerun()
            else:
                st.info("✅ No hay reportes de rotura pendientes.")
