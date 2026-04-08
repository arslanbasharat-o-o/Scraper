const fs = require('fs');
let html = fs.readFileSync('/Users/arslan0_0/Documents/mobilesentrix_tool_v8-main-2-main/txparts_db_vulnerability_report.html', 'utf8');

// The file has a <style> block we want to replace with our super premium theme
let newStyle = `
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap');

:root {
    --bg: #09090b; /* Zinc 950 */
    --bg2: #18181b; /* Zinc 900 */
    --bg3: #27272a; /* Zinc 800 */
    --bg4: #3f3f46; /* Zinc 700 */
    --border: rgba(255,255,255,0.08); 
    --text: #fafafa;
    --muted: #a1a1aa; /* Zinc 400 */
    
    --red: #ef4444;       
    --red-glow: #fca5a5;  
    --redbg: rgba(239, 68, 68, 0.1);
    
    --orange: #f97316;
    --orgbg: rgba(249, 115, 22, 0.1);
    
    --yellow: #eab308;
    --ylwbg: rgba(234, 179, 8, 0.1);
    
    --green: #22c55e;
    --grnbg: rgba(34, 197, 94, 0.1);
    
    --blue: #3b82f6;
    --blubg: rgba(59, 130, 246, 0.1);
    
    --purple: #a855f7;
    --purpbg: rgba(168, 85, 247, 0.1);
}

* {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
}

body {
    font-family: 'Space Grotesk', system-ui, -apple-system, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    overflow-x: hidden;
    background-image: 
        radial-gradient(circle at 15% 50%, rgba(239, 68, 68, 0.04) 0%, transparent 40%),
        radial-gradient(circle at 85% 30%, rgba(59, 130, 246, 0.04) 0%, transparent 40%);
    background-attachment: fixed;
}

code {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.85em;
    background: var(--bg3);
    padding: 3px 6px;
    border-radius: 6px;
    color: var(--red-glow);
    letter-spacing: -0.02em;
}

pre {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.8rem;
    background: #000;
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.25rem;
    overflow-x: auto;
    color: var(--text);
    line-height: 1.7;
    margin: 1rem 0;
    box-shadow: inset 0 2px 10px rgba(0,0,0,0.5);
}

pre .red { color: var(--red); }
pre .grn { color: var(--green); }
pre .ylw { color: var(--yellow); }
pre .blu { color: var(--blue); }
pre .muted { color: var(--muted); }
pre .pur { color: var(--purple); }

/* Animations */
@keyframes pulse { 0% { transform: scale(0.8); opacity: 0.5; } 100% { transform: scale(1.3); opacity: 0; } }
@keyframes slideUp { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }

/* Header */
.hdr {
    position: relative;
    padding: 5rem 2rem 4rem;
    border-bottom: 1px solid var(--border);
    background: linear-gradient(180deg, rgba(239,68,68,0.06) 0%, var(--bg) 100%);
    overflow: hidden;
}

.hdr::before {
    content: '';
    position: absolute;
    top: -50%; right: -10%;
    width: 60%; height: 200%;
    background: radial-gradient(ellipse at center, rgba(239, 68, 68, 0.12), transparent 70%);
    pointer-events: none;
    z-index: 0;
    filter: blur(40px);
}

.hdr-inner {
    max-width: 1200px;
    margin: 0 auto;
    position: relative;
    z-index: 1;
    animation: slideUp 0.8s cubic-bezier(0.16, 1, 0.3, 1);
}

.badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: var(--redbg);
    border: 1px solid rgba(239, 68, 68, 0.4);
    color: var(--red-glow);
    border-radius: 999px;
    padding: 6px 16px;
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    margin-bottom: 1.5rem;
    box-shadow: 0 0 20px rgba(239, 68, 68, 0.2);
    transition: transform 0.3s;
}

.badge:hover { transform: translateY(-2px); box-shadow: 0 0 30px rgba(239, 68, 68, 0.4); }

.badge::before {
    content: '';
    display: block;
    width: 8px; height: 8px;
    background: var(--red);
    border-radius: 50%;
    box-shadow: 0 0 10px var(--red);
    animation: pulse 2s infinite;
}

.hdr h1 {
    font-size: clamp(2.5rem, 5vw, 4rem);
    font-weight: 700;
    letter-spacing: -0.04em;
    margin-bottom: 0.5rem;
    line-height: 1.1;
}

.hdr h1 span {
    background: linear-gradient(to right, #fff, #a1a1aa);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

.hdr h1 .highlight {
    background: linear-gradient(to right, var(--red-glow), var(--red));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

.hdr .sub {
    color: var(--muted);
    font-size: 1.15rem;
    max-width: 800px;
    margin-top: 1rem;
    font-weight: 400;
}

.meta {
    margin-top: 3rem;
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 1.5rem;
    background: rgba(255,255,255,0.02);
    padding: 2.5rem;
    border-radius: 20px;
    border: 1px solid var(--border);
    backdrop-filter: blur(10px);
}

.mi label {
    display: block;
    color: var(--muted);
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-bottom: 0.4rem;
    font-weight: 600;
}

.mi span {
    font-size: 1.05rem;
    font-weight: 500;
    color: #fff;
}

.wrap {
    max-width: 1200px;
    margin: 0 auto;
    padding: 4rem 2rem;
}

/* Score Card */
.score-card {
    display: grid;
    grid-template-columns: 180px 1fr;
    gap: 3.5rem;
    background: rgba(24, 24, 27, 0.4);
    border: 1px solid var(--border);
    backdrop-filter: blur(12px);
    border-radius: 24px;
    padding: 3.5rem;
    margin-bottom: 5rem;
    align-items: center;
    position: relative;
    overflow: hidden;
    box-shadow: 0 20px 40px rgba(0,0,0,0.3);
    animation: slideUp 0.8s cubic-bezier(0.16, 1, 0.3, 1) 0.1s both;
}

.score-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 4px;
    background: linear-gradient(90deg, var(--red), var(--orange));
}

.donut {
    width: 170px;
    height: 170px;
    border-radius: 50%;
    background: conic-gradient(var(--red) 0deg 144deg, var(--bg3) 144deg);
    display: flex;
    align-items: center;
    justify-content: center;
    position: relative;
    flex-shrink: 0;
    box-shadow: 0 0 30px rgba(239, 68, 68, 0.15);
}

.donut::after {
    content: '';
    position: absolute;
    width: 140px;
    height: 140px;
    background: var(--bg2);
    border-radius: 50%;
    box-shadow: inset 0 2px 10px rgba(0,0,0,0.5);
}

.donut-num {
    position: relative;
    z-index: 1;
    font-size: 2.5rem;
    font-weight: 700;
    background: linear-gradient(135deg, var(--red-glow), var(--red));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

.score-info h2 {
    font-size: 2rem;
    font-weight: 700;
    margin-bottom: 0.8rem;
    letter-spacing: -0.02em;
}

.score-info p {
    color: var(--muted);
    font-size: 1.1rem;
    margin-bottom: 2rem;
    line-height: 1.8;
}

.chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.8rem;
}

.chip {
    padding: 8px 16px;
    border-radius: 8px;
    font-size: 0.85rem;
    font-weight: 600;
    display: flex;
    align-items: center;
    transition: all 0.2s ease;
}

.chip:hover { filter: brightness(1.2); transform: translateY(-1px); }

.chip-r { background: var(--redbg); color: var(--red-glow); border: 1px solid rgba(239, 68, 68, 0.3); }
.chip-o { background: var(--orgbg); color: var(--orange); border: 1px solid rgba(249, 115, 22, 0.3); }
.chip-y { background: var(--ylwbg); color: var(--yellow); border: 1px solid rgba(234, 179, 8, 0.3); }
.chip-g { background: var(--grnbg); color: var(--green); border: 1px solid rgba(34, 197, 94, 0.3); }

/* Findings */
.sec {
    margin-bottom: 5rem;
    animation: slideUp 0.8s cubic-bezier(0.16, 1, 0.3, 1) 0.2s both;
}

.sec-title {
    font-size: 1.75rem;
    font-weight: 700;
    padding-bottom: 1.25rem;
    border-bottom: 1px solid var(--border);
    margin-bottom: 2.5rem;
    display: flex;
    align-items: center;
    gap: 0.8rem;
    letter-spacing: -0.02em;
}

.finding {
    background: rgba(24, 24, 27, 0.3);
    border: 1px solid var(--border);
    border-radius: 20px;
    padding: 2.5rem;
    margin-bottom: 2rem;
    position: relative;
    transition: all 0.3s ease;
}

.finding:hover {
    background: rgba(24, 24, 27, 0.6);
    border-color: rgba(255,255,255,0.1);
    transform: translateY(-2px);
    box-shadow: 0 10px 30px rgba(0,0,0,0.2);
}

.finding::before {
    content: '';
    position: absolute;
    left: -1px; top: 2.5rem; bottom: 2.5rem;
    width: 4px; border-radius: 0 4px 4px 0;
}

.f-crit::before { background: var(--red); box-shadow: 0 0 15px rgba(239,68,68,0.5); }
.f-high::before { background: var(--orange); }
.f-med::before { background: var(--yellow); }
.f-low::before { background: var(--blue); }
.f-ok::before { background: var(--green); }

.f-head {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 1.5rem;
    margin-bottom: 1.25rem;
}

.f-title {
    font-weight: 700;
    font-size: 1.35rem;
    color: #fff;
    letter-spacing: -0.01em;
}

.sev {
    padding: 6px 14px;
    border-radius: 8px;
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    white-space: nowrap;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
}

.s-crit { background: var(--redbg); color: var(--red-glow); border: 1px solid rgba(239, 68, 68, 0.3); }
.s-high { background: var(--orgbg); color: var(--orange); border: 1px solid rgba(249, 115, 22, 0.3); }
.s-med { background: var(--ylwbg); color: var(--yellow); border: 1px solid rgba(234, 179, 8, 0.3); }
.s-low { background: var(--blubg); color: var(--blue); border: 1px solid rgba(59, 130, 246, 0.3); }
.s-ok { background: var(--grnbg); color: var(--green); border: 1px solid rgba(34, 197, 94, 0.3); }

.f-desc {
    color: var(--muted);
    font-size: 1.05rem;
    margin-bottom: 2rem;
    line-height: 1.8;
}

.f-evidence {
    background: rgba(0,0,0,0.4);
    border-radius: 12px;
    padding: 2rem;
    font-size: 0.95rem;
    margin-bottom: 1.5rem;
    border: 1px solid rgba(255,255,255,0.03);
    border-left: 3px solid var(--red);
}

.f-evidence strong {
    display: block;
    color: var(--red-glow);
    margin-bottom: 1rem;
    font-size: 1rem;
}

.f-fix {
    background: rgba(34, 197, 94, 0.05);
    border-radius: 12px;
    padding: 2rem;
    font-size: 0.95rem;
    border: 1px solid rgba(34, 197, 94, 0.1);
    border-left: 3px solid var(--green);
}

.f-fix strong {
    display: block;
    color: var(--green);
    margin-bottom: 1rem;
    font-size: 1rem;
}

/* Payloads */
.payload-box {
    background: #000;
    border: 1px solid var(--border);
    border-radius: 12px;
    overflow: hidden;
    margin: 1.25rem 0;
    box-shadow: inset 0 2px 10px rgba(0,0,0,0.5);
}

.payload-head {
    background: var(--bg3);
    padding: 0.8rem 1.5rem;
    font-size: 0.8rem;
    color: var(--muted);
    font-family: 'JetBrains Mono', monospace;
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
}

.payload-head::before {
    content: '';
    display: inline-block;
    width: 12px; height: 12px;
    border-radius: 50%;
    background: var(--red);
    margin-right: 12px;
    box-shadow: 18px 0 0 var(--yellow), 36px 0 0 var(--green);
    margin-right: 54px;
}

.payload-body {
    padding: 1.5rem;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.85rem;
    color: #e4e4e7;
    white-space: pre-wrap;
    word-break: break-all;
    line-height: 1.7;
}

/* Table container */
.table-container {
    background: rgba(24, 24, 27, 0.4);
    border: 1px solid var(--border);
    border-radius: 20px;
    overflow: hidden;
    box-shadow: 0 10px 30px rgba(0,0,0,0.2);
}

table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.95rem;
}

th {
    background: rgba(255,255,255,0.02);
    color: var(--muted);
    padding: 1.2rem 1.5rem;
    text-align: left;
    font-size: 0.8rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    border-bottom: 1px solid var(--border);
}

td {
    padding: 1.2rem 1.5rem;
    border-bottom: 1px solid rgba(255, 255, 255, 0.02);
    color: #e4e4e7;
}

tr:last-child td { border-bottom: none; }
tr:hover td { background: rgba(255, 255, 255, 0.03); }

.s200 { color: var(--green); font-family: 'JetBrains Mono'; font-weight: 600; }
.s401 { color: var(--yellow); font-family: 'JetBrains Mono'; font-weight: 600; }
.s404 { color: var(--muted); font-family: 'JetBrains Mono'; }
.s405 { color: var(--orange); font-family: 'JetBrains Mono'; font-weight: 600; }
.vuln { color: var(--red-glow); font-weight: 600; }
.safe { color: var(--green); }
.warn { color: var(--yellow); font-weight: 600; }

/* Action Plan */
.action-item {
    background: rgba(24, 24, 27, 0.5);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 2.5rem;
    margin-bottom: 1.5rem;
    position: relative;
    transition: all 0.2s;
    backdrop-filter: blur(10px);
}

.action-item:hover {
    transform: translateX(4px);
    border-color: rgba(255,255,255,0.1);
    background: rgba(24, 24, 27, 0.7);
}

.action-item::before {
    content: '';
    position: absolute;
    left: -1px; top: 2.5rem; bottom: 2.5rem;
    width: 4px; border-radius: 0 4px 4px 0;
}

.action-urgent::before { background: var(--red); box-shadow: 0 0 10px var(--red); }
.action-high::before { background: var(--orange); }
.action-med::before { background: var(--yellow); }
.action-low::before { background: var(--blue); }

.action-header {
    display: flex;
    align-items: center;
    gap: 1.25rem;
    margin-bottom: 1.25rem;
}

.action-num {
    width: 36px; height: 36px;
    border-radius: 50%;
    display: flex;
    align-items: center; justify-content: center;
    font-weight: 700; font-size: 1rem;
    flex-shrink: 0;
    color: #000;
}

.n-urgent { background: var(--red-glow); box-shadow: 0 0 15px rgba(239, 68, 68, 0.4); }
.n-high { background: var(--orange); }
.n-med { background: var(--yellow); }
.n-low { background: var(--blue); }
.n-info { background: var(--muted); }

.action-title {
    font-size: 1.25rem;
    font-weight: 700;
    color: #fff;
}

.action-body {
    padding-left: calc(1.25rem + 36px);
    color: #d4d4d8;
    font-size: 1.05rem;
    line-height: 1.7;
}

.action-body pre {
    margin-top: 1rem;
}

.footer {
    margin-top: 6rem;
    padding: 3rem 2rem;
    border-top: 1px solid var(--border);
    text-align: center;
    color: var(--muted);
    font-size: 0.95rem;
    background: linear-gradient(0deg, rgba(255,255,255,0.02) 0%, transparent 100%);
}

@media(max-width:768px) {
    .score-card { grid-template-columns: 1fr; text-align: center; justify-items: center; padding: 2.5rem; }
    .action-item { padding: 1.5rem; }
    .action-header { margin-bottom: 1rem; }
    .f-head { flex-direction: column; gap: 0.8rem; }
    .action-body { padding-left: 0; margin-top: 1rem; }
}
</style>
`;

let result = html.replace(/<style>[\s\S]*?<\/style>/i, newStyle);

// Title styling
result = result.replace(/<h1><span>txparts\.com<\/span>/, '<h1><span class="highlight">txparts.com</span>');
result = result.replace(/class="donut"><span class="donut-num">40\/100<\/span>/, 'class="glass donut"><span class="donut-num">40</span>');

// Apply new action plan template using regex since old styling is still there
result = result.replace(
    /<div style="background:var\(--bg2\);border:1px solid var\(--border\);border-radius:10px;padding:1\.5rem(?:;margin-bottom:\.8rem)?;border-left:3px solid var\(--red\);\">\s*<div style="display:flex;align-items:center;gap:\.6rem;margin-bottom:\.6rem;"><span style="background:var\(--red\);color:#000;width:26px;height:26px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:900;font-size:\.8rem;flex-shrink:0;">1<\/span><strong>URGENT\s*— Disable Debug Mode \(do this RIGHT NOW\)<\/strong><\/div>/gs, 
    '<div class="action-item action-urgent"><div class="action-header"><span class="action-num n-urgent">1</span><div class="action-title">URGENT — Disable Debug Mode (do this RIGHT NOW)</div></div><div class="action-body">'
);

result = result.replace(
    /<div style="background:var\(--bg2\);border:1px solid var\(--border\);border-radius:10px;padding:1\.5rem(?:;margin-bottom:\.8rem)?;border-left:3px solid var\(--red\);\">\s*<div style="display:flex;align-items:center;gap:\.6rem;margin-bottom:\.6rem;"><span style="background:var\(--orange\);color:#000;width:26px;height:26px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:900;font-size:\.8rem;flex-shrink:0;">2<\/span><strong>Secure\s*the \/api Endpoint<\/strong><\/div>/gs, 
    '</div></div><div class="action-item action-high"><div class="action-header"><span class="action-num n-high">2</span><div class="action-title">Secure the /api Endpoint</div></div><div class="action-body">'
);

result = result.replace(
    /<div style="background:var\(--bg2\);border:1px solid var\(--border\);border-radius:10px;padding:1\.5rem(?:;margin-bottom:\.8rem)?;border-left:3px solid var\(--orange\);\">\s*<div style="display:flex;align-items:center;gap:\.6rem;margin-bottom:\.6rem;"><span style="background:var\(--yellow\);color:#000;width:26px;height:26px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:900;font-size:\.8rem;flex-shrink:0;">3<\/span><strong>Add\s*Rate Limiting \+ CAPTCHA to Login & Register<\/strong><\/div>/gs, 
    '</div></div><div class="action-item action-med"><div class="action-header"><span class="action-num n-med">3</span><div class="action-title">Add Rate Limiting + CAPTCHA to Login & Register</div></div><div class="action-body">'
);

result = result.replace(
    /<div style="background:var\(--bg2\);border:1px solid var\(--border\);border-radius:10px;padding:1\.5rem(?:;margin-bottom:\.8rem)?;border-left:3px solid var\(--yellow\);\">\s*<div style="display:flex;align-items:center;gap:\.6rem;margin-bottom:\.6rem;"><span style="background:var\(--blue\);color:#000;width:26px;height:26px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:900;font-size:\.8rem;flex-shrink:0;">4<\/span><strong>Add\s*All Security Headers \(Apache \/ Cloudflare\)<\/strong><\/div>/gs, 
    '</div></div><div class="action-item action-low"><div class="action-header"><span class="action-num n-low">4</span><div class="action-title">Add All Security Headers (Apache / Cloudflare)</div></div><div class="action-body">'
);

result = result.replace(
    /<div style="background:var\(--bg2\);border:1px solid var\(--border\);border-radius:10px;padding:1\.5rem(?:;margin-bottom:\.8rem)?;border-left:3px solid var\(--yellow\);\">\s*<div style="display:flex;align-items:center;gap:\.6rem;margin-bottom:\.6rem;"><span style="background:var\(--blue\);color:#000;width:26px;height:26px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:900;font-size:\.8rem;flex-shrink:0;">5<\/span><strong>Verify\s*All DB Queries Use Parameterized Statements<\/strong><\/div>/gs, 
    '</div></div><div class="action-item action-low"><div class="action-header"><span class="action-num n-low">5</span><div class="action-title">Verify All DB Queries Use Parameterized Statements</div></div><div class="action-body">'
);

result = result.replace(
    /<div style="background:var\(--bg2\);border:1px solid var\(--border\);border-radius:10px;padding:1\.5rem(?:;margin-bottom:\.8rem)?;border-left:3px solid var\(--blue\);\">\s*<div style="display:flex;align-items:center;gap:\.6rem;margin-bottom:\.6rem;"><span style="background:var\(--muted\);color:#000;width:26px;height:26px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:900;font-size:\.8rem;flex-shrink:0;">6<\/span><strong>Manual\s*Testing Needed \(Cannot do remotely\)<\/strong><\/div>/gs, 
    '</div></div><div class="action-item action-low"><div class="action-header"><span class="action-num n-info">6</span><div class="action-title">Manual Testing Needed (Cannot do remotely)</div></div><div class="action-body">'
);

// Close the last action block
result = result.replace(
    /<\/ul>\s*<\/div>\s*<\/div>\s*<\/div>\s*<div class="footer">/gs,
    '</ul></div></div></div></div><div class="footer">'
);

result = result.replace('405 + FULL PATH DISCLOSED', '405 + FULL PATH DISCLOSURE');
result = result.replace('200 OK — Unauthenticated!', '200 OK — UNAUTHENTICATED API');


fs.writeFileSync('/Users/arslan0_0/Documents/mobilesentrix_tool_v8-main-2-main/txparts_db_vulnerability_report.html', result);
