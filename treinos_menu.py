import io
import os
from datetime import time
import pandas as pd
import streamlit as st

# =========================
# Config
# =========================
st.set_page_config(page_title="Controle de Corridas", layout="wide")
FILE_PATH = "Treinos Corrida.xlsx"

# Cabeçalhos exatamente como na planilha
COLS = ["Mês/Ano", "Data", "Semana", "Dia da Semana", "Distância (km)", "Tempo", "Pace (min/km)"]
MESES_PT = ["janeiro","fevereiro","março","abril","maio","junho","julho","agosto","setembro","outubro","novembro","dezembro"]
DIAS_PT   = ["Segunda","Terça","Quarta","Quinta","Sexta","Sábado","Domingo"]

# =========================
# Helpers
# =========================
def mes_ano_label(dt):
    m = MESES_PT[int(dt.month)-1].capitalize()
    return f"{m} {int(dt.year)}"

def dia_semana_nome(dt):
    return DIAS_PT[int(dt.weekday())]

def semana_iso_label(dt):
    iso = dt.isocalendar()
    return f"{int(iso.year)}-W{int(iso.week):02d}"

def to_timedelta(val):
    if pd.isna(val) or val == "":
        return pd.to_timedelta(0, unit="s")
    if isinstance(val, time):
        return pd.to_timedelta(f"{val.hour}:{val.minute}:{val.second}")
    try:
        return pd.to_timedelta(val)
    except Exception:
        try:
            return pd.to_timedelta(str(val))
        except Exception:
            return pd.to_timedelta(0, unit="s")

def timedelta_to_hms(td):
    # sempre em HH:MM:SS (soma dias em horas)
    secs = int(td.total_seconds())
    return f"{secs//3600:02d}:{(secs%3600)//60:02d}:{secs%60:02d}"

def pace_str(tempo_td, dist):
    dist = float(dist or 0)
    if dist <= 0:
        return ""
    secs = int(tempo_td.total_seconds() / dist)
    return f"{secs//60:02d}:{secs%60:02d}"

def normalize_and_fill(df: pd.DataFrame) -> pd.DataFrame:
    # Garante todas as colunas
    for c in COLS:
        if c not in df.columns:
            df[c] = None

    # Data
    if not pd.api.types.is_datetime64_any_dtype(df["Data"]):
        df["Data"] = pd.to_datetime(df["Data"], errors="coerce")

    # Distância
    df["Distância (km)"] = pd.to_numeric(df["Distância (km)"], errors="coerce")

    # Tempo e Pace
    tempo_td = df["Tempo"].apply(to_timedelta)
    df["Tempo"] = tempo_td.apply(timedelta_to_hms)
    pace_td = df["Pace (min/km)"].apply(to_timedelta)
    df["Pace (min/km)"] = pace_td.apply(lambda t: "" if t.total_seconds()==0 else f"{int((t.total_seconds()//60)%60):02d}:{int(t.total_seconds()%60):02d}")

    # Derivados da Data
    mask = df["Data"].notna()
    df.loc[mask, "Mês/Ano"]       = df.loc[mask, "Data"].apply(mes_ano_label)
    df.loc[mask, "Dia da Semana"] = df.loc[mask, "Data"].apply(dia_semana_nome)
    df.loc[mask, "Semana"]        = df.loc[mask, "Data"].apply(semana_iso_label)

    return df[COLS].sort_values("Data").reset_index(drop=True)

def load_planilha(f) -> pd.DataFrame:
    df = pd.read_excel(f, sheet_name="treinos")
    return normalize_and_fill(df)

def save_excel_bytes(df):
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="treinos", index=False)

        aux = df.copy()
        aux["tempo_td"] = aux["Tempo"].apply(to_timedelta)

        # Resumo por Mês/Ano
        rm = (
            aux.groupby("Mês/Ano", as_index=False)
               .agg(treinos=("Data","count"),
                    distancia_km=("Distância (km)","sum"),
                    tempo=("tempo_td","sum"))
               .sort_values("Mês/Ano")
        )
        rm["ritmo_medio"] = rm.apply(lambda r: pace_str(r["tempo"], r["distancia_km"]), axis=1)
        rm["tempo"] = rm["tempo"].apply(timedelta_to_hms)
        rm.to_excel(writer, sheet_name="resumo_mes", index=False)

        # Resumo por Semana
        rs = (
            aux.groupby("Semana", as_index=False)
               .agg(treinos=("Data","count"),
                    distancia_km=("Distância (km)","sum"),
                    tempo=("tempo_td","sum"))
               .sort_values("Semana")
        )
        rs["ritmo_medio"] = rs.apply(lambda r: pace_str(r["tempo"], r["distancia_km"]), axis=1)
        rs["tempo"] = rs["tempo"].apply(timedelta_to_hms)
        rs.to_excel(writer, sheet_name="resumo_semana", index=False)
    return out.getvalue()

# =========================
# Estado
# =========================
if "df" not in st.session_state:
    st.session_state.df = pd.DataFrame(columns=COLS)

# =========================
# Sidebar (Menu)
# =========================
st.sidebar.title("🏃 Controle de Corridas")
menu = st.sidebar.radio(
    "Navegação",
    options=[
        "➕ Adicionar treino",
        "✏️ Editar treino",
        "📋 Listagem completa",
        "📊 Resumos",
    ],
    index=0,
)

st.sidebar.markdown("---")
st.sidebar.header("📂 Planilha oficial")
if os.path.exists(FILE_PATH):
    try:
        st.session_state.df = load_planilha(FILE_PATH)
        st.sidebar.success("Carregada automaticamente")
    except Exception as e:
        st.sidebar.error(str(e))
else:
    up = st.sidebar.file_uploader("Carregar Treinos Corrida.xlsx", type=["xlsx"])
    if up:
        try:
            st.session_state.df = load_planilha(up)
            st.sidebar.success("Planilha carregada via upload.")
        except Exception as e:
            st.sidebar.error(str(e))

if not st.session_state.df.empty:
    st.sidebar.download_button(
        "⬇️ Baixar Excel atualizado",
        data=save_excel_bytes(st.session_state.df),
        file_name="Treinos Corrida - atualizado.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

df = st.session_state.df

# =========================
# Views
# =========================
if menu.startswith("➕"):
    st.header("🏃‍♂️ Adicionar treino")
    with st.form("add", clear_on_submit=True):
        c1,c2 = st.columns(2)
        data = c1.date_input("Data")
        dist = c2.number_input("Distância (km)", min_value=0.0, step=0.01, format="%.2f")
        t1,t2,t3 = st.columns(3)
        hh = t1.number_input("Horas",   min_value=0, max_value=23, step=1, value=0)
        mm = t2.number_input("Minutos", min_value=0, max_value=59, step=1, value=0)
        ss = t3.number_input("Segundos",min_value=0, max_value=59, step=1, value=0)
        ok = st.form_submit_button("➕ Adicionar")
        if ok:
            tempo_td = pd.to_timedelta(f"{int(hh):02d}:{int(mm):02d}:{int(ss):02d}")
            new = {
                "Mês/Ano": mes_ano_label(pd.to_datetime(data)),
                "Data": pd.to_datetime(data),
                "Semana": semana_iso_label(pd.to_datetime(data)),
                "Dia da Semana": dia_semana_nome(pd.to_datetime(data)),
                "Distância (km)": dist,
                "Tempo": timedelta_to_hms(tempo_td),
                "Pace (min/km)": pace_str(tempo_td, dist),
            }
            st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new])], ignore_index=True)
            st.session_state.df = normalize_and_fill(st.session_state.df)
            st.success("Treino adicionado! ✅")

elif menu.startswith("✏️"):
    st.header("✏️ Editar treino")
    if df.empty:
        st.info("Carregue a planilha na barra lateral.")
    else:
        dfv = df.copy()
        dfv["idx"] = dfv.index
        dfv["rotulo"] = dfv["Data"].dt.strftime("%Y-%m-%d") + " | " + dfv["Distância (km)"].fillna(0).map(lambda x: f"{x:.2f} km")
        idx = st.selectbox("Selecione", options=dfv["idx"], format_func=lambda i: dfv.loc[i,"rotulo"])
        row = df.loc[idx]

        c1,c2 = st.columns(2)
        data = c1.date_input("Data", value=row["Data"].date() if pd.notna(row["Data"]) else pd.Timestamp.today().date())
        dist = c2.number_input("Distância (km)", min_value=0.0, step=0.01, value=float(row["Distância (km)"] or 0))
        t1,t2,t3 = st.columns(3)
        td = to_timedelta(row["Tempo"])
        hh0 = int(td.total_seconds()//3600); mm0 = int((td.total_seconds()%3600)//60); ss0 = int(td.total_seconds()%60)
        hh = t1.number_input("Horas",   min_value=0, max_value=23, step=1, value=hh0)
        mm = t2.number_input("Minutos", min_value=0, max_value=59, step=1, value=mm0)
        ss = t3.number_input("Segundos",min_value=0, max_value=59, step=1, value=ss0)

        col1,col2 = st.columns(2)
        if col1.button("💾 Guardar alterações", use_container_width=True):
            tempo = pd.to_timedelta(f"{int(hh):02d}:{int(mm):02d}:{int(ss):02d}")
            st.session_state.df.at[idx,"Data"]            = pd.to_datetime(data)
            st.session_state.df.at[idx,"Mês/Ano"]         = mes_ano_label(pd.to_datetime(data))
            st.session_state.df.at[idx,"Semana"]          = semana_iso_label(pd.to_datetime(data))
            st.session_state.df.at[idx,"Dia da Semana"]   = dia_semana_nome(pd.to_datetime(data))
            st.session_state.df.at[idx,"Distância (km)"]  = dist
            st.session_state.df.at[idx,"Tempo"]           = timedelta_to_hms(tempo)
            st.session_state.df.at[idx,"Pace (min/km)"]   = pace_str(tempo, dist)
            st.success("Registo atualizado. ✅")
        if col2.button("🗑️ Apagar treino", use_container_width=True):
            st.session_state.df = df.drop(index=idx).reset_index(drop=True)
            st.success("Registo apagado. 🗑️")

elif menu.startswith("📋"):
    st.header("📋 Listagem completa")
    if df.empty:
        st.info("Carregue a planilha.")
    else:
        st.dataframe(df.sort_values("Data", ascending=False), use_container_width=True)

else:  # 📊 Resumos
    st.header("📊 Resumos")
    st.caption("Selecione abaixo o tipo de resumo que deseja visualizar.")

    # 🔽 seletor no topo (como no seu exemplo)
    tipo = st.selectbox(
        "Escolha o tipo de resumo",
        ["Mês/ano", "Semana", "Total geral"],
        index=0,
    )

    if df.empty:
        st.info("Carregue a planilha.")
    else:
        aux = df.copy()
        aux["tempo_td"] = aux["Tempo"].apply(to_timedelta)

        if tipo == "Mês/ano":
            g = (
                aux.groupby("Mês/Ano", as_index=False)
                   .agg(Treinos=("Data","count"),
                        **{"Distância (km)": ("Distância (km)","sum")},
                        Tempo=("tempo_td","sum"))
                   .sort_values("Mês/Ano")
            )
            if not g.empty:
                g["Ritmo médio"] = g.apply(lambda r: pace_str(r["Tempo"], r["Distância (km)"]), axis=1)
                g["Tempo"] = g["Tempo"].apply(timedelta_to_hms)
                st.dataframe(g, use_container_width=True)
            else:
                st.info("Sem dados para agrupar por mês/ano.")

        elif tipo == "Semana":
            g = (
                aux.groupby("Semana", as_index=False)
                   .agg(Treinos=("Data","count"),
                        **{"Distância (km)": ("Distância (km)","sum")},
                        Tempo=("tempo_td","sum"))
                   .sort_values("Semana")
            )
            if not g.empty:
                g["Ritmo médio"] = g.apply(lambda r: pace_str(r["Tempo"], r["Distância (km)"]), axis=1)
                g["Tempo"] = g["Tempo"].apply(timedelta_to_hms)
                st.dataframe(g, use_container_width=True)
            else:
                st.info("Sem dados para agrupar por semana.")

        else:  # Total geral
            total_km = aux["Distância (km)"].sum()
            total_t  = aux["tempo_td"].sum()
            c1,c2,c3 = st.columns(3)
            c1.metric("Total (km)", f"{total_km:.2f}")
            c2.metric("Tempo total", timedelta_to_hms(total_t))  # <-- SEM 'days', sempre HH:MM:SS
            ritmo = pace_str(total_t, total_km) if total_km>0 else "00:00"
            c3.metric("Ritmo médio", ritmo)
            st.dataframe(df.sort_values("Data"), use_container_width=True)
