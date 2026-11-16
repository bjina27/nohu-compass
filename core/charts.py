"""화면에서 같이 쓰는 Plotly 그래프."""
import plotly.graph_objects as go

from core import data as d
from core.ui import BLUE, BLUE_D, ORANGE, GREEN, RED, PURPLE, PINK, YELLOW, G200, G300, G500, G900, style, gap


def rgba(hex_, a):
    h = hex_.lstrip("#")
    return f"rgba({int(h[0:2],16)},{int(h[2:4],16)},{int(h[4:6],16)},{a})"


def fan(h=340):
    f = d.D()["fan"]
    x = f["years"]
    fig = go.Figure()
    for lo, hi, a, nm in (("p5", "p95", .14, "5~95%"), ("p25", "p75", .30, "25~75%")):
        fig.add_trace(go.Scatter(x=x, y=f[lo], line=dict(width=0), hoverinfo="skip", showlegend=False))
        fig.add_trace(go.Scatter(x=x, y=f[hi], line=dict(width=0), fill="tonexty", fillcolor=rgba(BLUE, a), name=nm, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=x, y=f["p5"], line=dict(width=0), name="하위 5%", hovertemplate="하위 5%%: %{y:.2f}억<extra></extra>", showlegend=False))
    fig.add_trace(go.Scatter(x=x, y=f["p50"], line=dict(color=BLUE, width=3), name="중앙값", hovertemplate="중앙값: %{y:.2f}억<extra></extra>"))
    style(fig, h, ysuf="억")
    fig.update_layout(hovermode="x unified")
    return gap(fig)


def donut(k, h=190):
    w = d.WEIGHTS[k]
    labels = ["예적금(비상자금)", "채권", "주식"]
    fig = go.Figure(go.Pie(labels=[f"{l} {v}%" for l, v in zip(labels, w)], values=w, hole=.62, sort=False,
                           marker=dict(colors=[YELLOW, BLUE, ORANGE], line=dict(color="white", width=2)),
                           textinfo="none", hovertemplate="%{label}<extra></extra>", direction="clockwise"))
    style(fig, h)
    fig.update_layout(legend=dict(orientation="v", x=1.0, y=.5, yanchor="middle"), margin=dict(l=0, r=0, t=4, b=4),
                      annotations=[dict(text=f"<b>{k}</b>", showarrow=False, font=dict(size=17, color=G900))])
    return fig


def cashflow(h=420):
    rows = d.D()["cashflow"]
    x = [r["year"] for r in rows]
    fig = go.Figure()
    for nm, k, c in (("근로소득", "wage", BLUE), ("국민연금", "pension", GREEN), ("퇴직급여", "retire", PURPLE),
                     ("생활비", "living", ORANGE), ("가족 지원", "family", PINK), ("주택대출", "housing", YELLOW)):
        fig.add_trace(go.Bar(x=x, y=[r[k] for r in rows], name=nm, marker_color=c, hovertemplate=f"{nm}: %{{y:,.0f}}만<extra></extra>"))
    fig.add_trace(go.Scatter(x=x, y=[r["net"] for r in rows], name="순현금흐름", line=dict(color=G900, width=2),
                             hovertemplate="순현금흐름: %{y:,.0f}만<extra></extra>"))
    style(fig, h)
    fig.update_layout(barmode="relative", hovermode="x unified", bargap=.25)
    return gap(fig)


def net_bars(y0=2030, y1=2042, h=260):
    rows = [r for r in d.D()["cashflow"] if y0 <= r["year"] <= y1]
    fig = go.Figure(go.Bar(x=[r["year"] for r in rows], y=[r["net"] for r in rows],
                           marker_color=[ORANGE if r["net"] < 0 else BLUE for r in rows],
                           hovertemplate="%{x}년: %{y:,.0f}만 원<extra></extra>"))
    style(fig, h, legend=False)
    fig.update_xaxes(dtick=2, tickangle=0)
    return gap(fig)


def heatmap(market, method, h=330):
    cells = d.heat(market, method)
    A, S = [60, 65, 70], [59, 64, 69]
    z = [[next(c for c in cells if c["a"] == a and c["s"] == s)["cvar"] for s in S] for a in A]
    txt = [[(lambda c: f"<b>{c['cvar']:.2f}억</b><br>실패 {c['short']:.2f}%")(next(c for c in cells if c["a"] == a and c["s"] == s)) for s in S] for a in A]
    fig = go.Figure(go.Heatmap(z=z, x=[f"배우자 {s}세" for s in S], y=[f"A씨 {a}세" for a in A], text=txt,
                               texttemplate="%{text}", textfont=dict(size=14), showscale=False, xgap=4, ygap=4,
                               colorscale=[[0, "#F2F4F6"], [.5, "#90C2FF"], [1, BLUE_D]],
                               hovertemplate="%{y} · %{x}<br>나쁜 경우 %{z:.2f}억<extra></extra>"))
    fig.add_shape(type="rect", x0=1.5, x1=2.5, y0=1.5, y1=2.5, line=dict(color=G900, width=3))
    style(fig, h, legend=False)
    fig.update_xaxes(side="top")
    return fig


def claim_bars(market, method, h=330):
    pick = [("일찍 (60·59세)", 60, 59), ("제때 (65·64세)", 65, 64), ("늦게 · 추천 (70·69세)", 70, 69)]
    cs = [d.cell(a, s, market, method) for _, a, s in pick]
    fig = go.Figure([go.Bar(name="중앙값", x=[p[0] for p in pick], y=[c["p50"] for c in cs], marker_color=BLUE, hovertemplate="%{y:.2f}억<extra>중앙값</extra>"),
                     go.Bar(name="나쁜 경우 (하위 5% 평균)", x=[p[0] for p in pick], y=[c["cvar"] for c in cs], marker_color=ORANGE, hovertemplate="%{y:.2f}억<extra>나쁜 경우</extra>")])
    return style(fig, h, ysuf="억")


def scatter(market, h=440):
    pts = d.D()["scatter"][market]
    fig = go.Figure()
    for nm, flt, col, sym in (("비상자금 6개월 (B)", lambda p: p["pass"] and p["id"][0] == "B", BLUE, "circle"),
                              ("비상자금 3개월 (A)", lambda p: p["pass"] and p["id"][0] == "A", ORANGE, "circle"),
                              ("검정 탈락", lambda p: not p["pass"], G500, "circle-open")):
        ps = [p for p in pts if flt(p)]
        fig.add_trace(go.Scatter(x=[p["vol"] for p in ps], y=[p["p50"] for p in ps], mode="markers+text", name=nm,
                                 text=[p["id"] if p["id"] in ("B00", "B40", "A100") else "" for p in ps], textposition="middle left" if col == ORANGE else "middle right",
                                 textfont=dict(color=G900, size=13),
                                 marker=dict(color=col, symbol=sym, size=[16 if p["id"] == "B00" else 11 for p in ps], line=dict(color="white", width=2) if sym == "circle" else dict(color=col, width=2)),
                                 customdata=[[p["id"], p["eq"], p["cvar"], p["short"]] for p in ps],
                                 hovertemplate="<b>%{customdata[0]}</b> 나머지 중 주식 %{customdata[1]}%<br>중앙값 %{y}억 · 나쁜 경우 %{customdata[2]}억 · 실패 %{customdata[3]}%<extra></extra>"))
    style(fig, h)
    xs = [p["vol"] for p in pts]
    fig.update_xaxes(title="연간 예상 변동성 (%)", showgrid=True, range=[min(xs) - 1.2, max(xs) + 1.6])
    fig.update_yaxes(title="100세 중앙값 (억 원)")
    return fig


def stress_bars(market, h=330):
    order = ["S0", "S1", "S2", "S3b", "S4b"]
    fig = go.Figure()
    for s, c, nm in (("B00", BLUE, "B00 (주식 0%)"), ("B40", ORANGE, "B40 (주식 약 29%)")):
        rs = [d.stress(s, k, market) for k in order]
        fig.add_trace(go.Bar(name=nm, x=[d.STRESS_NAMES[k].replace(" ", "<br>", 1) for k in order], y=[r["cvar"] for r in rs], marker_color=c,
                             customdata=[[r["p50"], r["short"]] for r in rs],
                             hovertemplate="나쁜 경우 %{y}억 · 중앙값 %{customdata[0]}억 · 실패 %{customdata[1]}%<extra>" + nm + "</extra>"))
    style(fig, h, ysuf="억")
    return fig.update_xaxes(tickangle=0)


def guard_bars(h=330):
    gs = ["none", "bridge", "living", "both"]
    v = [d.guard("S2", g)["short"] for g in gs]
    fig = go.Figure(go.Bar(x=[d.GUARD_NAMES[g].replace(" ", "<br>", 1) for g in gs], y=v, marker_color=[GREEN if g == "living" else ORANGE for g in gs],
                           text=[f"{x:.2f}%" for x in v], textposition="outside", hovertemplate="%{y:.2f}%<extra></extra>"))
    style(fig, h, legend=False, ysuf="%")
    fig.update_xaxes(tickangle=0)
    fig.update_yaxes(range=[0, max(v) * 1.3])
    return fig


def tornado(h=470):
    rows = sorted(d.D()["tornado"]["rows"], key=lambda r: -max(abs(r["d_low"]), abs(r["d_high"])))[::-1]
    lab = [f"{r['name']}<br><span style='font-size:11px;color:{G500}'>{r['lo']} / {r['hi']}</span>" for r in rows]
    fig = go.Figure([go.Bar(name="낮은 값", y=lab, x=[r["d_low"] for r in rows], orientation="h", marker_color=BLUE,
                            customdata=[[r["lo"], r["basis"]] for r in rows], hovertemplate="%{customdata[0]}: %{x:+.2f}억 (근거: %{customdata[1]})<extra></extra>"),
                     go.Bar(name="높은 값", y=lab, x=[r["d_high"] for r in rows], orientation="h", marker_color=ORANGE,
                            customdata=[[r["hi"], r["basis"]] for r in rows], hovertemplate="%{customdata[0]}: %{x:+.2f}억 (근거: %{customdata[1]})<extra></extra>")])
    style(fig, h)
    fig.update_layout(barmode="overlay", bargap=.3, margin=dict(l=150))
    fig.update_xaxes(showgrid=True, ticksuffix="억", zeroline=True, zerolinecolor=G300)
    return fig


def family_timeline(h=250):
    """가족 시간표: 막대 안에 설명을 직접 써서 범례 없이 읽히게 한다. (시작, 끝) 은 포함 연도."""
    rows = {"A씨": [(2026, 2035, "근로 (2035 은퇴)", BLUE), (2036, 2038, "연금 대기", YELLOW), (2039, 2069, "국민연금 (70세~)", GREEN)],
            "배우자": [(2026, 2033, "근로 (2033 은퇴)", BLUE), (2034, 2035, "대기", YELLOW), (2036, 2069, "국민연금 (69세~)", GREEN)],
            "아들": [(2026, 2044, "부모 지원 · 월 38.2만 (45세까지)", PINK)]}
    who = ["아들", "배우자", "A씨"]
    fig = go.Figure()
    for w in who:
        for s0, s1, lab, c in rows[w]:
            fig.add_trace(go.Bar(y=[w], x=[s1 - s0 + 1], base=[s0], orientation="h", marker=dict(color=c, cornerradius=8, line=dict(color="white", width=2)),
                                 text=[lab], textposition="inside", insidetextanchor="middle", textfont=dict(color="white" if c != YELLOW else G900, size=13),
                                 hovertemplate=f"{w} · {lab}: {s0}~{s1}년<extra></extra>", showlegend=False))
    style(fig, h, legend=False)
    fig.update_layout(barmode="overlay", bargap=.38, margin=dict(l=64, t=10))
    fig.update_xaxes(range=[2026, 2070], tickvals=[2026, 2030, 2035, 2040, 2045, 2050, 2055, 2060, 2065, 2069], showgrid=True)
    return fig


def balance(h=230):
    lab, v = ["주택", "금융자산", "자동차 등", "주택담보대출"], [3.30, 0.70, 0.23, -1.10]
    fig = go.Figure(go.Bar(y=lab[::-1], x=v[::-1], orientation="h", marker_color=[RED, BLUE, BLUE, BLUE],
                           text=[f"{x:.2f}억" for x in v[::-1]], textposition=["inside" if x < 0 else "outside" for x in v[::-1]], insidetextfont=dict(color="white"),
                           hovertemplate="%{y}: %{x:.2f}억<extra></extra>"))
    style(fig, h, legend=False)
    fig.update_layout(margin=dict(l=100))
    fig.update_xaxes(range=[-1.4, 4.0], ticksuffix="억", showgrid=True)
    return fig


RATING = {"낮음": ORANGE, "보통": BLUE, "높음": BLUE_D}
RCODE = {"낮음": 1, "보통": 2, "높음": 3}


def cfa_strip(outside, h=150):
    ys = d.D()["cfa"][outside]
    x = [y["y"] for y in ys]
    z = [[RCODE.get(y["r"], 0) for y in ys]]
    txt = [[f"{y['y']}년 · <b>{y['r']}</b><br>인출 비율 {y['liq']}% · 바닥 {y['floor']}억 · 완충 {y['cushion']}억" for y in ys]]
    cs = [[0, G300], [.1667, G300], [.1667, ORANGE], [.5, ORANGE], [.5, BLUE], [.8333, BLUE], [.8333, BLUE_D], [1, BLUE_D]]
    fig = go.Figure(go.Heatmap(z=z, x=x, y=[""], zmin=0, zmax=3, colorscale=cs, showscale=False, xgap=2,
                               text=txt, hovertemplate="%{text}<extra></extra>"))
    style(fig, h, legend=False)
    fig.update_layout(margin=dict(l=8, r=8, t=26, b=6))
    fig.add_shape(type="rect", x0=2035.5, x1=2039.5, y0=-0.62, y1=0.62, line=dict(color=G900, width=2, dash="dot"))
    fig.add_annotation(x=2037.5, y=0.62, yanchor="bottom", text="연금 공백기", showarrow=False, font=dict(size=12, color=G900))
    fig.add_annotation(x=2067, y=0.62, yanchor="bottom", text="남은 기간 5년 이하", showarrow=False, font=dict(size=11, color=G500))
    fig.update_yaxes(visible=False)
    fig.update_xaxes(dtick=4, showgrid=False)
    return fig


def liq_bars(outside, h=260):
    ys = d.D()["cfa"][outside]
    fig = go.Figure(go.Bar(x=[y["y"] for y in ys], y=[y["liq"] for y in ys], marker_color=[ORANGE if y["r"] == "낮음" else BLUE for y in ys],
                           customdata=[y["r"] for y in ys], hovertemplate="%{x}년 인출 비율 %{y}% · CFA %{customdata}<extra></extra>"))
    style(fig, h, legend=False, ysuf="%")
    return gap(fig)


def need_bars(h=200):
    n = d.D()["need"]
    lab = ["필요한 수익률", "현금(예적금)", "채권", "주식"][::-1]
    v = [n["req"] * 100, n["cash"], n["bond"], n["eq"]][::-1]
    fig = go.Figure(go.Bar(y=lab, x=v, orientation="h", marker_color=[GREEN, YELLOW, BLUE, ORANGE][::-1],
                           text=[f"{x:.2f}%" for x in v], textposition="outside", hovertemplate="%{y}: %{x:.2f}%<extra></extra>"))
    style(fig, h, legend=False)
    fig.update_layout(margin=dict(l=100))
    fig.update_xaxes(range=[0, 10], ticksuffix="%", showgrid=True)
    return fig


def pair_bars(labels, a, b, na, nb, h=300, ca=BLUE, cb=ORANGE, suf="억"):
    fig = go.Figure([go.Bar(name=na, x=labels, y=a, marker_color=ca, text=[f"{x:.2f}{suf}" for x in a], textposition="outside", hovertemplate="%{y:.2f}" + suf + "<extra>" + na + "</extra>"),
                     go.Bar(name=nb, x=labels, y=b, marker_color=cb, text=[f"{x:.2f}{suf}" for x in b], textposition="outside", hovertemplate="%{y:.2f}" + suf + "<extra>" + nb + "</extra>")])
    style(fig, h, ysuf=suf)
    fig.update_yaxes(range=[0, max(a + b) * 1.22])
    return fig
