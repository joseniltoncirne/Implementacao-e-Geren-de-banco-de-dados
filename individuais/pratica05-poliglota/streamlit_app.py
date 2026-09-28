import streamlit as st
import pandas as pd
import plotly.express as px
from db_utils import (
    fetch_years,
    fetch_sessions_by_year,
    fetch_laps_data,
    fetch_driver_names,
    save_analysis_reports,
    fetch_analysis_history
)

st.set_page_config(
    page_title="OpenF1 Data Explorer",
    page_icon="🏎️",
    layout="wide"
)

st.title("🏎️ OpenF1 Data Explorer")
st.markdown("""
Esta aplicação demonstra o uso de **Persistência Poliglota**:
- **MongoDB**: Armazenamento e consulta dos dados brutos e semiestruturados de voltas e sessões.
- **SQLite**: Persistência de relatórios sumarizados, métricas calculadas e histórico de análises.
""")

tab1, tab2 = st.tabs(["📊 Análise de Sessão (MongoDB)", "📜 Histórico de Análises (SQLite)"])

with tab1:
    st.header("Exploração da Telemetria de Corridas")

    try:
        available_years = fetch_years()
    except Exception as e:
        st.error(f"Erro ao conectar ao MongoDB. Verifique suas credenciais em `.env`. Detalhes: {e}")
        st.stop()

    if not available_years:
        st.warning("Nenhum dado de ano encontrado na coleção 'sessions'.")
        st.stop()

    col_filter1, col_filter2 = st.columns(2)
    
    with col_filter1:
        selected_year = st.selectbox("Selecione o Ano:", options=available_years)

    sessions = fetch_sessions_by_year(selected_year)
    
    if not sessions:
        st.info("Nenhuma sessão encontrada para o ano selecionado.")
        st.stop()

    session_map = {
        f"{s.get('location', 'N/A')} - {s.get('session_name', 'Sessão')} ({s.get('country_name', '')})": s
        for s in sessions
    }

    with col_filter2:
        selected_session_label = st.selectbox("Selecione a Sessão:", options=list(session_map.keys()))
    
    selected_session = session_map[selected_session_label]

    st.subheader(f"📍 {selected_session.get('session_name')} - {selected_session.get('location')}")
    st.write(f"**País:** {selected_session.get('country_name', 'N/A')} | **Circuito:** {selected_session.get('circuit_short_name', 'N/A')}")

    df_laps = fetch_laps_data(selected_session["session_key"])

    if df_laps.empty:
        st.warning("Não há registros de voltas cadastrados para esta sessão.")
        st.stop()

    driver_col = "driver_number" if "driver_number" in df_laps.columns else "driver_name"
    lap_duration_col = "lap_duration" if "lap_duration" in df_laps.columns else "duration"
    lap_num_col = "lap_number" if "lap_number" in df_laps.columns else "lap"

    available_drivers = sorted(df_laps[driver_col].dropna().unique())
    driver_names = fetch_driver_names(selected_session["session_key"])
    nome_piloto = lambda d: driver_names.get(d, str(d))

    selected_drivers = st.multiselect(
        "Selecione os pilotos para comparação:",
        options=available_drivers,
        default=available_drivers[:2] if len(available_drivers) >= 2 else available_drivers,
        format_func=nome_piloto
    )

    if selected_drivers:
        df_filtered = df_laps[df_laps[driver_col].isin(selected_drivers)].copy()
        df_filtered["piloto"] = df_filtered[driver_col].map(nome_piloto)
        df_filtered = df_filtered.sort_values(["piloto", lap_num_col])

        st.subheader("📈 Comparativo de Duração de Voltas")
        
        fig = px.line(
            df_filtered,
            x=lap_num_col,
            y=lap_duration_col,
            color="piloto",
            markers=True,
            title="Duração da Volta (segundos) por Volta",
            labels={
                lap_num_col: "Número da Volta",
                lap_duration_col: "Tempo da Volta (s)",
                "piloto": "Piloto"
            }
        )
        fig.update_layout(hovermode="x unified")
        st.plotly_chart(fig, width="stretch")

        with st.expander("📄 Ver Dados Brutos das Voltas"):
            st.dataframe(df_filtered, width="stretch")

        st.divider()

        st.subheader("💾 Persistência Poliglota: Gravar Insights no SQLite")
        st.caption("Ao clicar no botão abaixo, a aplicação calculará métricas agregadas (NoSQL -> Relacional) e salvará na tabela SQLite `race_analysis`.")

        if st.button("🚀 Gerar Resumo da Análise", type="primary"):
            summary_list = []

            for driver in selected_drivers:
                df_driver = df_filtered[df_filtered[driver_col] == driver].copy()

                df_driver_valid = df_driver[df_driver[lap_duration_col] > 0]

                if "is_pit_out_lap" in df_driver_valid.columns:
                    voltas_saida = df_driver.loc[df_driver["is_pit_out_lap"] == True, lap_num_col]
                    voltas_box = set(voltas_saida) | set(voltas_saida - 1)
                    df_driver_consistency = df_driver_valid[~df_driver_valid[lap_num_col].isin(voltas_box)]
                else:
                    df_driver_consistency = df_driver_valid

                fastest_lap = df_driver_valid[lap_duration_col].min() if not df_driver_valid.empty else None
                avg_lap_time = df_driver_valid[lap_duration_col].mean() if not df_driver_valid.empty else None
                total_laps = len(df_driver)
                std_dev = df_driver_consistency[lap_duration_col].std() if len(df_driver_consistency) > 1 else 0.0

                summary_list.append({
                    "session_name": selected_session_label,
                    "driver_name": nome_piloto(driver),
                    "fastest_lap": round(fastest_lap, 3) if fastest_lap else None,
                    "average_lap_time": round(avg_lap_time, 3) if avg_lap_time else None,
                    "total_laps": total_laps,
                    "consistency_std_dev": round(std_dev, 3) if std_dev else 0.0
                })

            st.write("**Métricas Calculadas:**")
            df_summary = pd.DataFrame(summary_list)
            st.dataframe(df_summary, width="stretch")

            try:
                save_analysis_reports(summary_list)
                st.success("✅ Relatório gravado com sucesso no banco relacional SQLite (`analysis_reports.db`)!")
            except Exception as e:
                st.error(f"Erro ao salvar os dados no SQLite: {e}")

    else:
        st.info("Por favor, selecione ao menos um piloto para gerar as métricas e o gráfico.")

with tab2:
    st.header("📜 Histórico de Análises Armazenadas (SQLite)")
    st.markdown("Exibição direta dos dados agregados e persistidos na tabela **`race_analysis`** do banco de dados relacional.")

    try:
        df_history = fetch_analysis_history()
        
        if not df_history.empty:
            df_history = df_history.rename(columns={
                "id": "ID",
                "session_name": "Sessão",
                "driver_name": "Piloto",
                "fastest_lap": "Volta mais Rápida (s)",
                "average_lap_time": "Tempo Médio (s)",
                "total_laps": "Total de Voltas",
                "consistency_std_dev": "Consistência (Desvio Padrão)",
                "analysis_timestamp": "Data/Hora da Análise"
            })
            
            st.dataframe(df_history, width="stretch")
            
            st.divider()
            col_m1, col_m2, col_m3 = st.columns(3)
            col_m1.metric("Total de Análises Salvas", len(df_history))
            col_m2.metric("Sessões Distintas Analisadas", df_history["Sessão"].nunique())
            col_m3.metric("Pilotos Processados", df_history["Piloto"].nunique())

        else:
            st.info("Nenhum histórico encontrado. Realize uma análise na primeira aba e clique em 'Gerar Resumo da Análise'.")
    except Exception as e:
        st.error(f"Erro ao carregar o histórico do SQLite: {e}")