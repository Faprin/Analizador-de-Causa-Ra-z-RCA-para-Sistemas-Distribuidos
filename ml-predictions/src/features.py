import pandas as pd
import re

# =========================
# FUNCIONES AUXILIARES
# =========================

def max_level(comb_level):
    level = str(comb_level).upper()
    if 'ERROR' in level:
        return 'ERROR'
    elif 'WARN' in level:
        return 'WARN'
    else:
        return 'INFO'

def etiquetado(fila):
    if '500' in str(fila['http_status']) or 'ERROR' in str(fila['level']):
        return -1
    else:
        return 1


def limpiar_texto(texto):
    if texto == "X" or pd.isna(texto):
        return ""
    
    texto = re.sub(r":\d+", "", texto)
    texto = re.sub(r"[^a-zA-Z\s]", " ", texto)
    return texto.lower().strip()

def get_duracion_relativa(df):
    return df[df["es_anomalia"] == 1].groupby("service")["duration_ms"].mean()

def marcar_cascada(df):
    # Primero aplica max_level para tener el level final de cada fila
    df['level_final'] = df['level'].apply(max_level)
    
    # traceIds que tienen ERROR en al menos dos servicios distintos
    errores_por_trace = (
        df[df['level_final'] == 'ERROR']
        .groupby('traceId')['service']
        .nunique()
    )
    traces_cascada = errores_por_trace[errores_por_trace > 1].index
    df['is_cascada'] = df['traceId'].isin(traces_cascada).astype(int)
    
    return df
    
# =========================
# FUNCIONES TRANSFORMADORAS
# =========================

def features_geneartor(df):
    # 2. ERROR 5XX
    df['tiene_error_5xx'] = df['http_status'].astype(str).str.contains(r'5\d{2}').astype(int)
    
    # 3. TIENE ANOMALIA
    df['es_anomalia'] = df.apply(etiquetado, axis=1)

    # 4. TEXTO COMPLETO
    # df['texto_completo'] = df['error_type'] + " " + df['error_message']

    # 5. DURACION RELATIVA
    baseline = get_duracion_relativa(df)

    df["duracion_relativa"] = df.apply(
    lambda row: row["duration_ms"] / baseline.get(row["service"], 1),
    axis=1
    )

    # 5. CASCADA
    df = marcar_cascada(df)

    return df


def logs_unifier(df):
    # Calculamos primero los logs cuyo traceid y service son iguales
    df['log_count'] = df.groupby(['traceId', 'service'])['traceId'].transform('count')

    # Asegurarnos de que el dataframe esté ordenado por tiempo
    df = df.sort_values(by=['@timestamp'])

    # PROPAGAR EL TRACEID: 
    # Agrupamos por tiempo exacto y servicio, y propagamos el traceId hacia atrás (bfill) y hacia adelante (ffill)
    # Así, la fila que tiene NaN adoptará el traceId '6a4bac01...' de su fila hermana.
    df['traceId'] = df.groupby(['@timestamp', 'service'])['traceId'].transform(lambda x: x.bfill().ffill())

    # Opcional pero recomendado: si queda algún log de sistema puro que no pertenece a ninguna 
    # petición (sigue teniendo traceId = NaN), lo filtramos para no meter ruido al modelo.
    df = df.dropna(subset=['traceId'])

    # EL DICCIONARIO DE AGREGACIÓN (El que ya teníamos)
    agregaciones = {
        '@timestamp': 'min',  
        'level': lambda x: ', '.join(x.dropna().astype(str).unique()),
        'event_type': lambda x: ', '.join(x.dropna().astype(str).unique()),
        'http_method': 'first',
        'http_status': lambda x: ', '.join(x.dropna().astype(str).unique()),
        'duration_ms': 'max', 
        'error_type': lambda x: ' | '.join(x.dropna().astype(str).unique()),
        'error_message': lambda x: ' | '.join(x.dropna().astype(str).unique()),
        'error_origin': lambda x: ' | '.join(x.dropna().astype(str).unique()),
        'log_count':'max'
    }

    # AGRUPACIÓN FINAL
    df_clear = df.groupby(['traceId', 'service']).agg(agregaciones).reset_index()

    # ARREGLAMOS EL PROBMELA DE LVEL MULTIPLE
    df_clear['level'] = df_clear['level'].apply(max_level)

    mediana = df_clear['duration_ms'].median()
    df_clear['duration_ms'] = df_clear['duration_ms'].fillna(mediana)

    # Rellena http_method y http_status vacíos
    df_clear['http_method'] = df_clear['http_method'].fillna('UNKNOWN')
    df_clear['http_status'] = df_clear['http_status'].fillna('0')

    return df_clear


def fill_na(df):
    df['error_message'] = df['error_message'].fillna('X')
    df['error_type'] = df['error_type'].fillna('X')
    df['error_origin']  = df['error_origin'].fillna('X')

    return df

def col_remover(df):
    df = df.drop(columns=["outcome", "http_uri", "error_type",
                          "error_message", "@timestamp", "service", 
                          "level_final"], errors='ignore')
    return df

def text_builder(df):
    df["texto_completo"] = (
        df["error_type"].apply(limpiar_texto) + " " +
        df["error_message"].apply(limpiar_texto) + " " +
        df["error_origin"].apply(limpiar_texto)
    )

    return df
# =========================
#   FUNCION PRINCIPAL
# =========================

def clean(df_raw):

    df = df_raw.copy()

    df = df.dropna(subset=["event_type", "duration_ms"], how="all")
    df = df[~df["http_uri"].str.contains("/chaos/", na=False)]
    df["duration_ms"] = pd.to_numeric(df["duration_ms"], errors="coerce")
    df["http_status"] = pd.to_numeric(df["http_status"], errors="coerce")

    df = fill_na(df)
    df = logs_unifier(df)
    df = text_builder(df)
    df = features_geneartor(df)
    df = col_remover(df)

    return df