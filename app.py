import streamlit as st
import streamlit_authenticator as stauth
from st_supabase_connection import SupabaseConnection
import google.generativeai as genai
import yaml
from yaml.loader import SafeLoader
import PyPDF2
from datetime import datetime
import pandas as pd

# 1. CONFIGURACIÓN DE LA IA (Usa tu propia API Key)
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# Conexión profesional a Supabase
# conn = st.connection("supabase", type=SupabaseConnection)ç

# Solo si el secreto falla y tienes prisa:
conn = st.connection(
    "supabase",
    type=SupabaseConnection,
    # url="https://ovxzfgyyixbfawuobovq.supabase.co",
    url=st.secrets["url_supabase"],
    # key="sb_publishable_-dtEZ32pPPuTo8LHWCRm6g_Wf7n4SFY"
    key=st.secrets["key_supabase"]
)




# 2. SISTEMA DE AUTENTICACIÓN
with open('auth_config.yaml') as file:
    config = yaml.load(file, Loader=SafeLoader)

authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days']
)

# --- PARTE CORREGIDA DEL LOGIN ---
# En la versión 0.3.1, solo llamamos al método y él gestiona el estado internamente
authenticator.login()

if st.session_state["authentication_status"] is False:
    st.error('Usuario o contraseña incorrectos')
elif st.session_state["authentication_status"] is None:
    st.warning('Por favor, introduce tus credenciales para acceder al panel del IES San Andrés.')

elif st.session_state["authentication_status"]:
    # Ahora recuperamos los datos de la sesión de Streamlit
    username = st.session_state["username"]
    name = st.session_state["name"]
    
    # El resto del código sigue igual, pero usando estas variables
    user_data = config['credentials']['usernames'][username]
    rol = user_data['role']
    
    st.sidebar.title(f"Bienvenido, {name}")
    authenticator.logout('Cerrar sesión', 'sidebar')
    

    # FECHA ACTUAL PARA EL SEGUIMIENTO (19 de Marzo de 2026)
    hoy = datetime(2026, 3, 19)

    # VISTA PARA EL ALUMNO
    if rol == 'estudiante':
        ciclo = user_data['ciclo']
        st.header(f"Seguimiento de Proyecto - Ciclo {ciclo}")
        
        hito = st.selectbox("Selecciona la entrega a evaluar:", 
                            ["Fase 1: Planificación", "Fase 2: Diseño", "Fase 3: Desarrollo"])

        archivo = st.file_uploader("Sube tu memoria actual (PDF)", type=["pdf"])

        if archivo:
            with st.spinner('El Tutor IA está revisando tu documento...'):
                # Extraer texto para la IA
                reader = PyPDF2.PdfReader(archivo)
                texto_alumno = ""
                for page in reader.pages:
                    texto_alumno += page.extract_text()

                # Prompt configurado con la normativa del centro
                prompt = f"""
                Eres el tutor IA del IES San Andrés para el ciclo {ciclo}. 
                Analiza el siguiente texto según:
                
                1. REGLAS FORMALES: 
                   - Márgenes: 2,5cm (sup/inf/izq) y 2cm (der).
                   - Interlineado: 1,5. Texto justificado.
                   - Fuente: Arial/Times 12 (títulos 14).
                
                2. CONTENIDO MÍNIMO: 
                   - Verifica si están los 7 puntos del esquema básico.
                   
                3. PLAZOS (Hoy es 19/03/2026):
                   - Si es DAM, la Fase 1 venció el 13/03/2026.
                   - Si es ASIR, la Fase 1 vence mañana 20/03/2026.
                   - Si es SMR, la Fase 1 venció el 11/03/2026.

                Texto del alumno:
                {texto_alumno}
                """

                print("*******************************************************************")
                for m in genai.list_models():
                    if 'generateContent' in m.supported_generation_methods:
                        print(f"Modelo disponible: {m.name}")
                print("*******************************************************************")

                model = genai.GenerativeModel('gemini-2.5-flash')
                response = model.generate_content(prompt)
                
                st.subheader("Feedback de tu Tutor")
                st.markdown(response.text)

        if st.button("Registrar Entrega en Supabase"):
        # Lógica de puntualidad (Hoy 19/03/2026)
            hoy_str = datetime(2026, 3, 19).strftime("%d/%m/%Y")
            plazos = {"DAM": "13/03/2026", "ASIR": "20/03/2026", "SMR": "11/03/2026"}
            
            # Guardar en la base de datos
            nuevo_registro = {
                "fecha": hoy_str,
                "alumno": name,
                "ciclo": ciclo,
                "hito": hito,
                "estado_formato": "Revisado (Margen 2.5cm / Int. 1.5)",
                "puntualidad": "A tiempo" if ciclo == "ASIR" else "Retraso",
                "observaciones_ia": response.text[:500] # El feedback de Gemini
            }
            
            try:
                conn.table("seguimiento").insert(nuevo_registro).execute()
                st.success("✅ Entrega registrada permanentemente en la base de datos.")
            except Exception as e:
                st.error(f"Error al guardar: {e}")
        
        # if st.button("Registrar Entrega y Notificar al Tutor"):
        #     # 1. Determinar puntualidad según calendario real
        #     hoy = datetime(2026, 3, 19)
        #     plazos = {"DAM": datetime(2026, 3, 13), "ASIR": datetime(2026, 3, 20), "SMR": datetime(2026, 3, 11)}
        #     entrega_a_tiempo = "A tiempo" if hoy <= plazos[ciclo] else "Retraso"

        #     # 2. Preparar nueva fila
        #     nueva_entrega = pd.DataFrame([{
        #         "Fecha": hoy.strftime("%d/%m/%Y"),
        #         "Alumno": name,
        #         "Ciclo": ciclo,
        #         "Hito": hito,
        #         "Estado_Formato": "Revisado por IA", # Aquí podrías extraer info de la respuesta de Gemini
        #         "Puntualidad": entrega_a_tiempo,
        #         "Observaciones_IA": response.text[:200] # Resumen del feedback
        #     }])

        #     # 3. Actualizar Google Sheets
        #     existente = conn.read(worksheet="Sheet1")
        #     actualizado = pd.concat([existente, nueva_entrega], ignore_index=True)
        #     conn.update(worksheet="Sheet1", data=actualizado)
        #     st.success("Tu entrega ha sido registrada correctamente en el panel del profesor.")

    # VISTA PARA EL PROFESOR
    elif rol == 'profesor':
        st.header("👨‍🏫 Panel de Control de Tutoría")
        st.subheader("Seguimiento de Proyectos Intermodulares 2025/2026")

        try:
            # 1. Recuperar datos reales desde Supabase
            res = conn.table("seguimiento").select("*").execute()
            df = pd.DataFrame(res.data)

            if df.empty:
                st.info("Aún no hay entregas registradas en la base de datos.")
            else:
                # 2. Métricas Rápidas (Contexto: 19/03/2026)
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Entregas", len(df))
                with col2:
                    entregas_asir = len(df[df['ciclo'] == 'ASIR'])
                    st.metric("Entregas ASIR", entregas_asir, help="Plazo: Mañana 20/03")
                with col3:
                    retrasos = len(df[df['puntualidad'] == 'Retraso'])
                    st.metric("Alertas de Retraso", retrasos, delta_color="inverse")


                # 3. Filtros Interactivos
                st.divider()
                ciclo_sel = st.multiselect("Filtrar por Ciclo:", ["DAM", "ASIR", "SMR"], default=["DAM", "ASIR", "SMR"])
                df_filtrado = df[df['ciclo'].isin(ciclo_sel)]

                # 4. Tabla de Seguimiento Detallada
                st.write("### Historial de Revisiones de la IA")
                st.dataframe(
                    df_filtrado[['fecha', 'alumno', 'ciclo', 'hito', 'puntualidad', 'estado_formato']], 
                    use_container_width=True,
                    hide_index=True
                )



                # --- ESTADÍSTICAS VISUALES (CORREGIDO) ---
                st.divider()
                st.subheader("📊 Estado de Entregas por Ciclo")

                # 1. Agrupamos los datos
                chart_data = df_filtrado.groupby(['ciclo', 'puntualidad']).size().unstack(fill_value=0)

                # 2. Definimos un mapa de colores lógico para el IES San Andrés
                color_map = {
                    "A tiempo": "#2ecc71", # Verde
                    "Retraso": "#e74c3c"   # Rojo
                }

                # 3. Creamos la lista de colores solo para las columnas que EXISTEN en chart_data
                # Esto evita el error de "misma longitud"
                colores_actuales = [color_map[col] for col in chart_data.columns if col in color_map]

                # 4. Mostramos la gráfica
                st.bar_chart(chart_data, color=colores_actuales)
                
                st.caption("Verde: A tiempo | Rojo: Con retraso (según calendario oficial 2025/2026)")


                # 5. Generador de Informe para el Tribunal
                st.divider()
                st.subheader("📝 Generar Informe Oficial para el Tribunal")
                st.write("Este informe resume el cumplimiento de los **aspectos formales** y la **planificación**.")
                
                alumno_sel = st.selectbox("Selecciona un alumno para el informe:", df_filtrado['alumno'].unique())
                
                if st.button(f"Generar Informe de {alumno_sel}"):
                    # Obtenemos la última entrega de ese alumno
                    datos = df_filtrado[df_filtrado['alumno'] == alumno_sel].iloc[-1]
                    
                    # Plantilla del informe basada en la normativa del IES San Andrés
                    informe_final = f"""
                        INFORME DE SEGUIMIENTO DEL TUTOR - PROYECTO 2025/2026
                        ------------------------------------------------------
                        CENTRO: IES San Andrés
                        FECHA DE EMISIÓN: {datetime.now().strftime('%d/%m/%Y')}
                        ------------------------------------------------------

                        DATOS DEL ALUMNO:
                        Nombre: {datos['alumno']}
                        Ciclo formativo: {datos['ciclo']}
                        Hito evaluado: {datos['hito']}

                        ESTADO DE CUMPLIMIENTO (SISTEMA IA):
                        1. Puntualidad: {datos['puntualidad']} (Fecha registro: {datos['fecha']})
                        2. Formato: {datos['estado_formato']}
                        - Márgenes (2.5cm / 2cm): Revisado
                        - Interlineado (1.5 / Justificado): Revisado

                        OBSERVACIONES TÉCNICAS (Gemini 3 Flash):
                        {datos['observaciones_ia']}

                        NOTAS PARA EL TRIBUNAL DE DEFENSA:
                        - El alumno debe presentar durante 20-30 minutos.
                        - Asegurar que se entrega el archivo 'leeme.txt' en el soporte digital.
                        - El esquema básico debe contener los 7 apartados obligatorios.

                        ------------------------------------------------------
                        Fdo: Tutor de Proyecto Individual
                    """
                    
                    st.text_area("Previsualización del Informe:", informe_final, height=300)
                    
                    st.download_button(
                        label="📥 Descargar Informe (TXT)",
                        data=informe_final,
                        file_name=f"Informe_Tribunal_{alumno_sel.replace(' ', '_')}.txt",
                        mime="text/plain"
                    )

        except Exception as e:
            st.error(f"Error al conectar con la base de datos de Supabase: {e}")