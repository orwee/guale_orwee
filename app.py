import streamlit as st
import pandas as pd
import requests
import re

# --- Configuración de la página ---
st.set_page_config(layout="wide", page_title="Dashboard de Pools")

# --- CAMBIO 1: Cargar credenciales de forma segura desde secrets.toml ---
# Ya no se escriben las claves directamente en el código.
# Streamlit las toma del archivo .streamlit/secrets.toml
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
except FileNotFoundError:
    st.error("Archivo 'secrets.toml' no encontrado. Por favor, créalo en la carpeta '.streamlit/' con tus credenciales.")
    st.stop()
except KeyError:
    st.error("Asegúrate de que 'SUPABASE_URL' y 'SUPABASE_KEY' están definidos en tu archivo 'secrets.toml'.")
    st.stop()


# Headers para la petición a la API
headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}"
}

# --- Funciones de Carga y Procesamiento de Datos ---

@st.cache_data
def load_data():
    """Carga los datos desde la API de Supabase y los filtra por memes=0."""
    select_columns = "blockchain,dex,pair,tier,aprmensual,tvlmensual,memes"
    params = {
        "select": select_columns,
        "memes": "eq.0"
    }
    
    try:
        response = requests.get(SUPABASE_URL, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        df = pd.DataFrame(data)
        return df
    except requests.exceptions.RequestException as e:
        st.error(f"Error al conectar con la base de datos: {e}")
        return pd.DataFrame()

def clean_numeric_text(series):
    """Convierte una columna de texto (ej. '$1.5M', '50.2K%') a valores numéricos."""
    series = series.fillna('0').astype(str).str.strip()
    
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
            return 0
            
    return series.apply(convert_value)

# --- Construcción de la Interfaz del Dashboard ---

st.title("📈 Dashboard de Pools de Liquidez")
st.markdown("Utiliza los filtros en la barra lateral para explorar los datos.")

df_raw = load_data()

if df_raw.empty:
    st.warning("No se pudieron cargar los datos. Revisa la configuración de la API o la conexión.")
else:
    df_processed = df_raw.copy()
    df_processed['tvl_numeric'] = clean_numeric_text(df_processed['tvlmensual'])
    df_processed['apr_numeric'] = clean_numeric_text(df_processed['aprmensual'])

    # --- Barra Lateral con Filtros ---
    st.sidebar.header("⚙️ Filtros")

    blockchains_disponibles = sorted(df_processed['blockchain'].unique())
    blockchain_seleccionada = st.sidebar.multiselect(
        "Blockchain",
        options=blockchains_disponibles,
        default=["arbitrum"]
    )

    if blockchain_seleccionada:
        df_filtrado_temp = df_processed[df_processed['blockchain'].isin(blockchain_seleccionada)]
        dex_disponibles = sorted(df_filtrado_temp['dex'].unique())
    else:
        dex_disponibles = sorted(df_processed['dex'].unique())
    
    dex_seleccionado = st.sidebar.multiselect("DEX (Exchange)", options=dex_disponibles, default=[])

    if dex_seleccionado:
        df_filtrado_temp = df_filtrado_temp[df_filtrado_temp['dex'].isin(dex_seleccionado)]
        pares_disponibles = sorted(df_filtrado_temp['pair'].unique())
    elif blockchain_seleccionada:
         pares_disponibles = sorted(df_filtrado_temp['pair'].unique())
    else:
        pares_disponibles = sorted(df_processed['pair'].unique())
    
    pair_seleccionado = st.sidebar.multiselect("Pair (Par de Tokens)", options=pares_disponibles, default=[])

    tvl_min = 0
    tvl_max = int(df_processed['tvl_numeric'].max()) if not df_processed.empty else 0
    tvl_seleccionado = st.sidebar.slider(
        "TVL Mensual (en $)",
        min_value=tvl_min,
        max_value=tvl_max,
        value=(1000000, tvl_max),
        step=100000,
        format="$%d"
    )
    
    apr_min = 0.0
    apr_max = float(df_processed['apr_numeric'].max()) if not df_processed.empty else 0.0
    apr_seleccionado = st.sidebar.slider(
        "APR Mensual (en %)",
        min_value=apr_min,
        max_value=apr_max,
        value=(apr_min, apr_max),
        step=1.0,
        format="%.2f%%"
    )

    # --- Lógica de Filtrado de Datos ---
    df_filtrado = df_processed.copy()

    if blockchain_seleccionada:
        df_filtrado = df_filtrado[df_filtrado['blockchain'].isin(blockchain_seleccionada)]
    if dex_seleccionado:
        df_filtrado = df_filtrado[df_filtrado['dex'].isin(dex_seleccionado)]
    if pair_seleccionado:
        df_filtrado = df_filtrado[df_filtrado['pair'].isin(pair_seleccionado)]

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
        # --- CAMBIO 2: Ordenar la tabla por el APR numérico de forma descendente ---
        df_ordenado = df_filtrado.sort_values(by='apr_numeric', ascending=False)
        
        st.markdown("### Tabla de Datos (ordenada por APR Mensual)")
        st.dataframe(df_ordenado[[
            'pair', 'tier', 'aprmensual', 'tvlmensual', 'blockchain', 'dex'
        ]], use_container_width=True)

        st.markdown("### Gráficos Comparativos")
        
        # Para los gráficos, usamos el dataframe ordenado por TVL para mejor visualización
        df_grafico = df_filtrado.sort_values(by='tvl_numeric', ascending=False).head(20)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### Top 20 TVL por Pair")
            st.bar_chart(df_grafico.rename(columns={'tvl_numeric': 'TVL'}), x='pair', y='TVL')
        with col2:
            st.markdown("#### APR de los Top 20 por TVL")
            st.bar_chart(df_grafico.rename(columns={'apr_numeric': 'APR'}), x='pair', y='APR')
