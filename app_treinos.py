
import io
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Treinos de Corrida", layout="wide")

# -----------------------------
# Helpers
# -----------------------------

WEEKDAY_PT = {
    0: "Segunda",
    1: "Terça",
    2: "Quarta",
    3: "Quinta",
    4: "Sexta",
    5: "Sábado",
    6: "Domingo",
}

def to_timedelta_safe(x):
    if pd.isna(x) or x == "":
        return pd.to_timedelta(0, unit="s")
    try:
        return pd.to_timedelta(x)
    except Exception:
        try:
            return pd.to_timedelta(str(x))
        except Exception:
            return pd.to_timedelta(0, unit="s")

def normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    rename_map = {
        "data": "data",
        "Data": "data",
        "mes": "mes",
        "Mês": "mes",
        "dia_semana": "dia_semana",
        "Dia da Semana": "dia_semana",
        "dist_km": "dist_km",
        "Distância": "dist_km",
        "tempo_hms": "tempo_hms",
        "Tempo": "tempo_hms",
        "ritmo_min_km": "ritmo_min_km",
        "Pace": "ritmo_min_km",
        "tipo": "tipo",
        "observacoes": "observacoes",
        "Observacoes": "observacoes",
        "semana_iso": "semana_iso",
        "ano": "ano",
        "ano_semana": "ano_semana",
    }
    df = df.rename(columns=rename_map)

    for col in ["data","dist_km","tempo_hms"]:
        if col not in df.columns:
            df[col] = None

    if not pd.api.types.is_datetime64_any_dtype(df["data"]):
        df["data"] = pd.to_datetime(df["data"], errors="coerce")

    df["mes"] = df["data"].dt.to_period("M").astype(str)
    df["semana_iso"] = df["data"].dt.isocalendar().week.astype("Int64")
    df["ano"] = df["data"].dt.year.astype("Int64")
    df["ano_semana"] = df["ano"].astype(str) + "-W" + df["semana_iso"].astype(str).str.zfill(2)
    df["dia_semana"] = df["data"].dt.weekday.map(WEEKDAY_PT)

    df["dist_km"] = pd.to_numeric(df["dist_km"], errors="coerce")

    td = df["tempo_hms"].apply(to_timedelta_safe)
    df["tempo_hms"] = td.dt.components.apply(
        lambda r: f"{int(r['hours'] + 24*(r['days'])):02d}:{int(r['minutes']):02d}:{int(r['seconds']):02d}", axis=1
    )

    secs = td.dt.total_seconds()
    with pd.option_context("mode.use_inf_as_na", True):
        pace_secs = (secs / df["dist_km"]).where(df["dist_km"] > 0)
    pace_td = pd.to_timedelta(pace_secs, unit="s")
    df["ritmo_min_km"] = pace_td.dt.components.apply(
        lambda r: f"{int(r['minutes'] + 60*(r['hours'] + 24*(r['days']))):02d}:{int(r['seconds']):02d}" if pd.notna(r["seconds"]) else "",
        axis=1
    )

    for col in ["tipo","observacoes"]:
        if col not in df.columns:
            df[col] = ""

    cols = ["data","mes","dia_semana","dist_km","tempo_hms","ritmo_min_km","tipo","observacoes","semana_iso","ano","ano_semana"]
    return df[cols].sort_values("data")

@st.cache_data
def df_to_excel_bytes(df: pd.DataFrame) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="treinos")
        g_mes = df.groupby("mes", as_index=False).agg(
            dist_km=("dist_km","sum"),
            tempo=("tempo_hms", lambda s: pd.to_timedelta(s).sum())
        )
        g_sem = df.groupby("ano_semana", as_index=False).agg(
            dist_km=("dist_km","sum"),
            tempo=("tempo_hms", lambda s: pd.to_timedelta(s).sum())
        )
        g_mes["tempo"] = g_mes["tempo"].astype(str)
        g_sem["tempo"] = g_sem["tempo"].astype(str)
        g_mes.to_excel(writer, index=False, sheet_name="resumo_mes")
        g_sem.to_excel(writer, index=False, sheet_name="resumo_semana")
    return output.getvalue()

def init_state():
    if "df" not in st.session_state:
        st.session_state.df = pd.DataFrame(columns=[
            "data","mes","dia_semana","dist_km","tempo_hms","ritmo_min_km","tipo","observacoes","semana_iso","ano","ano_semana"
        ])

def add_row(form_vals):
    df = st.session_state.df.copy()
    new = pd.DataFrame([form_vals])
    df = pd.concat([df, new], ignore_index=True)
    st.session_state.df = normalize_df(df)

def update_row(idx, form_vals):
    df = st.session_state.df.copy()
    for k,v in form_vals.items():
        df.at[idx, k] = v
    st.session_state.df = normalize_df(df)

def time_to_text(hours:int, minutes:int, seconds:int) -> str:
    h = int(hours or 0); m = int(minutes or 0); s = int(seconds or 0)
    total = h*3600 + m*60 + s
    td = pd.to_timedelta(total, unit="s")
    comps = td.components.iloc[0]
    hh = int(comps["hours"] + 24*(comps["days"]))
    mm = int(comps["minutes"])
    ss = int(comps["seconds"])
    return f"{hh:02d}:{mm:02d}:{ss:02d}"

# Sidebar
st.sidebar.header("📂 Ficheiro")
uploaded = st.sidebar.file_uploader("Carregar CSV ou XLSX", type=["csv","xlsx"])

init_state()

if uploaded:
    if uploaded.name.lower().endswith(".csv"):
        df_file = pd.read_csv(uploaded)
    else:
        try:
            df_file = pd.read_excel(uploaded, sheet_name="treinos")
        except Exception:
            df_file = pd.read_excel(uploaded)
    st.session_state.df = normalize_df(df_file)

if st.session_state.df.empty:
    st.sidebar.info("Sem dados. Use a aba **Adicionar** para criar seus treinos, ou faça upload.")
else:
    st.sidebar.success(f"{len(st.session_state.df)} registos carregados.")

if not st.session_state.df.empty:
    st.sidebar.download_button(
        "⬇️ Descarregar CSV",
        data=st.session_state.df.to_csv(index=False).encode("utf-8"),
        file_name="treinos.csv",
        mime="text/csv"
    )
    st.sidebar.download_button(
        "⬇️ Descarregar Excel",
        data=df_to_excel_bytes(st.session_state.df),
        file_name="treinos.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

st.title("🏃‍♂️ Planilha de Treinos")

tab_add, tab_edit, tab_list, tab_sum = st.tabs(["Adicionar", "Alterar", "Listagem Completa", "Resumos"])

with tab_add:
    st.subheader("Adicionar treino")
    with st.form("form_add", clear_on_submit=True):
        c1, c2 = st.columns(2)
        data = c1.date_input("Data")
        dist = c2.number_input("Distância (km)", min_value=0.0, step=0.01, format="%.2f")
        t1, t2, t3 = st.columns(3)
        h = t1.number_input("Horas", min_value=0, step=1, value=0)
        m = t2.number_input("Minutos", min_value=0, max_value=59, step=1, value=0)
        s = t3.number_input("Segundos", min_value=0, max_value=59, step=1, value=0)
        c3, c4 = st.columns(2)
        tipo = c3.text_input("Tipo (opcional)", value="")
        obs = c4.text_input("Observações (opcional)", value="")
        submitted = st.form_submit_button("➕ Adicionar")
        if submitted:
            tempo = time_to_text(h, m, s)
            vals = {
                "data": pd.to_datetime(data),
                "dist_km": dist,
                "tempo_hms": tempo,
                "tipo": tipo,
                "observacoes": obs,
            }
            add_row(vals)
            st.success("Treino adicionado!")

with tab_edit:
    st.subheader("Alterar treino")
    df = st.session_state.df
    if df.empty:
        st.info("Nenhum treino para editar.")
    else:
        df_disp = df.copy()
        df_disp["linha"] = df_disp.index
        df_disp["label"] = df_disp["data"].dt.strftime("%Y-%m-%d") + " | " + df_disp["dist_km"].fillna(0).map(lambda x: f"{x:.2f} km")
        idx = st.selectbox("Selecione o registo", options=df_disp["linha"], format_func=lambda i: df_disp.loc[i, "label"])
        row = df.loc[idx]

        c1, c2 = st.columns(2)
        data = c1.date_input("Data", value=row["data"].date() if pd.notna(row["data"]) else pd.Timestamp("today").date())
        dist = c2.number_input("Distância (km)", min_value=0.0, step=0.01, value=float(row["dist_km"] or 0))
        t1, t2, t3 = st.columns(3)
        td0 = to_timedelta_safe(row["tempo_hms"])
        comps = td0.components
        h0 = int(comps["hours"] + 24*(comps["days"]))
        m0 = int(comps["minutes"])
        s0 = int(comps["seconds"])
        h = t1.number_input("Horas", min_value=0, step=1, value=h0)
        m = t2.number_input("Minutos", min_value=0, max_value=59, step=1, value=m0)
        s = t3.number_input("Segundos", min_value=0, max_value=59, step=1, value=s0)
        c3, c4 = st.columns(2)
        tipo = c3.text_input("Tipo (opcional)", value=row.get("tipo","") or "")
        obs = c4.text_input("Observações (opcional)", value=row.get("observacoes","") or "")
        colb1, colb2 = st.columns([1,1])
        b_save = colb1.button("💾 Guardar alterações")
        b_delete = colb2.button("🗑️ Apagar este registo")
        if b_save:
            tempo = time_to_text(h, m, s)
            vals = {
                "data": pd.to_datetime(data),
                "dist_km": dist,
                "tempo_hms": tempo,
                "tipo": tipo,
                "observacoes": obs,
            }
            update_row(idx, vals)
            st.success("Registo atualizado.")
        if b_delete:
            st.session_state.df = df.drop(index=idx).reset_index(drop=True)
            st.session_state.df = normalize_df(st.session_state.df)
            st.warning("Registo apagado.")

with tab_list:
    st.subheader("Listagem Completa")
    df = st.session_state.df
    if df.empty:
        st.info("Sem dados.")
    else:
        cc1, cc2, cc3 = st.columns(3)
        year_sel = cc1.multiselect("Filtrar Ano", options=sorted(df["ano"].dropna().unique().tolist()))
        mes_sel = cc2.multiselect("Filtrar Mês (AAAA-MM)", options=sorted(df["mes"].dropna().unique().tolist()))
        tipo_sel = cc3.multiselect("Filtrar Tipo", options=sorted([x for x in df["tipo"].dropna().unique().tolist() if x]))
        q = df.copy()
        if year_sel:
            q = q[q["ano"].isin(year_sel)]
        if mes_sel:
            q = q[q["mes"].isin(mes_sel)]
        if tipo_sel:
            q = q[q["tipo"].isin(tipo_sel)]
        st.dataframe(q.sort_values("data", ascending=False), use_container_width=True)

with tab_sum:
    st.subheader("Resumos")
    df = st.session_state.df
    if df.empty:
        st.info("Sem dados.")
    else:
        t1, t2, t3 = st.columns(3)
        total_km = df["dist_km"].sum()
        total_t = pd.to_timedelta(df["tempo_hms"]).sum()
        ritmo_medio = pd.to_timedelta(df["tempo_hms"]).sum() / df["dist_km"].sum() if total_km > 0 else pd.to_timedelta(0, unit="s")
        t1.metric("Total (km)", f"{total_km:.2f}")
        t2.metric("Total (tempo)", str(total_t))
        t3.metric("Ritmo médio", str(ritmo_medio))

        tab_m, tab_w, tab_tot = st.tabs(["Por mês/ano", "Por semana", "Total"])

        with tab_m:
            g_mes = df.groupby("mes", as_index=False).agg(
                dist_km=("dist_km","sum"),
                tempo=("tempo_hms", lambda s: pd.to_timedelta(s).sum())
            ).sort_values("mes")
            g_mes["tempo"] = g_mes["tempo"].astype(str)
            st.dataframe(g_mes, use_container_width=True)
            st.bar_chart(g_mes.set_index("mes")["dist_km"])

        with tab_w:
            g_sem = df.groupby("ano_semana", as_index=False).agg(
                dist_km=("dist_km","sum"),
                tempo=("tempo_hms", lambda s: pd.to_timedelta(s).sum())
            ).sort_values("ano_semana")
            g_sem["tempo"] = g_sem["tempo"].astype(str)
            st.dataframe(g_sem, use_container_width=True)
            st.bar_chart(g_sem.set_index("ano_semana")["dist_km"])

        with tab_tot:
            st.write("**Totais gerais**")
            c1, c2 = st.columns(2)
            c1.write(f"**Total de treinos:** {len(df)}")
            c1.write(f"**Total de km:** {total_km:.2f}")
            c1.write(f"**Tempo total:** {total_t}")
            c2.write(f"**Primeiro treino:** {df['data'].min().date() if len(df)>0 else '-'}")
            c2.write(f"**Último treino:** {df['data'].max().date() if len(df)>0 else '-'}")
