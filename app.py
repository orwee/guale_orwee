import streamlit as st
import pandas as pd
import requests
import re
import numpy as np
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# --- Configuración de la página ---
st.set_page_config(layout="wide", page_title="Dashboard de Pools y Análisis")

# --- Cargar credenciales de forma segura desde secrets.toml ---
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    ARBISCAN_KEY = st.secrets["ARBISCAN_KEY"] # <-- AÑADIDO: Clave para la API de Arbiscan
except FileNotFoundError:
    st.error("Archivo 'secrets.toml' no encontrado. Por favor, créalo en la carpeta '.streamlit/' con tus credenciales.")
    st.stop()
except KeyError as e:
    st.error(f"Asegúrate de que la clave '{e.args[0]}' está definida en tu archivo 'secrets.toml'.")
    st.stop()

# --- Creación de Pestañas ---
tab1, tab2 = st.tabs(["📈 Dashboard de Pools", "🧾 Análisis de Wallet (Tax)"])

# ==============================================================================
# PESTAÑA 1: DASHBOARD DE POOLS (Tu código original)
# ==============================================================================
with tab1:
    # Headers para la petición a la API de Supabase
    headers_supabase = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }

    # --- Funciones de Carga y Procesamiento de Datos ---
    @st.cache_data
    def load_data():
        """Carga los datos desde la API de Supabase."""
        select_columns = "blockchain,dex,pair,tier,aprmensual,tvlmensual,memes,filtro_3,correlacion,aprmonthchart,tvlmonthchart,datemonthchart"
        params = {"select": select_columns, "memes": "eq.0", "filtro_3": "in.(1,2,3)"}
        try:
            response = requests.get(SUPABASE_URL, headers=headers_supabase, params=params)
            response.raise_for_status()
            df = pd.DataFrame(response.json())
            return df
        except requests.exceptions.RequestException as e:
            st.error(f"Error al conectar con la base de datos: {e}")
            return pd.DataFrame()

    def clean_numeric_text(series):
        """Convierte una columna de texto a valores numéricos."""
        series = series.fillna('0').astype(str).str.strip()
        def convert_value(val):
            val = val.lower().replace('$', '').replace('%', '').replace(',', '')
            if 'b' in val: return float(val.replace('b', '')) * 1_000_000_000
            elif 'm' in val: return float(val.replace('m', '')) * 1_000_000
            elif 'k' in val: return float(val.replace('k', '')) * 1_000
            try: return float(val)
            except (ValueError, TypeError): return 0
        return series.apply(convert_value)

    # --- Construcción de la Interfaz del Dashboard ---
    st.title("📈 Dashboard de Pools de Liquidez")
    st.markdown("Utiliza los filtros en la barra lateral para explorar los datos.")

    df_raw = load_data()

    if df_raw.empty:
        st.warning("No se pudieron cargar los datos o no hay resultados.")
    else:
        df_processed = df_raw.copy()
        df_processed['tvl_numeric'] = clean_numeric_text(df_processed['tvlmensual'])
        df_processed['apr_numeric'] = clean_numeric_text(df_processed['aprmensual'])

        # --- Barra Lateral con Filtros ---
        st.sidebar.header("⚙️ Filtros del Dashboard")
        blockchains_disponibles = sorted(df_processed['blockchain'].unique())
        blockchain_seleccionada = st.sidebar.multiselect("Blockchain", options=blockchains_disponibles, default=["arbitrum"])

        df_filtrado_temp = df_processed
        if blockchain_seleccionada:
            df_filtrado_temp = df_processed[df_processed['blockchain'].isin(blockchain_seleccionada)]
        
        dex_disponibles = sorted(df_filtrado_temp['dex'].unique())
        dex_seleccionado = st.sidebar.multiselect("DEX (Exchange)", options=dex_disponibles, default=[])

        if dex_seleccionado:
            df_filtrado_temp = df_filtrado_temp[df_filtrado_temp['dex'].isin(dex_seleccionado)]
        
        pares_disponibles = sorted(df_filtrado_temp['pair'].unique())
        pair_seleccionado = st.sidebar.multiselect("Pair (Par de Tokens)", options=pares_disponibles, default=[])

        tvl_min, tvl_max = 0, int(df_processed['tvl_numeric'].max())
        tvl_seleccionado = st.sidebar.slider("TVL Mensual ($)", min_value=tvl_min, max_value=tvl_max, value=(1000000, tvl_max), step=100000, format="$%d")
        
        apr_min, apr_max = 0.0, float(df_processed['apr_numeric'].max())
        apr_seleccionado = st.sidebar.slider("APR Mensual (%)", min_value=apr_min, max_value=apr_max, value=(apr_min, apr_max), step=1.0, format="%.2f%%")

        # --- Lógica de Filtrado ---
        df_filtrado = df_processed.copy()
        if blockchain_seleccionada: df_filtrado = df_filtrado[df_filtrado['blockchain'].isin(blockchain_seleccionada)]
        if dex_seleccionado: df_filtrado = df_filtrado[df_filtrado['dex'].isin(dex_seleccionado)]
        if pair_seleccionado: df_filtrado = df_filtrado[df_filtrado['pair'].isin(pair_seleccionado)]
        df_filtrado = df_filtrado[df_filtrado['tvl_numeric'].between(*tvl_seleccionado)]
        df_filtrado = df_filtrado[df_filtrado['apr_numeric'].between(*apr_seleccionado)]
        
        # --- Visualización de Resultados ---
        st.markdown("---")
        st.subheader(f"📊 {len(df_filtrado)} Resultados Encontrados")

        if df_filtrado.empty:
            st.info("No se encontraron resultados con los filtros aplicados.")
        else:
            df_ordenado = df_filtrado.sort_values(by='apr_numeric', ascending=False).reset_index(drop=True)
            
            st.markdown("### Tabla de Datos (ordenada por APR Mensual)")
            columnas_deseadas = ['pair', 'tier', 'correlacion', 'aprmensual', 'tvlmensual', 'blockchain', 'dex']
            
            datos_pair_seleccionado = None
            header_cols = st.columns((3, 1, 1, 1, 1, 1, 1, 2))
            labels = columnas_deseadas + ["Acción"]
            for col, name in zip(header_cols, labels):
                col.markdown(f"**{name.capitalize()}**")

            for index, row in df_ordenado.iterrows():
                row_cols = st.columns((3, 1, 1, 1, 1, 1, 1, 2))
                for i, col_name in enumerate(columnas_deseadas):
                    row_cols[i].write(row[col_name])
                if row_cols[-1].button("Ver Historial", key=f"historial_{index}"):
                    datos_pair_seleccionado = row
            
            st.markdown("### Gráficos Comparativos (Top 20 por TVL)")
            df_grafico = df_filtrado.sort_values(by='tvl_numeric', ascending=False).head(20)
            col1, col2 = st.columns(2)
            with col1:
                st.bar_chart(df_grafico.rename(columns={'tvl_numeric': 'TVL'}), x='pair', y='TVL', use_container_width=True)
            with col2:
                st.bar_chart(df_grafico.rename(columns={'apr_numeric': 'APR'}), x='pair', y='APR', use_container_width=True)

            st.markdown("---")
            st.subheader("Análisis Histórico Mensual")

            if datos_pair_seleccionado is not None:
                pair_para_grafico = datos_pair_seleccionado['pair']
                st.markdown(f"Mostrando historial para: **{pair_para_grafico}**")
                
                dates, tvls, aprs = datos_pair_seleccionado['datemonthchart'], datos_pair_seleccionado['tvlmonthchart'], datos_pair_seleccionado['aprmonthchart']
                if dates and tvls and aprs and len(dates) > 0:
                    df_chart = pd.DataFrame({'Fecha': pd.to_datetime(dates), 'TVL': tvls, 'APR': aprs}).set_index('Fecha')
                    media_tvl, media_apr = df_chart['TVL'].mean(), df_chart['APR'].mean()
                    df_chart[f'TVL Medio ({media_tvl:,.0f})'] = media_tvl
                    df_chart[f'APR Medio ({media_apr:.2f}%)'] = media_apr
                    
                    st.markdown(f"#### Historial de TVL")
                    st.line_chart(df_chart[['TVL', f'TVL Medio ({media_tvl:,.0f})']])
                    st.markdown(f"#### Historial de APR")
                    st.line_chart(df_chart[['APR', f'APR Medio ({media_apr:.2f}%)']])
                else:
                    st.warning(f"No hay datos históricos disponibles para '{pair_para_grafico}'.")
            else:
                st.info("Presiona 'Ver Historial' en cualquier fila para ver el detalle.")

# ==============================================================================
# PESTAÑA 2: ANÁLISIS DE WALLET (Tu nuevo código)
# ==============================================================================
with tab2:
    st.header("🧾 Análisis de Transacciones de Wallet")
    st.markdown("Introduce una dirección de wallet de Arbitrum para obtener un resumen de sus transacciones y eventos.")

    # --- Funciones para la pestaña de Tax ---
    def fetch_txs(address, apikey, chainid=42161, page=1, offset=10000, sort="asc"):
        # URL actualizada para Arbiscan
        url = (
            f"https://api.arbiscan.io/api?module=account&action=tokentx"
            f"&address={address}&page={page}&offset={offset}&sort={sort}&apikey={apikey}"
        )
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            if not isinstance(data, dict) or "result" not in data:
                raise ValueError(f"Respuesta inesperada de la API: {data.get('message', 'Sin mensaje')}")
            return data["result"]
        except requests.exceptions.RequestException as e:
            st.error(f"Error de conexión con la API de Arbiscan: {e}")
            return None

    def summarize_tx(tx, queried_address):
        q, frm, to = queried_address.lower(), (tx.get("from") or "").lower(), (tx.get("to") or "").lower()
        
        if frm == q and to != q: direction = "OUT"
        elif to == q and frm != q: direction = "IN"
        elif frm == q and to == q: direction = "SELF"
        else: direction = "OTHER"

        raw_value = int(tx.get("value", "0") or 0)
        decimals = int(tx.get("tokenDecimal") or 0)
        adjusted_value = raw_value / (10 ** decimals) if decimals else raw_value
        ts = int(tx.get("timeStamp", 0) or 0)
        utc_dt = datetime.fromtimestamp(ts, tz=timezone.utc) if ts else None
        
        gas_used, gas_price = int(tx.get("gasUsed", 0) or 0), int(tx.get("gasPrice", 0) or 0)
        gas_cost_wei = gas_used * gas_price
        gas_cost_eth = gas_cost_wei / 10**18  # ETH es el token nativo en Arbitrum

        return {
            "hash": tx.get("hash"), "block": int(tx.get("blockNumber") or 0),
            "datetime_utc": utc_dt.isoformat() if utc_dt else "",
            "from": frm, "to": to, "direction": direction,
            "token_symbol": tx.get("tokenSymbol") or "", "contract": (tx.get("contractAddress") or "").lower(),
            "adjusted_value": adjusted_value, "gas_cost_eth": gas_cost_eth,
            "function": tx.get("functionName") or tx.get("methodId") or ""
        }

    def determine_event(row, hash_counts):
        func, direction, token, hash_val = (row.get("function") or "").lower(), row.get("direction") or "", (row.get("token_symbol") or "").upper(), row.get("hash")
        if pd.notna(row.get("event")) and row.get("event") != '': return row.get("event")
        if direction == "OUT" and token == "USDC" and hash_counts.get(str(hash_val), 0) == 1: return "USD_TRANSFER_OUT"
        if direction == "IN" and token == "USDC" and hash_counts.get(str(hash_val), 0) == 1: return "USD_TRANSFER_IN"
        if func.startswith("transfer") and direction == "IN": return "USD_TRANSFER_IN"
        return None

    @st.cache_data # Cache para evitar re-cálculos con la misma wallet
    def process_wallet_data(address, apikey):
        txs = fetch_txs(address, apikey)
        if txs is None: return pd.DataFrame() # Retorna DF vacío si hay error
        
        summaries = [summarize_tx(tx, address) for tx in txs]
        df = pd.DataFrame(summaries)
        if df.empty: return df

        # --- Lógica de procesamiento ---
        hash_counts = df['hash'].fillna('').astype(str).value_counts().to_dict()
        df["event"] = df.apply(lambda r: determine_event(r, hash_counts), axis=1)
        df = df[["hash", "direction", "token_symbol", "adjusted_value", "contract", "datetime_utc", "event"]]
        df = df[~df["token_symbol"].str.contains("claim", case=False, na=False)]
        df['datetime_utc'] = pd.to_datetime(df['datetime_utc'], utc=True, errors='coerce')
        df = df.sort_values('datetime_utc').reset_index(drop=True)
        df['adjusted_value'] = pd.to_numeric(df['adjusted_value'], errors='coerce')

        run_id = (df['hash'] != df['hash'].shift(1)).cumsum()
        run_hash = df.groupby(run_id)['hash'].first()
        df['prev_diff_hash'] = run_id.map(run_hash.shift(1))
        df['next_diff_hash'] = run_id.map(run_hash.shift(-1))

        event_empty = df['event'].isna() | (df['event'].astype(str).str.strip() == '')
        hash_has_any_nonempty_event = (~event_empty).groupby(df['hash']).any()
        eligible_hashes = hash_has_any_nonempty_event[~hash_has_any_nonempty_event].index
        
        mask_usdc_out = df['token_symbol'].str.upper().eq('USDC') & df['direction'].str.upper().eq('OUT')
        mask_usdc_in = df['token_symbol'].str.upper().eq('USDC') & df['direction'].str.upper().eq('IN')

        sum_by_hash_usdc_out = df.loc[mask_usdc_out & df['hash'].isin(eligible_hashes)].groupby('hash')['adjusted_value'].sum()
        sum_by_hash_usdc_in = df.loc[mask_usdc_in & df['hash'].isin(eligible_hashes)].groupby('hash')['adjusted_value'].sum()
        
        sum_current_out = df['hash'].map(sum_by_hash_usdc_out).fillna(0.0)
        sum_prevdiff_out = df['prev_diff_hash'].map(sum_by_hash_usdc_out).fillna(0.0)
        sum_current_in = df['hash'].map(sum_by_hash_usdc_in).fillna(0.0)
        sum_nextdiff_in = df['next_diff_hash'].map(sum_by_hash_usdc_in).fillna(0.0)

        mask_guale_in = df['token_symbol'].str.contains(r'^GUALE', case=False, na=False) & df['direction'].eq('IN')
        mask_guale_out = df['token_symbol'].str.contains(r'^GUALE', case=False, na=False) & df['direction'].eq('OUT')

        df['value'] = np.nan
        df.loc[mask_guale_in, 'value'] = sum_current_out + sum_prevdiff_out
        df.loc[mask_guale_out, 'value'] = sum_current_in + sum_nextdiff_in
        df.loc[df['event'].str.startswith("USD_TRANSFER", na=False), 'value'] = df['adjusted_value']

        mask_guale = df['token_symbol'].str.upper().str.startswith('GUALE', na=False)
        df.loc[mask_guale, 'token_symbol'] = df.loc[mask_guale, 'token_symbol'].str.replace(r'(?i)^GUALE-CLM', '', regex=True).str.strip()
        
        direction_up = df['direction'].str.upper()
        prefix_series = pd.Series(np.where(direction_up == 'IN', 'INCREASE LIQUIDITY ', np.where(direction_up == 'OUT', 'DECREASE LIQUIDITY ', '')), index=df.index)
        df.loc[mask_guale, 'event'] = prefix_series[mask_guale] + df.loc[mask_guale, 'token_symbol']

        df_final = df[pd.to_numeric(df['value'], errors='coerce').notna()].copy()
        df_final.drop(columns=['prev_diff_hash', 'next_diff_hash'], inplace=True)
        return df_final

    # --- Interfaz de la Pestaña de Tax ---
    wallet_address = st.text_input(
        "Dirección de la Wallet",
        "0x0447dF6dBe7D260eCDC31cb97A6266d209d13960", # Dirección de ejemplo
        help="Pega aquí la dirección de la wallet de Arbitrum que quieres analizar."
    )

    if st.button("🔍 Analizar Wallet"):
        if not re.match(r"^0x[a-fA-F0-9]{40}$", wallet_address):
            st.error("Por favor, introduce una dirección de wallet Ethereum válida (0x...).")
        else:
            with st.spinner("Consultando API de Arbiscan y procesando transacciones... Esto puede tardar un momento."):
                final_df = process_wallet_data(wallet_address, ARBISCAN_KEY)
                # Guardar en el estado de la sesión para persistencia
                st.session_state['tax_results'] = final_df

    # Mostrar la tabla si existen resultados en el estado de la sesión
    if 'tax_results' in st.session_state:
        results = st.session_state['tax_results']
        st.markdown("---")
        st.subheader(f"✅ Análisis completado. Se encontraron {len(results)} eventos relevantes.")
        
        if not results.empty:
            # Formatear columnas para mejor visualización
            display_df = results.copy()
            display_df['adjusted_value'] = display_df['adjusted_value'].map('{:,.4f}'.format)
            display_df['value'] = display.df['value'].map('{:,.2f}'.format)
            st.dataframe(
                display_df[['datetime_utc', 'event', 'value', 'token_symbol', 'direction', 'hash']],
                use_container_width=True
            )
        else:
            st.warning("No se encontraron transacciones o eventos relevantes para la wallet especificada con la lógica actual.")
