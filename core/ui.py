"""토스 스타일 화면 부품: CSS, 카드·KPI·표, Plotly 공통 스타일."""
import html as _h

import streamlit as st

# 토스 계열 색
BLUE, BLUE_D, BLUE_L = "#3182F6", "#1B64DA", "#E8F3FF"
ORANGE, GREEN, RED, PURPLE, PINK, YELLOW = "#FE9800", "#03B26C", "#F04452", "#7A5AF8", "#F25E9E", "#FFC342"
G900, G700, G600, G500, G300, G200, G100, G50 = "#191F28", "#4E5968", "#6B7684", "#8B95A1", "#D1D6DB", "#E5E8EB", "#F2F4F6", "#F9FAFB"
GAPC = "#FFF4E0"
FONT = "Pretendard, 'Malgun Gothic', system-ui, sans-serif"

CSS = """
<style>
@import url("https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css");
html, body, .stApp, .stApp *:not([data-testid="stIconMaterial"]):not(.material-symbols-rounded) { font-family: Pretendard, 'Malgun Gothic', system-ui, sans-serif; }
.stApp { background: #FFFFFF; color: #191F28; }
.block-container { padding-top: 3.8rem; padding-bottom: 6rem; max-width: 1280px; }
section[data-testid="stSidebar"] { background: #F9FAFB; border-right: 1px solid #F2F4F6; }
section[data-testid="stSidebar"] a[data-testid="stSidebarNavLink"] { border-radius: 12px; }
section[data-testid="stSidebar"] a[aria-current="page"], section[data-testid="stSidebar"] a[data-testid="stSidebarNavLink"][aria-current="page"] { background: #E8F3FF; }
section[data-testid="stSidebar"] a[aria-current="page"] span { color: #1B64DA !important; font-weight: 700; }
header[data-testid="stHeader"] { background: rgba(255,255,255,.85); backdrop-filter: blur(8px); }
div[data-testid="stVerticalBlockBorderWrapper"]:has(> div > div[data-testid="stVerticalBlock"]) { border-radius: 20px; }
.stButton > button, .stDownloadButton > button, a[data-testid="stPageLink-NavLink"] { border-radius: 12px; font-weight: 600; }
.stButton > button[kind="primary"] { background: #3182F6; border-color: #3182F6; }
.stButton > button[kind="primary"]:hover { background: #1B64DA; border-color: #1B64DA; }

/* 머리말 */
.ph { display:flex; flex-direction:column; gap:6px; margin: 4px 0 18px; }
.ph .cr { font-size: 13px; font-weight: 700; color: #3182F6; letter-spacing: .02em; }
.ph h1 { font-size: 30px; font-weight: 800; letter-spacing: -0.03em; color: #191F28; margin: 0; padding: 0; line-height: 1.3; }
.ph p { font-size: 16px; color: #4E5968; margin: 0; }
.ct { display:flex; align-items:center; gap:8px; margin: 2px 0 6px; }
.ct b { font-size: 17px; font-weight: 700; color: #191F28; letter-spacing:-0.01em; }
.ct span { margin-left:auto; font-size: 12px; color: #8B95A1; }
.ft { font-size: 12.5px; color: #8B95A1; margin-top: -4px; }

/* KPI */
.kg { display:grid; gap:12px; margin-bottom: 14px; }
.kt { background:#F9FAFB; border-radius:20px; padding:18px 20px; display:flex; flex-direction:column; gap:4px; min-width:0; }
.kt .l { font-size:13.5px; color:#4E5968; font-weight:500; }
.kt .v { font-size:28px; font-weight:800; letter-spacing:-0.02em; color:#191F28; font-variant-numeric: tabular-nums; line-height:1.25; }
.kg.sm .kt { padding:12px 14px; } .kt .v small { font-size:16px; color:#4E5968; font-weight:600; margin-left:2px; }
.kt .s { font-size:12.5px; color:#8B95A1; }
.kt.blue { background:#E8F3FF; } .kt.blue .v { color:#1B64DA; }

/* 안내 상자 */
.easy { display:flex; gap:10px; background:#E8F3FF; color:#191F28; border-radius:16px; padding:14px 16px; font-size:15px; line-height:1.6; margin: 6px 0 12px; }
.easy b.k { color:#1B64DA; white-space:nowrap; }
.info { display:flex; gap:10px; background:#F9FAFB; color:#4E5968; border-radius:14px; padding:12px 14px; font-size:14px; margin: 4px 0 10px; }
.chips { display:flex; flex-wrap:wrap; gap:6px; margin: 6px 0; }
.chip { font-size:13px; padding:5px 12px; border-radius:999px; background:#E8F3FF; color:#1B64DA; font-weight:600; }
.badge { display:inline-block; font-size:12.5px; font-weight:700; padding:3px 10px; border-radius:999px; white-space:nowrap; }
.badge.ok { background:#E5F8EF; color:#03884F; } .badge.chk { background:#FFF4E0; color:#B86E00; } .badge.mu { background:#F2F4F6; color:#6B7684; }
.tl { display:flex; flex-direction:column; gap:7px; margin: 4px 0 8px; }
.tl div { display:grid; grid-template-columns: 76px 1fr; gap:10px; font-size:14.5px; align-items:baseline; color:#333D4B; }
.tl b { color:#3182F6; font-variant-numeric: tabular-nums; }

/* 표 */
table.tt { width:100%; border-collapse:collapse; font-size:14px; font-variant-numeric: tabular-nums; }
table.tt th { text-align:left; font-size:12.5px; color:#8B95A1; font-weight:600; padding:8px 10px; border-bottom:1px solid #E5E8EB; }
table.tt td { padding:10px; border-bottom:1px solid #F2F4F6; color:#333D4B; }
table.tt td.n, table.tt th.n { text-align:right; }
table.tt td:first-child { white-space:nowrap; color:#4E5968; }
table.tt tr.pick td { background:#E8F3FF; }
.bar { display:inline-block; height:8px; border-radius:4px; background:#FE9800; vertical-align:middle; margin-right:6px; }

/* 단계 */
.steps { display:grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap:10px; margin-bottom: 14px; }
.steps div { background:#E8F3FF; border-radius:16px; padding:12px 14px; display:flex; flex-direction:column; gap:2px; }
.steps em { font-style:normal; font-size:11.5px; font-weight:800; color:#3182F6; }
.steps b { font-size:14.5px; color:#191F28; } .steps span { font-size:12.5px; color:#4E5968; }
.gauge { display:grid; gap:3px; margin-top:6px; } .gauge i { height:10px; border-radius:5px; background:#E5E8EB; display:block; } .gauge i.on { background:#3182F6; }
.gl { display:grid; gap:3px; font-size:11px; color:#8B95A1; text-align:center; }

/* 고객 화면 */
.hero { background: linear-gradient(135deg, #E8F3FF 0%, #F9FAFB 70%); border-radius: 28px; padding: 32px 34px; display:grid; grid-template-columns: minmax(0,1.25fr) minmax(0,1fr); gap: 28px; align-items:center; margin-bottom: 16px; }
.hero h1 { font-size: 38px; font-weight: 800; letter-spacing:-0.035em; margin: 8px 0 10px; color:#191F28; line-height:1.25; padding:0; }
.hero p { font-size: 16.5px; color:#4E5968; line-height:1.65; margin: 0 0 6px; }
.hero p b { color:#191F28; }
.dots { display:grid; grid-template-columns: repeat(20, minmax(0,1fr)); gap:5px; }
.dots i { aspect-ratio:1; border-radius:50%; background:#E5E8EB; display:block; animation: fill .4s ease forwards; }
@keyframes fill { from { background:#E5E8EB; transform:scale(.55);} to { background:#03B26C; transform:scale(1);} }
.big { font-size: 40px; font-weight: 800; color:#3182F6; letter-spacing:-0.03em; font-variant-numeric: tabular-nums; line-height:1.15; }
.big small { font-size: 18px; color:#4E5968; font-weight:700; }
.key { background:#F9FAFB; border-radius:24px; padding:22px; display:flex; gap:14px; height:100%; }
.key .n { width:34px; height:34px; border-radius:50%; background:#3182F6; color:#fff; font-weight:800; display:flex; align-items:center; justify-content:center; flex:none; }
.key h3 { font-size:18px; font-weight:800; margin:2px 0 6px; color:#191F28; padding:0; }
.key p { font-size:15px; color:#4E5968; margin:0; line-height:1.6; }
.people { display:grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap:10px; margin: 6px 0 10px; }
.person { display:flex; align-items:center; gap:12px; background:#F9FAFB; border-radius:18px; padding:14px; }
.av { width:46px; height:46px; border-radius:50%; color:#fff; font-weight:800; display:flex; align-items:center; justify-content:center; flex:none; font-size:14px; }
.person .nm { font-weight:800; font-size:15.5px; color:#191F28; } .person .ag { font-size:13px; color:#6B7684; font-weight:500; }
.pill { display:inline-block; font-size:12.5px; font-weight:700; padding:3px 10px; border-radius:999px; margin-top:3px; }
.pill.work { background:#E8F3FF; color:#1B64DA; } .pill.pen { background:#E5F8EF; color:#03884F; } .pill.wait { background:#FFF4E0; color:#B86E00; } .pill.sup { background:#FDEEF5; color:#C2347A; }
.event { background:#E8F3FF; border-radius:16px; padding:14px 16px; font-size:16px; color:#191F28; animation: pop .35s ease; margin-bottom: 8px; }
@keyframes pop { from { opacity:0; transform: translateY(6px);} to { opacity:1; transform:none;} }
.say { font-size: 17px; line-height: 1.65; color:#191F28; } .say b { color:#1B64DA; }
.wave { width:100%; height:56px; display:block; overflow:hidden; }
.wave path { fill:none; stroke:#3182F6; stroke-width:2.6; }
.wave g { animation: wv 1.4s linear infinite; } @keyframes wv { to { transform: translateX(-50px);} }
.lights { display:flex; flex-direction:column; gap:8px; margin-bottom:12px; }
.lights div { display:flex; gap:12px; align-items:center; background:#F9FAFB; border-radius:14px; padding:12px 14px; font-size:15px; color:#333D4B; }
.lamp { width:14px; height:14px; border-radius:50%; flex:none; }
.lamp.g { background:#03B26C; box-shadow:0 0 0 5px rgba(3,178,108,.15); } .lamp.y { background:#FE9800; box-shadow:0 0 0 5px rgba(254,152,0,.18); }
.fadeup { animation: pop .6s ease both; }

/* 물어보기 버튼(고객 화면) */
.st-key-askpop { position: fixed !important; right: 28px; bottom: 26px; z-index: 1000; width: auto !important; }
.st-key-askpop button { background:#3182F6 !important; color:#fff !important; border:0 !important; border-radius:999px !important; padding: 10px 20px !important; box-shadow: 0 8px 24px rgba(49,130,246,.35); font-weight:700 !important; }
.st-key-askpop button p { color:#fff !important; font-size:15px !important; }

@media (max-width: 900px) {
  .hero { grid-template-columns: 1fr; padding: 24px; } .hero h1 { font-size: 30px; }
  .people, .steps { grid-template-columns: 1fr; }
  .ph h1 { font-size: 25px; }
}
@media (prefers-reduced-motion: reduce) { .dots i, .event, .fadeup, .wave g { animation: none !important; } .dots i { background:#03B26C; } }
</style>
"""


def inject():
    st.markdown(CSS, unsafe_allow_html=True)


def md(s):
    # 마크다운이 ~ 두 개를 취소선으로 바꾸지 않도록
    st.markdown(s.replace("~", "&#126;") if "<style" not in s else s, unsafe_allow_html=True)


def esc(s):
    return _h.escape(str(s))


def head(crumb, title, sub=None):
    md(f'<div class="ph"><span class="cr">{crumb}</span><h1>{title}</h1>{f"<p>{sub}</p>" if sub else ""}</div>')


def title(t, right=None):
    md(f'<div class="ct"><b>{t}</b>{f"<span>{right}</span>" if right else ""}</div>')


def foot(t):
    md(f'<div class="ft">{t}</div>')


def easy(t, label="쉽게 말하면"):
    md(f'<div class="easy"><b class="k">{label}</b><span>{t}</span></div>')


def info(t):
    md(f'<div class="info"><span>ⓘ</span><span>{t}</span></div>')


def chips(items):
    md('<div class="chips">' + "".join(f'<span class="chip">{c}</span>' for c in items) + "</div>")


def timeline(rows):
    md('<div class="tl">' + "".join(f"<div><b>{y}</b><span>{t}</span></div>" for y, t in rows) + "</div>")


def badge(t, kind="ok"):
    return f'<span class="badge {kind}">{t}</span>'


def kpis(items, cols=4, fixed=False):
    """items: (label, value_html, sub, blue?)"""
    cells = "".join(
        f'<div class="kt{" blue" if (len(it) > 3 and it[3]) else ""}"><span class="l">{it[0]}</span>'
        f'<span class="v">{it[1]}</span><span class="s">{it[2]}</span></div>' for it in items)
    tmpl = f'repeat({cols},minmax(0,1fr))' if fixed else f'repeat(auto-fit,minmax(min(100%,{max(130, 760 // cols)}px),1fr))'
    md(f'<div class="kg" style="grid-template-columns:{tmpl}">{cells}</div>')


def table(headers, rows, num=(), pick=None):
    th = "".join(f'<th class="{"n" if i in num else ""}">{h}</th>' for i, h in enumerate(headers))
    body = ""
    for r in rows:
        tds = "".join(f'<td class="{"n" if i in num else ""}">{c}</td>' for i, c in enumerate(r))
        body += f'<tr class="{"pick" if pick is not None and r[0] == pick else ""}">{tds}</tr>'
    md(f'<div style="overflow-x:auto"><table class="tt">{"<tr>" + th + "</tr>" if any(headers) else ""}{body}</table></div>')


# ---------------- Plotly ----------------
def style(fig, h=320, legend=True, ysuf=None, xgrid=False):
    fig.update_layout(
        height=h, margin=dict(l=56, r=16, t=44 if legend else 14, b=6), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT, size=13, color=G700), showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, font=dict(size=12.5), bgcolor="rgba(0,0,0,0)"),
        hoverlabel=dict(bgcolor="white", bordercolor=G200, font=dict(family=FONT, color=G900, size=13)),
        bargap=0.35)
    fig.update_xaxes(showgrid=xgrid, gridcolor=G100, linecolor=G200, zeroline=False, tickfont=dict(color=G600), automargin=True, exponentformat="none")
    fig.update_yaxes(gridcolor=G100, zerolinecolor=G200, linecolor="rgba(0,0,0,0)", tickfont=dict(color=G600),
                     ticksuffix=ysuf or "", automargin=True, exponentformat="none", separatethousands=True)
    return fig


def gap(fig, label=True, half=0.5, tint=False):
    """연금 공백기(2036~2039) 띠. tint=True: 면적 그래프 위에 연한 주황을 얹어 회색으로 탁해지지 않게."""
    kw = dict(annotation_text="연금 공백기", annotation_position="top left", annotation_font=dict(size=11.5, color=G600)) if label else {}
    if tint:
        # 면을 칠하면 파란 면적과 섞여 탁해지므로: 양 끝 점선 + 바닥 막대 + 라벨
        x0, x1 = 2036 - half, 2039 + half
        for x in (x0, x1):
            fig.add_vline(x=x, line=dict(color=ORANGE, width=1.5, dash="dot"), layer="above")
        fig.add_shape(type="rect", x0=x0, x1=x1, xref="x", yref="paper", y0=0, y1=0.035, fillcolor=ORANGE, line_width=0, layer="above")
        if label:
            fig.add_annotation(x=(x0 + x1) / 2, y=0.99, xref="x", yref="paper", yanchor="top", showarrow=False, bgcolor="rgba(255,255,255,0.85)",
                               text="연금 공백기", font=dict(size=12, color="#B86E00"))
    else:
        fig.add_vrect(x0=2036 - half, x1=2039 + half, fillcolor=GAPC, line_width=0, layer="below", **kw)
    return fig


def show(fig, key=None):
    st.plotly_chart(fig, theme=None, key=key, config={"displayModeBar": False, "locale": "ko"})


COUNT_JS = """<script>
(()=>{const run=()=>document.querySelectorAll('.cu:not([data-done])').forEach(el=>{el.dataset.done=1;
const to=+el.dataset.to,d=+(el.dataset.d||0),f=v=>v.toLocaleString('ko-KR',{minimumFractionDigits:d,maximumFractionDigits:d});
if(matchMedia('(prefers-reduced-motion: reduce)').matches){el.textContent=f(to);return;}
let t0=null;const step=t=>{t0??=t;const k=Math.min(1,(t-t0)/1200),e=1-Math.pow(1-k,3);el.textContent=f(to*e);if(k<1)requestAnimationFrame(step);};requestAnimationFrame(step);});
run();setTimeout(run,300);})();
</script>"""


def count(to, d=0):
    """숫자 올라가기(JS가 막혀도 최종값이 보이도록 기본 텍스트는 최종값)."""
    txt = f"{to:,.{d}f}"
    return f'<span class="cu" data-to="{to}" data-d="{d}">{txt}</span>'


def count_js():
    st.html(COUNT_JS, unsafe_allow_javascript=True)
