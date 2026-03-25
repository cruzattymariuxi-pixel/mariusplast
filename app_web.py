import streamlit as st
import psycopg2
import pandas as pd
from datetime import date

# --- 1. CONFIGURACIÓN DE CONEXIÓN (POOLER SESIÓN) ---
# Usamos la URL exacta que te dio Supabase con el puerto 6543
URL_POOLER = "postgresql://postgres.wtnvbkugbpgqvooqubms:joe1307493013@://aws-0-us-west-2.pooler.supabase.com"

# --- CONEXIÓN DESARMADA (PARA EVITAR EL ERROR DE LOCALHOST) ---
try:
    conn = psycopg2.connect(
        user="postgres.wtnvbkugbpgqvooqubms",
        password="joe1307493013",
        host="aws-0-us-west-2.pooler.supabase.com", # El host .com que sí funciona
        port="6543", # El puerto del agrupador
        database="postgres",
        sslmode="require" # Obligatorio para Supabase
    )
    cursor = conn.cursor()
    st.sidebar.success("✅ ¡CONECTADO A LA NUBE POR POOLER!")
except Exception as e:
    st.error(f"❌ Error de conexión: {e}")
    st.stop()


# --- 2. INTERFAZ DEL SISTEMA ---
st.title("📦 Inventario Web Sincronizado")

menu = st.sidebar.selectbox("Seleccione una opción:", ["Ver Inventario", "Agregar/Editar", "Ventas"])

if menu == "Ver Inventario":
    st.header("📦 Stock Actual")
    busqueda = st.text_input("🔍 Buscar por nombre...")
    
    # Consulta usando %s e ILIKE (para que ignore mayúsculas)
    query = "SELECT * FROM productos WHERE nombre ILIKE %s ORDER BY nombre ASC"
    df = pd.read_sql(query, conn, params=(f'%{busqueda}%',))
    
    if not df.empty:
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No se encontraron productos o la tabla está vacía.")

elif menu == "Agregar/Editar":
    st.header("📝 Gestión de Mercadería")
    
    with st.form("form_prod"):
        col1, col2 = st.columns(2)
        with col1:
            id_p = st.number_input("ID (0 para nuevo, >0 para editar)", min_value=0)
            nom = st.text_input("Nombre")
            cat = st.text_input("Categoría")
            prov = st.text_input("Proveedor")
        with col2:
            p_c = st.number_input("Precio Compra", format="%.2f")
            p_v = st.number_input("Precio Menor", format="%.2f")
            p_m = st.number_input("Precio Mayor", format="%.2f")
            stk = st.number_input("Stock", min_value=0)
        
        btn = st.form_submit_button("✅ Guardar / Actualizar")

        if btn:
            try:
                if id_p == 0: # Nuevo
                    cursor.execute("""
                        INSERT INTO productos (nombre, categoria, proveedor, precio_compra, precio_venta, precio_mayor, stock) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (nom, cat, prov, p_c, p_v, p_m, stk))
                else: # Editar
                    cursor.execute("""
                        UPDATE productos SET nombre=%s, categoria=%s, proveedor=%s, precio_compra=%s, precio_venta=%s, precio_mayor=%s, stock=%s 
                        WHERE id=%s
                    """, (nom, cat, prov, p_c, p_v, p_m, stk, id_p))
                
                conn.commit()
                st.success("¡Datos guardados en la nube!")
                st.rerun()
            except Exception as e:
                st.error(f"Error al guardar: {e}")

elif menu == "Ventas":
    st.header("💰 Registrar Nueva Venta")

    
    # --- 1. BUSCADOR DINÁMICO EN VENTAS ---
# Agregamos una 'key' única para que Streamlit detecte el cambio al escribir
    busqueda_v = st.text_input("🔍 Escribe el nombre para buscar y vender...", key="buscador_ventas_rapido")

# Filtramos en tiempo real en la nube
# Usamos ILIKE para que no importe si escribes en mayúsculas o minúsculas
    query_v = "SELECT id, nombre, precio_venta, precio_mayor, stock FROM productos WHERE nombre ILIKE %s AND stock > 0 ORDER BY nombre ASC LIMIT 20"

    df_res = pd.read_sql(query_v, conn, params=(f'%{busqueda_v}%',))


    if not df_res.empty:
        # 2. Selección del producto
        nombres_productos = df_res['nombre'].tolist()
        producto_sel = st.selectbox("Seleccione el producto:", nombres_productos)
        
        # Obtener datos del producto elegido (iloc[0] corregido)
        datos_p = df_res[df_res['nombre'] == producto_sel].iloc[0]
        
        col_v1, col_v2, col_v3 = st.columns(3)
        
        with col_v1:
            cantidad = st.number_input("Cantidad", min_value=1, max_value=int(datos_p['stock']), step=1)
            st.caption(f"Disponible: {datos_p['stock']}")
            
        with col_v2:
            tipo_p = st.selectbox("Tipo de Precio", ["Menor", "Mayor"])
            precio_u = datos_p['precio_venta'] if tipo_p == "Menor" else datos_p['precio_mayor']
            st.write(f"Precio Unitario: **${precio_u:.2f}**")
            
        with col_v3:
            metodo = st.selectbox("Método de Pago", ["Contado", "Transferencia", "Crédito"])
            total = cantidad * precio_u
            st.metric("TOTAL A PAGAR", f"${total:.2f}")

        # 3. Botón para ejecutar la venta en la nube
        if st.button("🛒 Confirmar y Registrar Venta", use_container_width=True):
            try:
                hoy = date.today().strftime("%Y-%m-%d")
                
                # A. Registrar la venta
                cursor.execute("""
                    INSERT INTO ventas (producto, cantidad, precio, total, pago, fecha)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (producto_sel, cantidad, precio_u, total, metodo, hoy))
                
                # B. Descontar el stock en la nube
                nuevo_stock = int(datos_p['stock']) - cantidad
                cursor.execute("UPDATE productos SET stock = %s WHERE id = %s", (nuevo_stock, int(datos_p['id'])))
                
                conn.commit()
                st.success(f"✅ Venta exitosa: {cantidad}x {producto_sel}. Stock actualizado.")
                st.balloons()
                st.rerun()
                
            except Exception as e:
                st.error(f"Error al procesar la venta: {e}")
    else:
        st.warning("No hay productos con stock que coincidan con la búsqueda.")

    # 4. Mostrar historial reciente de la nube
    st.divider()
    st.subheader("📋 Últimas 5 Ventas registradas")
    df_historial = pd.read_sql("SELECT * FROM ventas ORDER BY id DESC LIMIT 5", conn)
    st.table(df_historial)
    

