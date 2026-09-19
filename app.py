"""제조 판매실적 대시보드 (Streamlit). SQL은 sql/*.sql, 이 파일은 화면만 담당한다."""
import sqlite3
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent / "src"))
from db import run  # noqa: E402
from etl import DB_PATH, build  # noqa: E402

# 팔레트: 검증된 카테고리 3슬롯 (색은 '사업부'라는 개체에 고정, 순위나 필터로 바뀌지 않음)
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e1"
BLUE, ORANGE, AQUA, MUTED = "#2a78d6", "#eb6834", "#1baf7a", "#8a8985"
UNIT_COLOR = {"Paperboard": BLUE, "Packaging": ORANGE, "Printing & Office": AQUA, "Other": MUTED}

st.set_page_config(page_title="제조 판매실적 대시보드", page_icon="📊", layout="wide")

if not DB_PATH.exists():  # 배포 환경 등 .db가 없으면 원본 CSV에서 재생성
    build()


@st.cache_data
def query(name: str, **params) -> pd.DataFrame:
    return run(name, **params)


def idr(v: float) -> str:
    if abs(v) >= 1e9:
        return f"Rp {v / 1e9:,.2f} B"
    if abs(v) >= 1e6:
        return f"Rp {v / 1e6:,.1f} M"
    return f"Rp {v:,.0f}"


def style(fig: go.Figure, height: int = 360) -> go.Figure:
    fig.update_layout(
        height=height, margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor=SURFACE, plot_bgcolor=SURFACE,
        font=dict(color=INK2, size=12),
        legend=dict(orientation="h", y=1.1, x=0),
        hoverlabel=dict(bgcolor="white", font_color=INK, bordercolor=GRID),
    )
    fig.update_xaxes(showgrid=False, linecolor=GRID, ticks="outside", tickcolor=GRID)
    fig.update_yaxes(gridcolor=GRID, zeroline=False)
    return fig


# ---------- 사이드바: 필터 ----------
with sqlite3.connect(DB_PATH) as con:
    d_min, d_max = con.execute("SELECT MIN(sale_date), MAX(sale_date) FROM sales").fetchone()
    units_all = [r[0] for r in con.execute(
        "SELECT business_unit FROM v_sales_enriched GROUP BY 1 ORDER BY SUM(sales_amount) DESC")]

st.sidebar.header("필터")
picked = st.sidebar.date_input(
    "기간", value=(date.fromisoformat(d_min), date(2023, 10, 31)),
    min_value=date.fromisoformat(d_min), max_value=date.fromisoformat(d_max))
units = st.sidebar.multiselect("사업부", units_all, default=units_all)
growth = st.sidebar.slider("목표 성장률 (%)", -10, 30, 5, help="목표 = 직전 3개월 평균 매출 x (1 + 성장률)") / 100
include_dup = st.sidebar.toggle("중복 후보 행 포함", value=True,
                                help="같은 날·제품·수량·단가가 반복된 40행. 주문번호가 없어 삭제하지 않고 표시만 함")
st.sidebar.caption("2023-11은 15일까지만 있는 불완전한 달이라 기본 기간에서 제외했습니다.")

if not isinstance(picked, tuple) or len(picked) != 2 or not units:
    st.info("기간(시작일과 종료일)과 사업부를 1개 이상 선택하세요.")
    st.stop()

P = dict(start=picked[0].isoformat(), end=picked[1].isoformat(), include_dup=int(include_dup),
         units="," + ",".join(units) + ",")

kpi = query("kpi", **P).iloc[0]
trend = query("monthly_trend", **P)
fam = query("family_summary", **P)
tva = query("target_vs_actual", **P, growth=growth)
top = query("top_products", **P)

if kpi.orders == 0:
    st.warning("선택한 조건에 해당하는 데이터가 없습니다.")
    st.stop()

# ---------- 헤더 ----------
st.title("제조 판매실적 대시보드")
st.caption("인도네시아 종이·포장용지 제조사의 일별 판매 기록 (2022-08 ~ 2023-11) · "
           "목표(계획) 데이터는 실적에서 산출한 시뮬레이션입니다.")

# ---------- KPI ----------
ach = tva.actual.sum() / tva.target.sum() * 100 if len(tva) and tva.target.sum() else None
mom = trend.mom_pct.dropna()
c1, c2, c3, c4 = st.columns(4)
c1.metric("총매출", idr(kpi.total_sales))
c2.metric("계획 대비 달성률", f"{ach:.1f}%" if ach is not None else "-",
          help="목표가 산출되는 달(2022-11~)만 집계" if ach is not None else "기간에 목표 산출 월이 없음")
c3.metric("최근월 전월 대비", f"{mom.iloc[-1]:+.1f}%" if len(mom) else "-",
          help=f"{trend.sale_month.iloc[-1]} 기준" if len(mom) else None)
c4.metric("주문 건수 / 평균 주문액", f"{int(kpi.orders):,}건", f"평균 {idr(kpi.avg_order_value)}", delta_color="off")

# ---------- 월별 실적 vs 목표 / 사업부별 달성률 ----------
left, right = st.columns([3, 2])
with left:
    st.subheader("월별 실적과 목표")
    tgt_m = tva.groupby("sale_month").target.sum()
    fig = go.Figure()
    fig.add_bar(x=trend.sale_month, y=trend.sales / 1e6, name="실적", marker_color=BLUE,
                marker_cornerradius=4, customdata=trend[["mom_pct"]].fillna(0).to_numpy(),
                hovertemplate="실적 %{y:,.1f} M<br>전월 대비 %{customdata[0]:+.1f}%<extra></extra>")
    fig.add_scatter(x=tgt_m.index, y=tgt_m / 1e6, name=f"목표 (성장률 {growth:+.0%})", mode="lines+markers",
                    line=dict(color=ORANGE, width=2), marker=dict(size=8, color=ORANGE, line=dict(width=2, color=SURFACE)),
                    hovertemplate="목표 %{y:,.1f} M<extra></extra>")
    style(fig).update_yaxes(title_text="매출 (백만 Rp)", tickformat=",.0f")
    fig.update_layout(hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)
    if len(tgt_m):
        hit = int((trend.set_index("sale_month").sales.reindex(tgt_m.index) >= tgt_m).sum())
        st.caption(f"목표가 산출된 {len(tgt_m)}개월 중 {hit}개월에서 실적이 목표 이상입니다.")
    else:
        st.caption("선택 기간에는 목표가 산출되는 달이 없습니다 (직전 3개월 데이터가 필요).")

with right:
    st.subheader("사업부별 달성률")
    by_unit = tva.groupby("business_unit")[["actual", "target"]].sum()
    by_unit["pct"] = by_unit.actual / by_unit.target * 100
    fig = go.Figure()
    for u, r in by_unit.sort_values("pct").iterrows():
        fig.add_bar(y=[u], x=[r.pct], name=u, orientation="h", marker_color=UNIT_COLOR[u],
                    marker_cornerradius=4, text=[f"{r.pct:.1f}%"], textposition="outside", cliponaxis=False,
                    hovertemplate=f"{u}<br>달성률 %{{x:.1f}}%<br>실적 {idr(r.actual)}<br>목표 {idr(r.target)}<extra></extra>")
    fig.add_vline(x=100, line=dict(color=INK2, width=1, dash="dot"), layer="below")
    style(fig).update_layout(barmode="group", showlegend=True)
    fig.update_xaxes(title_text="달성률 (%)", range=[0, max(130, by_unit.pct.max() * 1.15) if len(by_unit) else 130])
    fig.update_yaxes(showticklabels=False, gridcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)
    st.caption("점선은 목표 100%. 목표는 직전 3개월 평균 기반의 시뮬레이션입니다.")

# ---------- 제품군 / 상위 품목 ----------
left, right = st.columns([3, 2])
with left:
    st.subheader("제품군별 매출과 점유율")
    f = fam.sort_values("sales")
    fig = go.Figure(go.Bar(
        y=f.product_family, x=f.sales / 1e6, orientation="h", marker_color=BLUE, marker_cornerradius=4,
        text=[f"{s:.1f}%" for s in f.share_pct], textposition="outside", cliponaxis=False,
        customdata=f[["business_unit", "qty", "orders"]].to_numpy(),
        hovertemplate="%{y} (%{customdata[0]})<br>매출 %{x:,.1f} M<br>수량 %{customdata[1]:,}<br>주문 %{customdata[2]}건<extra></extra>"))
    style(fig, 380).update_xaxes(title_text="매출 (백만 Rp)", tickformat=",.0f")
    fig.update_layout(margin=dict(l=8, r=48, t=8, b=8))
    fig.update_yaxes(gridcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)
with right:
    st.subheader("상위 10개 품목")
    st.dataframe(
        top.rename(columns={"product_raw": "품목(원본명)", "product_family": "제품군", "sales": "매출(Rp)", "qty": "수량"}),
        hide_index=True, use_container_width=True, height=380,
        column_config={"매출(Rp)": st.column_config.NumberColumn(format="localized"), "수량": st.column_config.NumberColumn(format="localized")})

# ---------- 데이터 표 (차트의 표 버전) ----------
with st.expander("데이터 표 보기 (월별 추이 / 계획 대비 실적)"):
    st.dataframe(trend.rename(columns={"sale_month": "월", "sales": "매출(Rp)", "prev_sales": "전월 매출", "mom_pct": "전월 대비(%)"}),
                 hide_index=True, use_container_width=True)
    st.dataframe(tva.rename(columns={"sale_month": "월", "business_unit": "사업부", "actual": "실적(Rp)",
                                     "target": "목표(Rp)", "achievement_pct": "달성률(%)"}),
                 hide_index=True, use_container_width=True)

st.divider()
st.caption("데이터 출처: Jabir Muktabir, 'Data Penjualan Produk Cetakan', Kaggle, Apache License 2.0 "
           "(https://www.kaggle.com/datasets/jabirmuktabir/data-penjualan-produk-cetakan). "
           "정제·제품군 표준화·사업부 분류·목표 산출은 이 프로젝트에서 수행한 변경입니다.")
