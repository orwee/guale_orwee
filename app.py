
import streamlit as st
import pandas as pd
import requests
import re

# --- Configuración de la página y credenciales de Supabase ---
st.set_page_config(layout="wide", page_title="Dashboard de Pools")

# IMPORTANTE: Reemplaza estos valores con la URL y la clave de tu proyecto Supabase.
# La URL debe apuntar a tu tabla 'Tabla2'.
SUPABASE_URL = "http://dexbooster.xyz:8000/rest/v1/Tabla2" 
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.ewogICJyb2xlIjogImFub24iLAogICJpc3MiOiAic3VwYWJhc2UiLAogICJpYXQiOiAxNzExODIzNDAwLAogICJleHAiOiAxODY5NTg5ODAwCn0._PUNk_bUiDmRLuACQLuNSlbdMxdQ86wonXOTF9hLEME"

# Headers para la petición a la API
headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}"
}

# --- Funciones de Carga y Procesamiento de Datos ---

# Usamos el decorador de Streamlit para cachear la carga de datos
@st.cache_data
def load_data():
    """Carga los datos desde la API de Supabase y los filtra por memes=0."""
    # Columnas necesarias para el dashboard
    select_columns = "blockchain,dex,pair,tier,aprmensual,tvlmensual,memes"
    # Filtro para excluir memes
    params = {
        "select": select_columns,
        "memes": "eq.0" # Filtra donde la columna 'memes' sea igual a 0
    }
    
    try:
        response = requests.get(SUPABASE_URL, headers=headers, params=params)
        response.raise_for_status()  # Lanza un error si la petición falla
        data = response.json()
        df = pd.DataFrame(data)
        return df
    except requests.exceptions.RequestException as e:
        st.error(f"Error al conectar con la base de datos: {e}")
        return pd.DataFrame() # Devuelve un DataFrame vacío en caso de error

def clean_numeric_text(series):
    """
    Convierte una columna de texto (ej. '$1.5M', '50.2K%') a valores numéricos.
    """
    # Rellenamos valores nulos o vacíos con '0' para evitar errores
    series = series.fillna('0').astype(str).str.strip()
    
    # Función para aplicar a cada valor
    def convert_value(val):
        val = val.lower().replace('$', '').replace('%', '').replace(',', '')
        if 'b' in val:
            return float(val.replace('b', '')) * 1_000_000_000
        elif 'm' in val:
            return float(val.replace('m', '')) * 1_000_000
        elif 'k' in val:
            return float(val.replace('k', '')) * 1_000
        try:
            return float(val)
        except (ValueError, TypeError):
            return 0 # Si falla la conversión, devuelve 0
            
    return series.apply(convert_value)

# --- Construcción de la Interfaz del Dashboard ---

st.title("📈 Dashboard de Pools de Liquidez")
st.markdown("Utiliza los filtros en la barra lateral para explorar los datos.")

# Cargar y procesar los datos
df_raw = load_data()

if df_raw.empty:
    st.warning("No se pudieron cargar los datos. Revisa la configuración de la API o la conexión.")
else:
    # Limpiar y convertir las columnas de TVL y APR a formato numérico
    df_processed = df_raw.copy()
    df_processed['tvl_numeric'] = clean_numeric_text(df_processed['tvlmensual'])
    df_processed['apr_numeric'] = clean_numeric_text(df_processed['aprmensual'])

    # --- Barra Lateral con Filtros ---
    st.sidebar.header("⚙️ Filtros")

    # Filtro desplegable para Blockchain
    blockchains_disponibles = sorted(df_processed['blockchain'].unique())
    blockchain_seleccionada = st.sidebar.multiselect(
        "Blockchain",
        options=blockchains_disponibles,
        default=["arbitrum"] # Valor por defecto
    )

    # Filtro desplegable para DEX
    # Las opciones se basan en la blockchain ya seleccionada
    if blockchain_seleccionada:
        df_filtrado_temp = df_processed[df_processed['blockchain'].isin(blockchain_seleccionada)]
        dex_disponibles = sorted(df_filtrado_temp['dex'].unique())
    else:
        dex_disponibles = sorted(df_processed['dex'].unique())
    
    dex_seleccionado = st.sidebar.multiselect(
        "DEX (Exchange)",
        options=dex_disponibles,
        default=[]
    )

    # Filtro desplegable para Pair
    if dex_seleccionado:
        df_filtrado_temp = df_filtrado_temp[df_filtrado_temp['dex'].isin(dex_seleccionado)]
        pares_disponibles = sorted(df_filtrado_temp['pair'].unique())
    elif blockchain_seleccionada:
         pares_disponibles = sorted(df_filtrado_temp['pair'].unique())
    else:
        pares_disponibles = sorted(df_processed['pair'].unique())
    
    pair_seleccionado = st.sidebar.multiselect(
        "Pair (Par de Tokens)",
        options=pares_disponibles,
        default=[]
    )

    # Slider para TVL Mensual
    tvl_min = 0
    tvl_max = int(df_processed['tvl_numeric'].max())
    tvl_seleccionado = st.sidebar.slider(
        "TVL Mensual (en $)",
        min_value=tvl_min,
        max_value=tvl_max,
        value=(1000000, tvl_max), # Valor por defecto: de 1 millón al máximo
        step=100000,
        format="$%d"
    )

    # Slider para APR Mensual
    apr_min = 0.0
    apr_max = float(df_processed['apr_numeric'].max())
    apr_seleccionado = st.sidebar.slider(
        "APR Mensual (en %)",
        min_value=apr_min,
        max_value=apr_max,
        value=(apr_min, apr_max), # Valor por defecto: todo el rango
        step=1.0,
        format="%.2f%%"
    )

    # --- Lógica de Filtrado de Datos ---
    df_filtrado = df_processed.copy()

    # Aplicar filtros secuencialmente
    if blockchain_seleccionada:
        df_filtrado = df_filtrado[df_filtrado['blockchain'].isin(blockchain_seleccionada)]
    if dex_seleccionado:
        df_filtrado = df_filtrado[df_filtrado['dex'].isin(dex_seleccionado)]
    if pair_seleccionado:
        df_filtrado = df_filtrado[df_filtrado['pair'].isin(pair_seleccionado)]

    # Aplicar filtros de los sliders
    df_filtrado = df_filtrado[
        (df_filtrado['tvl_numeric'] >= tvl_seleccionado[0]) & 
        (df_filtrado['tvl_numeric'] <= tvl_seleccionado[1])
    ]
    df_filtrado = df_filtrado[
        (df_filtrado['apr_numeric'] >= apr_seleccionado[0]) &
        (df_filtrado['apr_numeric'] <= apr_seleccionado[1])
    ]
    
    # --- Visualización de Resultados ---
    
    st.markdown("---")
    st.subheader(f"📊 {len(df_filtrado)} Resultados Encontrados")

    if df_filtrado.empty:
        st.info("No se encontraron resultados con los filtros aplicados. Intenta ampliar los rangos.")
    else:
        # Tabla con los datos filtrados
        st.markdown("### Tabla de Datos")
        st.dataframe(df_filtrado[[
            'pair', 'tier', 'aprmensual', 'tvlmensual', 'blockchain', 'dex'
        ]], use_container_width=True)

        # Gráficos de barras
        st.markdown("### Gráficos Comparativos")
        
        # Ordenar por TVL para una mejor visualización en el gráfico
        df_grafico = df_filtrado.sort_values(by='tvl_numeric', ascending=False).head(20) # Limitar a 20 para no saturar

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### TVL por Pair")
            st.bar_chart(df_grafico.rename(columns={'tvl_numeric': 'TVL'}), x='pair', y='TVL')
        
        with col2:
            st.markdown("#### APR por Pair")
            st.bar_chart(df_grafico.rename(columns={'apr_numeric': 'APR'}), x='pair', y='APR')
