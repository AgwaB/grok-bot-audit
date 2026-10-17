#!/usr/bin/env python3
"""Bot Audit, step 5: render the findings JSON as one self-contained HTML file plus a PDF.

Usage:
  python3 make_report.py W/findings.json --outdir W/report [--no-pdf]

Output: fleet_report_<date>.html and fleet_report_<date>.pdf.
Schema: references/findings-schema.md. The report is written in the user's language: findings.json carries
"lang" (BCP 47, sets <html lang>), plain-string text fields in that language, and optional "ui" labels that
override the English defaults in UI_DEFAULT. A quote is {"orig": exact words, "translation": into the report
language, only when the chat language differs}; the translation goes on the main line, the original underneath.
Design rules: references/design-notes.md.

Fonts: system fonts only (nothing is embedded). The CSS stacks below cover macOS/iOS, Windows, Android and Linux, with
Noto and platform fallbacks for non-Latin scripts;
the HTML uses the viewer's fonts, the PDF uses whatever fonts the machine that prints it has.
PDF: headless Chrome/Chromium print-to-pdf with a temporary profile that is removed afterwards.
"""
import argparse, html, json, os, re, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
E = lambda s: html.escape(str(s if s is not None else ''), quote=True)

# ---------- strings ----------
# Default UI labels (English). The host bot writes the report in the user's language and passes translated
# labels in findings.json "ui"; any key it leaves out falls back to these. Keep the {placeholders}.
UI_DEFAULT = {
    'when': 'Checked {date}', 'glance': 'At a glance', 'th': ['Bot', 'Status', 'Current issue', 'Proposals'],
    'n_items': '{n}', 'top': 'Do these 3 first', 'topref': '{bot}, item {n}', 'bybot': 'Bot by bot', 'fleet': 'Across all bots',
    'fleet_h': 'All bots', 'fleet_iss': 'Overlaps, outages, clean-up candidates',
    'fleet_note': 'Nothing is deleted automatically. Before removing a bot, check in the app whether any routine uses it.',
    'fix': 'Fix', 'apply': 'Apply', 'copy': 'Copy', 'copied': 'Copied',
    'kind': {'description': 'Text for the description', 'memory': 'Text for memory', 'routine': 'Text for a new routine', 'other': 'Text to add'},
    'why': 'Why this status', 'improving': 'Already improving, nothing to do', 'more': 'More ({n})', 'see': 'See: {ref}',
    'info': 'For your information', 'collapse': 'Collapse', 'expand': 'Show findings ({n})', 'nothing': 'Nothing major to fix.',
    'fleet_bot': 'All bots', 'st': {'red': 'Clean up', 'yellow': 'Needs work', 'green': 'Fine'},
    'lede_all': 'Checked {n} bots. {y} need work and {r} should be cleaned up.', 'lede_none': 'Checked {n} bots. Nothing major to fix.',
    'lede_y': 'Checked {n} bots. {y} need work.', 'lede_r': 'Checked {n} bots. {r} should be cleaned up.',
    'sel_none': 'Tick the items you want to apply', 'sel_n': '{n} selected', 'go': 'Copy selection', 'sel_prefix': 'Apply: ',
    'pick_first': 'Tick the items to apply first', 'copied_msg': 'Copied: ', 'copy_fail': "Couldn't copy. Please select the text and copy it.",
    'footer': 'Built from the {date} audit. Quotes are taken word for word from the chats; translated quotes show the original below.',
    'date_fmt': '{month} {d}, {y}',
    'months': ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'],
    'quote_marks': ['\u201c', '\u201d'],
}
UI = dict(UI_DEFAULT)

def set_ui(custom):
    """Merge the host bot's labels over the defaults (nested dicts merge key by key)."""
    UI.clear(); UI.update(UI_DEFAULT)
    for k, v in (custom or {}).items():
        if k in UI and isinstance(UI[k], dict) and isinstance(v, dict):
            UI[k] = {**UI[k], **v}
        elif v not in (None, '', []):
            UI[k] = v

def fmt_date(iso):
    y, m, d = int(iso[:4]), int(iso[5:7]), int(iso[8:10])
    months = UI.get('months') or UI_DEFAULT['months']
    return UI['date_fmt'].format(y=y, m=m, d=d, month=months[m - 1] if len(months) >= 12 else m)

def T(x):
    """Text of a field: a plain string (in the report language); a {lang: text} object gives its first value."""
    if isinstance(x, dict):
        return next((v for v in x.values() if isinstance(v, str) and v), '')
    return '' if x is None else str(x)

# ---------- css / js ----------
CSS = r"""
:root{--paper:#FCFCFA;--ink:#1E2226;--sub:#5F666D;--faint:#8A9097;--rule:#DCDDD8;--tint:#F1F2EE;
--acc:#1F5A54;--r:#A23B2A;--y:#8C5D00;--g:#3F6B47;
--intl-sans:'Noto Sans','Noto Sans CJK SC','Noto Sans CJK JP','Noto Sans CJK KR','PingFang SC','Hiragino Sans','Apple SD Gothic Neo','Microsoft YaHei','Yu Gothic','Malgun Gothic','Noto Sans Arabic','Noto Sans Devanagari','Noto Sans Thai';
--intl-serif:'Noto Serif','Noto Serif CJK SC','Noto Serif CJK JP','Noto Serif CJK KR','Songti SC','Hiragino Mincho ProN','SimSun','Yu Mincho';
--sans:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,var(--intl-sans),sans-serif;
--serif:'Iowan Old Style',Charter,'Bitstream Charter','Sitka Text',Cambria,Georgia,var(--intl-serif),serif}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--paper);color:var(--ink);font:400 15.5px/1.7 var(--sans);overflow-wrap:anywhere}
.page{max-width:820px;margin:0 auto;padding:56px 28px 140px}
a{color:inherit}
:focus-visible{outline:2px solid var(--acc);outline-offset:2px}
header h1{font:400 40px/1.15 var(--serif);letter-spacing:-.01em;margin:0}
header .when{color:var(--sub);margin:6px 0 0;font-size:15px}
header .lede{font-size:19px;line-height:1.6;margin:28px 0 0;max-width:34em}
h2{font:600 15px/1.4 var(--sans);color:var(--ink);margin:56px 0 10px;padding-bottom:8px;border-bottom:1px solid var(--ink)}
h2+ol.top li:first-child,h2+.note+details.bot,h2+details.bot{border-top:0}
h2+details.bot,h2+.note+details.bot{margin-top:0}
/* status table */
table.st{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}
table.st th{white-space:nowrap;font-weight:400;font-size:13px;color:var(--faint);text-align:left;padding:0 12px 6px 0}
table.st td{padding:11px 12px 11px 0;border-top:1px solid var(--rule);vertical-align:baseline}
table.st td.n{width:30%;font-weight:600}table.st td.n a{text-decoration:none;white-space:nowrap}
table.st td.n a:hover{text-decoration:underline;text-underline-offset:3px}
table.st td.s{width:16%;white-space:nowrap}table.st td.c{width:10%;text-align:right;color:var(--sub)}
table.st tr.sev-red td{border-top-color:var(--rule)}
.mk{display:inline-block;width:8px;height:8px;margin-right:7px;vertical-align:1px}
.st-r{color:var(--r)}.st-r .mk{background:var(--r)}.st-y{color:var(--y)}.st-y .mk{background:var(--y)}
.st-g{color:var(--g)}.st-g .mk{border:1.5px solid var(--g)}
/* top 3 */
ol.top{list-style:none;margin:0;padding:0;counter-reset:t}
ol.top li{counter-increment:t;display:grid;grid-template-columns:48px 1fr;align-items:baseline;padding:10px 0;border-top:1px solid var(--rule);font-size:17px}
ol.top li::before{content:counter(t);font:400 30px/1 var(--serif);color:var(--acc)}
ol.top a{text-decoration:none}ol.top a:hover{text-decoration:underline;text-underline-offset:3px}
ol.top small{display:block;color:var(--sub);font-size:13.5px}
/* bot sections */
details.bot{border-top:1px solid var(--ink);margin-top:44px}
details.bot>summary{list-style:none;cursor:pointer;display:grid;grid-template-columns:1fr auto;column-gap:16px;padding:14px 0 4px}
details.bot>summary::-webkit-details-marker{display:none}
details.bot>summary h3{font:400 26px/1.3 var(--serif);margin:0}
details.bot>summary .stt{font-size:14px;align-self:center;white-space:nowrap}
details.bot>summary .iss{grid-column:1/-1;color:var(--sub);font-size:15px}
details.bot>summary .tog{grid-column:1/-1;color:var(--faint);font-size:13px;margin-top:2px}
details.bot[open]>summary .tog .c,details.bot:not([open])>summary .tog .o{display:none}
.f{display:grid;grid-template-columns:40px 1fr;padding:20px 0 4px;border-top:1px solid var(--rule);margin-top:14px}
.f:first-child{border-top:0}
.f .no{font:400 20px/1.35 var(--serif);color:var(--faint)}
.f .hd{display:flex;gap:16px;justify-content:space-between;align-items:baseline}
.f h4{font:600 17px/1.45 var(--sans);margin:0}
.ev{margin:10px 0 0;padding:0;list-style:none}
.ev{display:grid;grid-template-columns:minmax(76px,max-content) 1fr;column-gap:12px}.ev li{display:contents}.ev li>span{padding:2px 0}
.ev .d{color:var(--faint);font-size:13.5px;font-variant-numeric:tabular-nums;white-space:nowrap;padding-top:4px}
.ev q{font-family:var(--serif);font-size:16.5px;quotes:none}
.ev .who{color:var(--sub);font-size:13.5px;margin-right:4px}
.ev .orig{display:block;color:var(--sub);font:400 13.5px/1.55 var(--sans);margin-top:1px}
.ev .aft{color:var(--sub);font-size:14px;margin-left:4px}
.gl{white-space:nowrap;color:var(--faint);font-weight:400;font-size:13.5px;margin-left:6px}
summary .gl{font:400 15px var(--sans)}
.ev q{font-size:17px}
header h1{letter-spacing:-.015em}
.fx{margin:12px 0 0;max-width:40em}
.fx b{font-weight:600;margin-right:6px}
.cp{margin:10px 0 2px;background:var(--tint);padding:12px 14px 14px;border-radius:3px}
.cp .k{display:flex;justify-content:space-between;align-items:baseline;font-size:13px;color:var(--sub);margin-bottom:4px}
.cp .t{white-space:pre-wrap;font-size:15px;line-height:1.65}
button.copy{font:600 13px var(--sans);color:var(--acc);background:none;border:0;padding:2px 0;cursor:pointer;text-decoration:underline;text-underline-offset:3px}
button.copy.done{color:var(--sub);text-decoration:none}
label.ap{display:inline-flex;gap:7px;align-items:center;font-size:14px;color:var(--sub);cursor:pointer;white-space:nowrap;user-select:none}
label.ap input{width:17px;height:17px;margin:0;accent-color:var(--acc)}
.f.on h4{color:var(--acc)}.f.on label.ap{color:var(--acc)}
.note{color:var(--sub);margin:4px 0 0;max-width:40em}
.why{color:var(--sub);margin:6px 0 4px;max-width:44em}.why b{color:var(--ink);font-weight:600;margin-right:6px}
.imp{margin:14px 0 4px;color:var(--sub)}.imp b{font-weight:600;color:var(--ink)}.imp ul{margin:4px 0 0;padding-left:1.1em}.imp li{margin:2px 0}
details.more{margin:6px 0 0}details.more>summary{cursor:pointer;color:var(--accent);font-weight:600;padding:8px 0;list-style:none}
details.more>summary::-webkit-details-marker{display:none}
.see{color:var(--accent);white-space:nowrap;margin-left:4px}
.f.pass .fx b{color:var(--sub)}
footer{margin-top:64px;padding-top:12px;border-top:1px solid var(--rule);color:var(--faint);font-size:12.5px}
/* action bar */
.bar{position:fixed;left:0;right:0;bottom:0;background:var(--paper);border-top:1px solid var(--ink);z-index:5}
.bar .in{max-width:820px;margin:0 auto;padding:12px 28px;display:flex;justify-content:space-between;align-items:center;gap:12px}
#cnt{color:var(--sub);font-size:14px}
button.go{font:600 14.5px var(--sans);background:var(--ink);color:var(--paper);border:0;border-radius:3px;padding:10px 16px;cursor:pointer}
button.go:hover{background:var(--acc)}
#msg{position:fixed;left:50%;bottom:72px;transform:translateX(-50%);background:var(--ink);color:var(--paper);padding:7px 12px;font-size:13.5px;border-radius:3px;opacity:0;transition:opacity .15s;pointer-events:none}
#msg.show{opacity:1}
@media (max-width:640px){
 .page{padding:32px 18px 130px}header h1{font-size:32px}header .lede{font-size:17px;margin-top:20px}
 table.st thead{display:none}table.st,table.st tbody,table.st tr,table.st td{display:block;width:auto!important}
 table.st tr{border-top:1px solid var(--rule);}
 table.st tbody tr:first-child{border-top:0} table.st tr{padding:10px 0;display:grid;grid-template-columns:1fr auto}
 table.st td{border:0;padding:0}table.st td.i{grid-column:1/-1;color:var(--sub);font-size:14.5px}table.st td.c{display:none}
 .f{grid-template-columns:28px 1fr}.f .hd{flex-direction:column;gap:4px}
 .ev{display:block}.ev li{display:block;padding:2px 0}.ev li>span{display:block;padding:0}
 details.bot>summary h3{font-size:23px}.bar .in{padding:10px 18px}
}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
@page{size:A4;margin:16mm 16mm 18mm}
@media print{
 body{background:#fff;font-size:10.5pt;line-height:1.6}.page{max-width:none;padding:0}
 .bar,#msg,button,label.ap,.tog{display:none!important}
 details.bot>summary{cursor:auto}details.bot{break-before:auto}
 .f,.cp,ol.top li,table.st tr{break-inside:avoid}h2,details.bot>summary{break-after:avoid}
 header .lede{font-size:13pt}a{text-decoration:none}
 .cp{background:#F3F4F0;-webkit-print-color-adjust:exact;print-color-adjust:exact}
 .mk{-webkit-print-color-adjust:exact;print-color-adjust:exact}
}
"""

JS_TPL = r"""
(function(){
var S=__S__;
var msg=document.getElementById('msg'),t;
function say(s){msg.textContent=s;msg.classList.add('show');clearTimeout(t);t=setTimeout(function(){msg.classList.remove('show')},1500)}
function put(s,ok){function fb(){var a=document.createElement('textarea');a.value=s;a.setAttribute('readonly','');a.style.position='fixed';a.style.opacity='0';document.body.appendChild(a);a.select();var r=false;try{r=document.execCommand('copy')}catch(e){}a.remove();r?ok():say(S.copy_fail)}
 if(navigator.clipboard&&window.isSecureContext){navigator.clipboard.writeText(s).then(ok,fb)}else fb()}
window.__put=put;
document.addEventListener('click',function(e){
 var b=e.target.closest('button.copy');
 if(b){put(b.closest('.cp').querySelector('.t').textContent,function(){b.textContent=S.copied;b.classList.add('done');setTimeout(function(){b.textContent=S.copy;b.classList.remove('done')},1600)});return}
 var a=e.target.closest('a[href^="#"]');
 if(a){var el=document.getElementById(a.getAttribute('href').slice(1));if(el){var d=el.tagName==='DETAILS'?el:el.closest('details');if(d)d.open=true}}
});
function upd(){var n=document.querySelectorAll('input.apply:checked').length;document.getElementById('cnt').textContent=n?S.sel_n.replace('{n}',n):S.sel_none;
 document.querySelectorAll('input.apply').forEach(function(i){i.closest('.f').classList.toggle('on',i.checked)})}
document.addEventListener('change',function(e){if(e.target.classList.contains('apply'))upd()});
window.selText=function(){var g={},o=[];document.querySelectorAll('input.apply:checked').forEach(function(i){var b=i.dataset.bot;if(!g[b]){g[b]=[];o.push(b)}g[b].push(i.dataset.no)});
 return o.length?S.sel_prefix+o.map(function(b){return b+' '+g[b].join('·')}).join(', '):''};
window.copySel=function(){var s=selText();if(!s){say(S.pick_first);return}put(s,function(){say(S.copied_msg+s)})};
window.addEventListener('beforeprint',function(){document.querySelectorAll('details').forEach(function(d){d.dataset.was=d.open?'1':'';d.open=true})});
window.addEventListener('afterprint',function(){document.querySelectorAll('details').forEach(function(d){if(d.dataset.was!==undefined){d.open=!!d.dataset.was}})});
upd();
})();
"""

# ---------- rendering ----------
EVID = re.compile(r'^(\d{1,2}/\d{1,2}(?:~\d{1,2})?(?:\s\d{1,2}:\d{2})?)\s+(.*)$')

def inline(s):
    """Legacy string evidence: escape, set "quoted" parts in the quote face, leading 'X:' as a speaker label."""
    s = E(s)
    s = re.sub(r'^([^\s:&]{1,12}):\s*(?=&quot;)', r'<span class="who">\1</span>', s)
    return re.sub(r'&quot;(.+?)&quot;', r'<q>\1</q>', s)

def norm_q(s):
    return re.sub(r'\s+', ' ', s or '').strip()

def ev_item(it):
    if isinstance(it, str):
        m = EVID.match(it); d, rest = (m.group(1), m.group(2)) if m else ('', it)
        return f'<li><span class="d">{E(d)}</span><span>{inline(rest)}</span></li>'
    d = E(it.get('date', ''))
    who = f'<span class="who">{E(T(it["who"]))}</span>' if it.get('who') else ''
    aft = f'<span class="aft">{E(T(it["after"]))}</span>' if it.get('after') else ''
    if it.get('quote'):
        qd = it['quote']; orig = ''
        if isinstance(qd, dict) and qd.get('orig'):
            main = qd.get('translation') or qd['orig']
            if norm_q(main) != norm_q(qd['orig']):
                orig = f'<span class="orig" lang="{E(qd.get("lang", ""))}">{E(qd["orig"])}</span>' if qd.get('lang') \
                    else f'<span class="orig">{E(qd["orig"])}</span>'
        else:
            main = T(qd)
        oq, cq = (list(UI.get('quote_marks') or ['', '']) + ['', ''])[:2]
        return f'<li><span class="d">{d}</span><span>{who}<q>{E(oq)}{E(main)}{E(cq)}</q>{aft}{orig}</span></li>'
    return f'<li><span class="d">{d}</span><span>{who}{E(T(it.get("text")))}{aft}</span></li>'

REFS = {}
def REFNAME(ref):
    t = UI; bid, n = ref.rsplit('-', 1)
    return t['topref'].format(bot=REFS.get(bid, t['fleet_bot']), n=n)

def finding(f, bot_name, anchor, n):
    t = UI; cp = ''
    if f.get('copy'):
        kind = f.get('copy_kind')
        cp = (f'<div class="cp"><div class="k"><span>{E(t["kind"].get(kind or 'other') or t["kind"].get('other', ''))}</span>'
              f'<button class="copy" type="button">{E(t["copy"])}</button></div><div class="t">{E(T(f["copy"]))}</div></div>')
    passive = bool(f.get('see') or f.get('info'))
    ap = '' if passive else (f'<label class="ap"><input type="checkbox" class="apply" '
                             f'data-bot="{E(bot_name)}" data-no="{n}">{E(t["apply"])}</label>')
    see = ''
    if f.get('see'):
        see = f' <a class="see" href="#{E(f["see"])}">{E(t["see"].format(ref=REFNAME(f["see"])))}</a>'
    lab = t['info'] if f.get('info') else t['fix']
    return (f'<div class="f{" pass" if passive else ""}" id="{E(anchor)}-{n}"><div class="no">{n}</div><div>'
            f'<div class="hd"><h4>{E(T(f["title"]))}</h4>{ap}</div>'
            f'<ul class="ev">{"".join(ev_item(x) for x in f.get("now", []))}</ul>'
            f'<p class="fx"><b>{E(lab)}</b>{E(T(f.get("fix")))}{see}</p>{cp}</div></div>')

def NPROP(b):
    return sum(1 for f in b['findings'] + b.get('more', []) if not f.get('info'))

def gloss(b):
    g = T(b.get('gloss'))
    return f'<span class="gl">{E(g)}</span>' if g else ''

def body(d, print_mode=False):
    t = UI; bots = d['bots']
    REFS.clear(); REFS.update({b['id']: T(b['name']) for b in bots}); REFS['fleet'] = t['fleet_bot']
    c = {k: sum(1 for b in bots if b['status'] == k) for k in ('red', 'yellow', 'green')}
    key = 'lede_all' if c['yellow'] and c['red'] else 'lede_y' if c['yellow'] else 'lede_r' if c['red'] else 'lede_none'
    lede = t[key].format(n=len(bots), y=c['yellow'], r=c['red'])
    cls = {'red': 'st-r', 'yellow': 'st-y', 'green': 'st-g'}
    th = t['th']
    rows = ''.join(
        f'<tr><td class="n"><a href="#bot-{E(b["id"])}">{E(T(b["name"]))}</a>{gloss(b)}</td>'
        f'<td class="s {cls[b["status"]]}"><span class="mk"></span>{E(t["st"][b["status"]])}</td>'
        f'<td class="i">{E(T(b["issue"]))}</td><td class="c">{E(t["n_items"].format(n=NPROP(b)))}</td></tr>' for b in bots)
    names = {b['id']: T(b['name']) for b in bots}; names['fleet'] = t['fleet_bot']
    top = ''.join(f'<li><a href="#{E(x["ref"])}">{E(T(x["text"]))}<small>'
                  f'{E(t["topref"].format(bot=names.get(x["ref"].rsplit("-", 1)[0], ""), n=x["ref"].rsplit("-", 1)[-1]))}</small></a></li>'
                  for x in d.get('top3', []))
    secs = []
    for b in bots:
        op = ' open' if (print_mode or b['status'] != 'green') else ''
        nm = T(b['name'])
        fs = ''.join(finding(f, nm, b['id'], i) for i, f in enumerate(b['findings'], 1)) or f'<p class="note">{E(t["nothing"])}</p>'
        k0 = len(b['findings'])
        if b.get('more'):
            fs += (f'<details class="more"{" open" if print_mode else ""}><summary>{E(t["more"].format(n=len(b["more"])))}</summary>'
                   + ''.join(finding(f, nm, b['id'], k0 + i) for i, f in enumerate(b['more'], 1)) + '</details>')
        why = f'<p class="why"><b>{E(t["why"])}</b>{E(T(b["why"]))}</p>' if b.get('why') else ''
        imp = (f'<div class="imp"><b>{E(t["improving"])}</b><ul>' + ''.join(f'<li>{E(T(x))}</li>' for x in b['improving']) + '</ul></div>') if b.get('improving') else ''
        fs = why + fs + imp
        secs.append(f'<details class="bot" id="bot-{E(b["id"])}"{op}><summary><h3>{E(nm)}{gloss(b)}</h3>'
                    f'<span class="stt {cls[b["status"]]}"><span class="mk"></span>{E(t["st"][b["status"]])}</span>'
                    f'<span class="iss">{E(T(b["issue"]))}</span>'
                    f'<span class="tog"><span class="o">{E(t["collapse"])}</span><span class="c">{E(t["expand"].format(n=len(b["findings"])))}</span></span></summary>{fs}</details>')
    fleet = ''.join(finding(f, t['fleet_bot'], 'fleet', i) for i, f in enumerate(d.get('fleet', []), 1))
    return f"""<div class="page">
<header><h1>{E(T(d['title']).split(' (')[0])}</h1><p class="when">{E(t['when'].format(date=fmt_date(d['date'])))}</p><p class="lede">{E(lede)}</p></header>
<h2>{E(t['glance'])}</h2>
<table class="st"><thead><tr><th>{E(th[0])}</th><th>{E(th[1])}</th><th>{E(th[2])}</th><th style="text-align:right">{E(th[3])}</th></tr></thead><tbody>{rows}</tbody></table>
<h2>{E(t['top'])}</h2><ol class="top">{top}</ol>
<h2>{E(t['bybot'])}</h2>{''.join(secs)}
<h2>{E(t['fleet'])}</h2>
<p class="note">{E(t['fleet_note'])}</p>
<details class="bot" id="bot-fleet" open><summary><h3>{E(t['fleet_h'])}</h3><span class="stt"></span><span class="iss">{E(t['fleet_iss'])}</span>
<span class="tog"><span class="o">{E(t['collapse'])}</span><span class="c">{E(t['expand'].format(n=len(d.get('fleet', []))))}</span></span></summary>{fleet}</details>
<footer>{E(t['footer'].format(date=fmt_date(d['date'])))}</footer>
</div>"""

def page(d, print_mode=False):
    t = UI
    bar = '' if print_mode else (f'<div class="bar"><div class="in"><span id="cnt"></span>'
                                 f'<button class="go" type="button" onclick="copySel()">{E(t["go"])}</button></div></div><div id="msg" role="status"></div>')
    js_s = json.dumps({k: t[k] for k in ('copy', 'copied', 'sel_none', 'sel_n', 'sel_prefix', 'pick_first', 'copied_msg', 'copy_fail')}, ensure_ascii=False)
    js = '' if print_mode else '<script>' + JS_TPL.replace('__S__', js_s) + '</script>'
    return (f'<!doctype html><html lang="{E(d.get("lang") or "en")}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{E(T(d["title"]))} ({E(d["date"][5:7].lstrip("0"))}/{E(d["date"][8:10].lstrip("0"))})</title><style>{CSS}</style></head>'
            f'<body>{body(d, print_mode)}{bar}{js}</body></html>')

def chrome():
    for c in ('chromium', 'chromium-browser', 'google-chrome', 'google-chrome-stable'):
        p = shutil.which(c)
        if p: return p

def to_pdf(html_path, pdf_path):
    exe = chrome()
    if not exe: print('pdf: no Chrome/Chromium found', file=sys.stderr); return False
    prof = tempfile.mkdtemp(prefix='rep-chrome-')
    try:
        r = subprocess.run([exe, '--headless=new', '--no-sandbox', '--disable-gpu', f'--user-data-dir={prof}',
                            '--no-pdf-header-footer', '--virtual-time-budget=3000', f'--print-to-pdf={pdf_path}',
                            'file://' + os.path.abspath(html_path)], capture_output=True, text=True, timeout=120)
        return r.returncode == 0 and os.path.exists(pdf_path)
    finally:
        shutil.rmtree(prof, ignore_errors=True)

def build(d, outdir, pdf=True):
    set_ui(d.get('ui'))
    base = os.path.join(outdir, f'fleet_report_{d["date"]}')
    open(base + '.html', 'w', encoding='utf-8').write(page(d)); print('wrote', base + '.html')
    if pdf:
        tmp = base + '.print.html'
        open(tmp, 'w', encoding='utf-8').write(page(d, print_mode=True))
        ok = to_pdf(tmp, base + '.pdf'); os.remove(tmp)
        print('wrote', base + '.pdf' if ok else 'PDF FAILED')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('findings'); ap.add_argument('--outdir', default='report')
    ap.add_argument('--no-pdf', action='store_true')
    a = ap.parse_args()
    d = json.load(open(a.findings, encoding='utf-8'))
    os.makedirs(a.outdir, exist_ok=True)
    build(d, a.outdir, pdf=not a.no_pdf)

if __name__ == '__main__':
    main()
