"""ShiftPlanner: интерфейс Streamlit. Здесь только экран, все расчёты в папке core/."""
import plotly.graph_objects as go
import streamlit as st

from core.baseline import build_baseline
from core.config import DEFAULTS, SHIFTS, WEEKDAYS, allowed_shifts
from core.data_gen import generate_demo
from core.data_io import DataError, load_csv
from core.demand import build_profile, compute_demand
from core.export import pivot_to_schedule, schedule_pivot, to_csv_bytes, to_excel_bytes
from core.kpi import compare_kpis, compute_coverage, compute_kpis
from core.optimizer import OptimizationError, optimize_schedule, validate_schedule
from core.roster import assign_roster, roster_matrix

st.set_page_config(page_title="ShiftPlanner", page_icon="🗓️", layout="wide")
st.title("ShiftPlanner: планирование смен операторов под нагрузку")

# ---------- состояние ----------
for key, value in {"raw": None, "is_demo": False, "result": None, "data_version": 0,
                   "upload_key": None, "upload_error": None, "plan_version": 0}.items():
    st.session_state.setdefault(key, value)

# ---------- параметры (боковая панель) ----------
sb = st.sidebar
sb.header("Параметры")
P = {
    "n_agents": int(sb.number_input("Операторов в штате", 1, 200, DEFAULTS["n_agents"], 1)),
    "max_days": int(sb.number_input("Рабочих дней на оператора в неделю", 1, 7, DEFAULTS["max_days"], 1)),
    "method": sb.radio("Расчёт потребности", ["Erlang C", "Упрощённый"],
                       help="Erlang C учитывает случайность звонков. Упрощённый: нагрузка ÷ допустимая загрузка."),
    "sl_target": float(sb.slider("Цель по уровню сервиса", 0.50, 0.99, DEFAULTS["sl_target"], 0.01)),
    "answer_sec": int(sb.number_input("Ответить за, секунд", 5, 120, DEFAULTS["answer_sec"], 5)),
    "max_occupancy": float(sb.slider("Максимальная загрузка оператора", 0.50, 1.00, DEFAULTS["max_occupancy"], 0.01)),
    "w_deficit": float(sb.number_input("Штраф за час дефицита", 0.1, 100.0, DEFAULTS["w_deficit"], 0.5)),
    "w_excess": float(sb.number_input("Штраф за час избытка", 0.1, 100.0, DEFAULTS["w_excess"], 0.5)),
    "tolerance": int(sb.number_input("Допуск избытка, операторов", 0, 10, DEFAULTS["tolerance"], 1)),
    "hourly_rate": float(sb.number_input("Ставка операторо-часа, руб. (для стоимости простоя)", 0.0, 100000.0,
                                         DEFAULTS["hourly_rate"], 50.0)),
    "time_limit": int(sb.number_input("Лимит времени решателя, сек", 5, 300, DEFAULTS["time_limit"], 5)),
}
sb.caption("Смены: " + "; ".join(s.label() for s in SHIFTS))


# ---------- вспомогательные функции показа ----------
def heatmap(df, value, title, colorscale, zmid=None):
    pivot = df.pivot(index="weekday", columns="hour", values=value).reindex(
        index=range(7), columns=range(8, 22))
    fig = go.Figure(go.Heatmap(
        z=pivot.values, x=[f"{h:02d}:00" for h in pivot.columns], y=WEEKDAYS,
        colorscale=colorscale, zmid=zmid, xgap=1, ygap=1, hoverongaps=False,
        texttemplate="%{z}"))
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(title=title, height=380, margin=dict(l=10, r=10, t=50, b=10))
    return fig


def coverage_for_export(cov):
    out = cov.copy()
    out["weekday"] = out["weekday"].map(lambda d: WEEKDAYS[int(d)])
    out.columns = ["День", "Час", "Нужно", "План", "Разница (+ дефицит, − избыток)"]
    return out.set_index(["День", "Час"])


tab_data, tab_need, tab_plan, tab_res = st.tabs(["1. Данные", "2. Потребность", "3. График", "4. Результаты"])

# ---------- вкладка 1: данные ----------
with tab_data:
    st.write("Загрузите CSV с колонками **timestamp** (дата и время), **calls** (число обращений "
             "за час), **aht_sec** (средняя длительность обработки, секунды) или возьмите демо-данные.")
    uploaded = st.file_uploader("CSV-файл", type=["csv"])
    if uploaded is not None:
        file_key = (uploaded.name, uploaded.size)
        if st.session_state["upload_key"] != file_key:
            st.session_state["upload_key"] = file_key
            try:
                st.session_state["raw"] = load_csv(uploaded)
                st.session_state["is_demo"] = False
                st.session_state["upload_error"] = None
                st.session_state["data_version"] += 1
                st.session_state["result"] = None
            except DataError as exc:
                st.session_state["upload_error"] = str(exc)
        if st.session_state["upload_error"]:
            st.error(st.session_state["upload_error"])

    col1, col2 = st.columns(2)
    if col1.button("Сгенерировать демо-данные"):
        st.session_state["raw"] = generate_demo()
        st.session_state["is_demo"] = True
        st.session_state["upload_error"] = None
        st.session_state["data_version"] += 1
        st.session_state["result"] = None
    col2.download_button("Скачать пример CSV (синтетика)", generate_demo(weeks=1).to_csv(index=False).encode("utf-8"),
                         file_name="example_calls.csv", mime="text/csv")

    raw = st.session_state["raw"]
    if raw is None:
        st.info("Данных пока нет. Загрузите файл или нажмите «Сгенерировать демо-данные».")
    else:
        if st.session_state["is_demo"]:
            st.info("Демо-режим: данные СИНТЕТИЧЕСКИЕ, сгенерированы программой, "
                    "это не данные реальной компании.")
        st.success(f"Данные загружены и проверены. Строк: {len(raw)}. "
                   f"Период: {raw['timestamp'].min():%d.%m.%Y} – {raw['timestamp'].max():%d.%m.%Y}.")
        st.dataframe(raw.head(100))

# ---------- расчёт потребности ----------
demand = None
raw = st.session_state["raw"]
if raw is not None:
    try:
        profile = build_profile(raw)
        demand = compute_demand(profile, "erlang" if P["method"] == "Erlang C" else "simple",
                                P["sl_target"], P["answer_sec"], P["max_occupancy"])
    except (ValueError, RuntimeError) as exc:
        st.error(f"Не удалось рассчитать потребность: {exc}")

# ---------- вкладка 2: потребность ----------
with tab_need:
    if demand is None:
        st.info("Сначала загрузите данные на вкладке «Данные».")
    else:
        m1, m2, m3 = st.columns(3)
        m1.metric("Пик, операторов в час", int(demand["required_agents"].max()))
        m2.metric("Операторо-часов в неделю", int(demand["required_agents"].sum()))
        m3.metric("Среднее обращений в час", f"{demand['avg_calls'].mean():.0f}")
        st.plotly_chart(heatmap(demand, "required_agents", "Нужно операторов: день недели × час",
                                "YlOrRd"))
        if P["method"] == "Erlang C":
            st.caption("Erlang C: сколько операторов нужно, чтобы "
                       f"{P['sl_target']:.0%} обращений получили ответ за {P['answer_sec']} сек "
                       f"при загрузке не выше {P['max_occupancy']:.0%}.")

# ---------- вкладка 3: график ----------
with tab_plan:
    if demand is None:
        st.info("Сначала загрузите данные на вкладке «Данные».")
    else:
        if st.button("Построить график", type="primary"):
            with st.spinner("Строю график..."):
                try:
                    schedule, info = optimize_schedule(
                        demand, P["n_agents"], P["max_days"], P["w_deficit"], P["w_excess"],
                        P["tolerance"], P["time_limit"])
                    baseline = build_baseline(info["total_shifts"], P["n_agents"])
                    st.session_state["plan_version"] += 1
                    st.session_state["result"] = {
                        "schedule": schedule, "baseline": baseline, "info": info, "roster": None,
                        "params": dict(P), "data_version": st.session_state["data_version"]}
                except (ValueError, OptimizationError) as exc:
                    st.error(f"Не удалось построить график: {exc}")

        res = st.session_state["result"]
        if res is None:
            st.info("Задайте параметры слева и нажмите «Построить график».")
        else:
            if res["params"] != P or res["data_version"] != st.session_state["data_version"]:
                st.warning("Параметры или данные изменились после построения. "
                           "Нажмите «Построить график», чтобы пересчитать.")
            res["cov_opt"] = compute_coverage(res["schedule"], demand)
            res["cov_base"] = compute_coverage(res["baseline"], demand)
            kp = res["params"]
            res["kpi_opt"] = compute_kpis(res["cov_opt"], kp["tolerance"], kp["hourly_rate"],
                                          kp["w_deficit"], kp["w_excess"])
            res["kpi_base"] = compute_kpis(res["cov_base"], kp["tolerance"], kp["hourly_rate"],
                                           kp["w_deficit"], kp["w_excess"])

            info = res["info"]
            st.caption(f"Метод: {info['method']}. Время: {info['seconds']} сек. "
                       f"Всего смен: {info['total_shifts']}.")
            if info.get("note"):
                st.warning(info["note"])

            day = st.selectbox("День недели для графика", range(7), format_func=lambda d: WEEKDAYS[d])
            dc = res["cov_opt"][res["cov_opt"]["weekday"] == day]
            fig = go.Figure()
            fig.add_bar(x=[f"{h:02d}:00" for h in dc["hour"]], y=dc["planned"], name="План")
            fig.add_scatter(x=[f"{h:02d}:00" for h in dc["hour"]], y=dc["required"], name="Потребность",
                            mode="lines+markers")
            fig.update_layout(title=f"Потребность и план, {WEEKDAYS[day]}", height=360,
                              margin=dict(l=10, r=10, t=50, b=10), yaxis_title="Операторов")
            st.plotly_chart(fig)

            st.plotly_chart(heatmap(res["cov_opt"], "gap",
                                    "Разница «нужно − план»: красный дефицит, синий избыток",
                                    "RdBu_r", zmid=0))

            st.subheader("График: сколько операторов на какую смену")
            st.dataframe(schedule_pivot(res["schedule"]))

            with st.expander("Ручная правка графика"):
                st.caption("Измените числа в таблице и нажмите «Применить». "
                           "Правка проверяется на ограничения, KPI пересчитываются.")
                pivot = schedule_pivot(res["schedule"])
                edited = st.data_editor(pivot, key=f"editor_{st.session_state['plan_version']}")
                if st.button("Применить правку"):
                    new_schedule = pivot_to_schedule(edited)
                    errors = validate_schedule(new_schedule, kp["n_agents"], kp["max_days"])
                    if errors:
                        st.error("Правка не применена:\n\n" + "\n".join(f"- {e}" for e in errors))
                    else:
                        res["schedule"] = new_schedule
                        res["roster"] = None
                        res["info"] = dict(info, method="Ручная правка", note="")
                        st.session_state["plan_version"] += 1
                        st.rerun()

# ---------- вкладка 4: результаты ----------
with tab_res:
    res = st.session_state["result"]
    if demand is None or res is None or "kpi_opt" not in res:
        st.info("Постройте график на вкладке «График».")
    else:
        ko, kb = res["kpi_opt"], res["kpi_base"]
        c1, c2, c3 = st.columns(3)
        c1.metric("Доля часов дефицита", f"{ko['deficit_hours_share']:.1%}",
                  f"{(ko['deficit_hours_share'] - kb['deficit_hours_share']) * 100:+.1f} п.п. к базовому",
                  delta_color="inverse")
        c2.metric("Покрытие нагрузки", f"{ko['coverage_ratio']:.1%}",
                  f"{(ko['coverage_ratio'] - kb['coverage_ratio']) * 100:+.1f} п.п. к базовому")
        c3.metric("Операторо-часы избытка", f"{ko['excess_agent_hours']:.0f}",
                  f"{ko['excess_agent_hours'] - kb['excess_agent_hours']:+.0f} к базовому",
                  delta_color="inverse")
        st.caption("Базовый график: те же типовые смены (утро и вечер), поровну каждый день, "
                   "то же общее число смен. Показатели рассчитаны по "
                   + ("СИНТЕТИЧЕСКИМ демонстрационным данным." if st.session_state["is_demo"]
                      else "загруженным данным."))

        comparison = compare_kpis(kb, ko)
        st.dataframe(comparison, hide_index=True)

        bars = go.Figure()
        for name, k in (("Базовый", kb), ("Оптимизированный", ko)):
            bars.add_bar(name=name, x=["Дефицит, операторо-ч", "Избыток, операторо-ч"],
                         y=[k["deficit_agent_hours"], k["excess_agent_hours"]])
        bars.update_layout(barmode="group", height=340, margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(bars)

        st.subheader("Назначение сотрудников")
        st.caption("Один человек одна смена в день, не больше "
                   f"{res['params']['max_days']} дней в неделю, отдых между сменами не меньше "
                   f"{DEFAULTS['min_rest_hours']} часов (вечерняя смена не идёт перед утренней).")
        if st.button("Назначить сотрудников"):
            roster, unfilled = assign_roster(res["schedule"], res["params"]["n_agents"],
                                             res["params"]["max_days"])
            res["roster"] = (roster, unfilled)
        if res.get("roster"):
            roster, unfilled = res["roster"]
            matrix = roster_matrix(roster, res["params"]["n_agents"])
            st.dataframe(matrix)
            if unfilled:
                st.warning("Не удалось закрыть смены: "
                           + ", ".join(f"{WEEKDAYS[d]} {n}" for d, n in unfilled)
                           + ". Увеличьте число операторов или поправьте график.")

        st.subheader("Выгрузка")
        sheets = {"График": schedule_pivot(res["schedule"]),
                  "Покрытие": coverage_for_export(res["cov_opt"]),
                  "KPI": comparison.set_index("KPI")}
        if res.get("roster"):
            sheets["Назначения"] = roster_matrix(res["roster"][0], res["params"]["n_agents"])
        d1, d2 = st.columns(2)
        d1.download_button("Скачать Excel", to_excel_bytes(sheets), file_name="shiftplanner.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        d2.download_button("Скачать CSV (график)", to_csv_bytes(schedule_pivot(res["schedule"])),
                           file_name="shiftplanner_schedule.csv", mime="text/csv")
