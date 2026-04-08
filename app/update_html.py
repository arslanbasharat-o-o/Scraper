with open('/Users/arslan0_0/Documents/mobilesentrix_tool_v8-main-2-main/txparts_db_vulnerability_report.html', 'r') as f:
    text = f.read()
    
# Clean up some formatting to make it look extremely premium, but preserving all content.

new_css = '''
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap');

        :root {
            --bg: #09090b; /* Zinc 950 */
            --bg2: #18181b; /* Zinc 900 */
            --bg3: #27272a; /* Zinc 800 */
            --bg4: #3f3f46; /* Zinc 700 */
            --border: #3f3f46; 
            --text: #fafafa;
            --muted: #a1a1aa; /* Zinc 400 */
            
            --red: #ef4444;       /* Base modern red */
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
            
            --accent: #ef4444; /* Primary theme accent */
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
                radial-gradient(circle at 15% 50%, rgba(239, 68, 68, 0.03) 0%, transparent 50%),
                radial-gradient(circle at 85% 30%, rgba(59, 130, 246, 0.03) 0%, transparent 50%);
        }

        /* Glassmorphism utility */
        .glass {
            background: rgba(24, 24, 27, 0.6);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.05);
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
            background: var(--bg2);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1.25rem;
            overflow-x: auto;
            color: var(--text);
            line-height: 1.7;
            margin: 1rem 0;
            box-shadow: inset 0 2px 10px rgba(0,0,0,0.5);
        }

        /* Smooth Gradients & Animation */
        @keyframes pulse-ring {
            0% { transform: scale(0.8); opacity: 0.5; }
            100% { transform: scale(1.3); opacity: 0; }
        }

        @keyframes slideUp {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }

        /* HEADER */
        .hdr {
            position: relative;
            padding: 4rem 2rem 3rem;
            border-bottom: 1px solid rgba(255,255,255,0.05);
            background: linear-gradient(180deg, rgba(239,68,68,0.05) 0%, var(--bg) 100%);
            overflow: hidden;
        }

        .hdr::before {
            content: '';
            position: absolute;
            top: -50%;
            right: -10%;
            width: 60%;
            height: 200%;
            background: radial-gradient(ellipse at center, rgba(239, 68, 68, 0.15), transparent 70%);
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
            transition: all 0.3s ease;
        }
        
        .badge:hover {
            box-shadow: 0 0 30px rgba(239, 68, 68, 0.4);
            transform: translateY(-1px);
        }

        .badge::before {
            content: '';
            display: block;
            width: 8px;
            height: 8px;
            background: var(--red);
            border-radius: 50%;
            box-shadow: 0 0 10px var(--red);
            animation: pulse-ring 2s infinite cubic-bezier(0.215, 0.61, 0.355, 1);
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
            font-size: 1.1rem;
            max-width: 800px;
            margin-top: 1rem;
            font-weight: 300;
        }

        .meta {
            margin-top: 2.5rem;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1.5rem;
            background: rgba(255,255,255,0.02);
            padding: 2rem;
            border-radius: 16px;
            border: 1px solid rgba(255,255,255,0.05);
            backdrop-filter: blur(10px);
        }

        .mi label {
            display: block;
            color: var(--muted);
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            margin-bottom: 0.3rem;
            font-weight: 600;
        }

        .mi span {
            font-size: 1rem;
            font-weight: 500;
            color: #fff;
        }

        /* LAYOUT */
        .wrap {
            max-width: 1200px;
            margin: 0 auto;
            padding: 3rem 2rem;
        }

        /* SCORE */
        .score-card {
            display: grid;
            grid-template-columns: 180px 1fr;
            gap: 3rem;
            border-radius: 24px;
            padding: 3rem;
            margin-bottom: 4rem;
            align-items: center;
            position: relative;
            overflow: hidden;
            transition: transform 0.3s ease;
            box-shadow: 0 20px 40px rgba(0,0,0,0.4);
            animation: slideUp 0.8s cubic-bezier(0.16, 1, 0.3, 1) 0.1s both;
            background: rgba(24, 24, 27, 0.4);
            border: 1px solid rgba(255,255,255,0.05);
            backdrop-filter: blur(12px);
        }
        
        .score-card:hover {
            transform: translateY(-5px);
        }

        .score-card::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 4px;
            background: linear-gradient(90deg, var(--red), var(--orange));
        }

        .donut {
            width: 160px;
            height: 160px;
            border-radius: 50%;
            background: conic-gradient(var(--red) 0deg 144deg, var(--bg3) 144deg);
            display: flex;
            align-items: center;
            justify-content: center;
            position: relative;
            flex-shrink: 0;
            box-shadow: 0 0 30px rgba(239, 68, 68, 0.1);
        }

        .donut::after {
            content: '';
            position: absolute;
            width: 130px;
            height: 130px;
            background: var(--bg2); /* matches glass bg usually */
            border-radius: 50%;
            box-shadow: inset 0 2px 10px rgba(0,0,0,0.5);
        }

        .donut-num {
            position: relative;
            z-index: 1;
            font-size: 2.2rem;
            font-weight: 700;
            background: linear-gradient(135deg, var(--red-glow), var(--red));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .score-info h2 {
            font-size: 1.8rem;
            font-weight: 700;
            margin-bottom: 0.8rem;
            letter-spacing: -0.02em;
        }

        .score-info p {
            color: var(--muted);
            font-size: 1.05rem;
            margin-bottom: 1.5rem;
            line-height: 1.8;
            font-weight: 300;
        }

        .chips {
            display: flex;
            flex-wrap: wrap;
            gap: 0.8rem;
        }

        .chip {
            padding: 6px 14px;
            border-radius: 8px;
            font-size: 0.8rem;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 6px;
            transition: all 0.2s ease;
        }
        
        .chip:hover {
            filter: brightness(1.2);
        }

        .chip-r { background: var(--redbg); color: var(--red-glow); border: 1px solid rgba(239, 68, 68, 0.3); }
        .chip-o { background: var(--orgbg); color: var(--orange); border: 1px solid rgba(249, 115, 22, 0.3); }
        .chip-y { background: var(--ylwbg); color: var(--yellow); border: 1px solid rgba(234, 179, 8, 0.3); }
        .chip-g { background: var(--grnbg); color: var(--green); border: 1px solid rgba(34, 197, 94, 0.3); }

        /* SECTION */
        .sec {
            margin-bottom: 4rem;
            animation: slideUp 0.8s cubic-bezier(0.16, 1, 0.3, 1) 0.2s both;
        }

        .sec-title {
            font-size: 1.5rem;
            font-weight: 700;
            padding-bottom: 1rem;
            border-bottom: 1px solid rgba(255,255,255,0.05);
            margin-bottom: 2rem;
            display: flex;
            align-items: center;
            gap: 0.8rem;
            letter-spacing: -0.02em;
        }

        /* FINDING */
        .finding {
            background: rgba(24, 24, 27, 0.4);
            border: 1px solid rgba(255,255,255,0.05);
            border-radius: 16px;
            padding: 2rem;
            margin-bottom: 1.5rem;
            position: relative;
            transition: all 0.3s ease;
        }

        .finding:hover {
            background: rgba(24, 24, 27, 0.8);
            border-color: rgba(255,255,255,0.1);
            transform: translateX(4px);
        }
        
        .finding::before {
            content: '';
            position: absolute;
            left: -1px;
            top: 2rem;
            bottom: 2rem;
            width: 3px;
            border-radius: 0 4px 4px 0;
        }

        .f-crit::before { background: var(--red); box-shadow: 0 0 10px var(--red); }
        .f-high::before { background: var(--orange); box-shadow: 0 0 10px var(--orange); }
        .f-med::before { background: var(--yellow); }
        .f-low::before { background: var(--blue); }
        .f-ok::before { background: var(--green); }

        .f-head {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 1.5rem;
            margin-bottom: 1rem;
        }

        .f-title {
            font-weight: 700;
            font-size: 1.2rem;
            color: #fff;
            letter-spacing: -0.01em;
        }

        .sev {
            padding: 4px 12px;
            border-radius: 6px;
            font-size: 0.75rem;
            font-weight: 700;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            white-space: nowrap;
            flex-shrink: 0;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }

        .s-crit { background: var(--redbg); color: var(--red-glow); border: 1px solid rgba(239, 68, 68, 0.3); }
        .s-high { background: var(--orgbg); color: var(--orange); border: 1px solid rgba(249, 115, 22, 0.3); }
        .s-med { background: var(--ylwbg); color: var(--yellow); border: 1px solid rgba(234, 179, 8, 0.3); }
        .s-low { background: var(--blubg); color: var(--blue); border: 1px solid rgba(59, 130, 246, 0.3); }
        .s-ok { background: var(--grnbg); color: var(--green); border: 1px solid rgba(34, 197, 94, 0.3); }
        .s-info { background: var(--purpbg); color: var(--purple); border: 1px solid rgba(168, 85, 247, 0.3); }

        .f-desc {
            color: var(--muted);
            font-size: 0.95rem;
            margin-bottom: 1.5rem;
            line-height: 1.7;
            font-weight: 300;
        }

        .f-evidence {
            background: rgba(0,0,0,0.3);
            border-radius: 12px;
            padding: 1.5rem;
            font-size: 0.9rem;
            margin-bottom: 1.5rem;
            border: 1px solid rgba(255,255,255,0.03);
            position: relative;
            overflow: hidden;
        }
        
        .f-evidence::after {
            content: '';
            position: absolute;
            top: 0; left: 0; width: 4px; height: 100%;
            background: var(--red);
        }

        .f-evidence strong {
            display: block;
            color: var(--red-glow);
            margin-bottom: 0.8rem;
            font-size: 0.95rem;
        }

        .f-fix {
            background: rgba(34, 197, 94, 0.05);
            border-radius: 12px;
            padding: 1.5rem;
            font-size: 0.9rem;
            border: 1px solid rgba(34, 197, 94, 0.1);
            position: relative;
            overflow: hidden;
        }
        
        .f-fix::after {
            content: '';
            position: absolute;
            top: 0; left: 0; width: 4px; height: 100%;
            background: var(--green);
        }

        .f-fix strong {
            display: block;
            color: var(--green);
            margin-bottom: 0.8rem;
            font-size: 0.95rem;
        }

        /* TABLE */
        .table-container {
            background: rgba(24, 24, 27, 0.4);
            border: 1px solid rgba(255,255,255,0.05);
            border-radius: 16px;
            overflow: hidden;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9rem;
        }

        th {
            background: rgba(255,255,255,0.02);
            color: var(--muted);
            padding: 1rem 1.5rem;
            text-align: left;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }

        td {
            padding: 1rem 1.5rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.02);
            color: #d4d4d8;
        }

        tr:last-child td {
            border-bottom: none;
        }

        tr:hover td {
            background: rgba(255, 255, 255, 0.02);
        }

        .s200 { color: var(--green); font-family: 'JetBrains Mono'; font-weight: 600; }
        .s401 { color: var(--yellow); font-family: 'JetBrains Mono'; font-weight: 600; }
        .s404 { color: var(--muted); font-family: 'JetBrains Mono'; }
        .s405 { color: var(--orange); font-family: 'JetBrains Mono'; font-weight: 600; }
        .s500 { color: var(--red); font-family: 'JetBrains Mono'; font-weight: 600; }

        .vuln { color: var(--red-glow); font-weight: 600; }
        .safe { color: var(--green); }
        .warn { color: var(--yellow); font-weight: 600; }
        .info { color: var(--blue); }

        /* PAYLOAD BOX */
        .payload-box {
            background: #000;
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 10px;
            overflow: hidden;
            margin: 1rem 0;
            box-shadow: inset 0 2px 10px rgba(0,0,0,0.5);
        }

        .payload-head {
            background: var(--bg3);
            padding: 0.6rem 1.2rem;
            font-size: 0.75rem;
            color: var(--muted);
            font-family: 'JetBrains Mono', monospace;
            border-bottom: 1px solid rgba(255,255,255,0.05);
            display: flex;
            align-items: center;
        }
        
        .payload-head::before {
            content: '';
            display: inline-block;
            width: 10px; height: 10px;
            border-radius: 50%;
            background: var(--red);
            margin-right: 10px;
            box-shadow: 16px 0 0 var(--yellow), 32px 0 0 var(--green);
            margin-right: 48px;
        }

        .payload-body {
            padding: 1.2rem;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.85rem;
            color: #e4e4e7;
            white-space: pre-wrap;
            word-break: break-all;
            line-height: 1.6;
        }

        /* ACTION PLAN */
        .action-item {
            background: rgba(24, 24, 27, 0.6);
            border: 1px solid rgba(255,255,255,0.05);
            border-radius: 16px;
            padding: 2rem;
            margin-bottom: 1.2rem;
            position: relative;
            transition: transform 0.2s ease;
            backdrop-filter: blur(10px);
        }
        
        .action-item:hover {
            transform: translateX(4px);
            border-color: rgba(255,255,255,0.1);
        }
        
        .action-item::before {
            content: '';
            position: absolute;
            left: -1px; top: 2rem; bottom: 2rem;
            width: 4px; border-radius: 0 4px 4px 0;
        }

        .action-urgent::before { background: var(--red); box-shadow: 0 0 10px var(--red); }
        .action-high::before { background: var(--orange); }
        .action-med::before { background: var(--yellow); }
        .action-low::before { background: var(--blue); }

        .action-header {
            display: flex;
            align-items: flex-start;
            gap: 1.2rem;
            margin-bottom: 1rem;
        }

        .action-num {
            width: 32px; height: 32px;
            border-radius: 50%;
            display: flex;
            align-items: center; justify-content: center;
            font-weight: 700; font-size: 0.9rem;
            flex-shrink: 0;
            color: #000;
        }

        .n-urgent { background: var(--red-glow); box-shadow: 0 0 15px rgba(239, 68, 68, 0.4); }
        .n-high { background: var(--orange); }
        .n-med { background: var(--yellow); }
        .n-low { background: var(--blue); }
        .n-info { background: var(--muted); }

        .action-title {
            font-size: 1.15rem;
            font-weight: 700;
            color: #fff;
            padding-top: 3px;
        }
        
        .action-body {
            padding-left: calc(1.2rem + 32px);
        }

        .footer {
            margin-top: 5rem;
            padding: 3rem 2rem;
            border-top: 1px solid rgba(255,255,255,0.05);
            text-align: center;
            color: var(--muted);
            font-size: 0.9rem;
            background: linear-gradient(0deg, rgba(255,255,255,0.02) 0%, transparent 100%);
        }

        @media(max-width:768px) {
            .score-card { grid-template-columns: 1fr; text-align: center; justify-items: center; padding: 2rem; }
            .chips { justify-content: center; }
            .score-card { background: rgba(24, 24, 27, 0.8); }
            .action-item { padding: 1.5rem; }
            .f-head { flex-direction: column; gap: 0.5rem; }
            .action-body { padding-left: 0; margin-top: 1rem; }
        }
'''

start_idx = text.find('<style>')
end_idx = text.find('</style>')
if start_idx != -1 and end_idx != -1:
    text = text[:start_idx] + '<style>\n' + new_css + '\n    </style>' + text[end_idx+8:]

# Fix typography mapping
text = text.replace("font-family: 'Inter', sans-serif;", "font-family: 'Space Grotesk', sans-serif;")

# Fix H1
text = text.replace('<h1><span>txparts.com</span>', '<h1><span class="highlight">txparts.com</span>')
text = text.replace('class="donut"><span class="donut-num">40/100</span>', 'class="glass donut"><span class="donut-num">40</span>')

# Update action plan
import re

# Urgent
text = re.sub(r'<div style="background:var\(--bg2\);.*?border-left:3px solid var\(--red\);">', '<div class="action-item action-urgent">', text, 1)
text = text.replace('<div style="display:flex;align-items:center;gap:.6rem;margin-bottom:.6rem;">', '<div class="action-header">', 1)
text = re.sub(r'<span style="background:var\(--red\).*?">1</span>', '<span class="action-num n-urgent">1</span>', text, 1)
text = text.replace('<strong>URGENT\n                        — Disable Debug Mode (do this RIGHT NOW)</strong>', '<div class="action-title">URGENT — Disable Debug Mode (do this RIGHT NOW)</div></div>\n<div class="action-body">', 1)

# High 
text = re.sub(r'<div style="background:var\(--bg2\);.*?border-left:3px solid var\(--red\);">', '<div class="action-item action-high">', text, 1)
text = text.replace('<div style="display:flex;align-items:center;gap:.6rem;margin-bottom:.6rem;">', '<div class="action-header">', 1)
text = re.sub(r'<span style="background:var\(--orange\).*?">2</span>', '<span class="action-num n-high">2</span>', text, 1)
text = text.replace('<strong>Secure\n                        the /api Endpoint</strong>', '<div class="action-title">Secure the /api Endpoint</div></div>\n<div class="action-body">', 1)

# Medium
text = re.sub(r'<div style="background:var\(--bg2\);.*?border-left:3px solid var\(--orange\);">', '<div class="action-item action-med">', text, 1)
text = text.replace('<div style="display:flex;align-items:center;gap:.6rem;margin-bottom:.6rem;">', '<div class="action-header">', 1)
text = re.sub(r'<span style="background:var\(--yellow\).*?">3</span>', '<span class="action-num n-med">3</span>', text, 1)
text = text.replace('<strong>Add\n                        Rate Limiting + CAPTCHA to Login & Register</strong>', '<div class="action-title">Add Rate Limiting + CAPTCHA to Login & Register</div></div>\n<div class="action-body">', 1)

# Low 1
text = re.sub(r'<div style="background:var\(--bg2\);.*?border-left:3px solid var\(--yellow\);">', '<div class="action-item action-low">', text, 1)
text = text.replace('<div style="display:flex;align-items:center;gap:.6rem;margin-bottom:.6rem;">', '<div class="action-header">', 1)
text = re.sub(r'<span style="background:var\(--blue\).*?">4</span>', '<span class="action-num n-low">4</span>', text, 1)
text = text.replace('<strong>Add\n                        All Security Headers (Apache / Cloudflare)</strong>', '<div class="action-title">Add All Security Headers (Apache / Cloudflare)</div></div>\n<div class="action-body">', 1)

# Low 2
text = re.sub(r'<div style="background:var\(--bg2\);.*?border-left:3px solid var\(--yellow\);">', '<div class="action-item action-low">', text, 1)
text = text.replace('<div style="display:flex;align-items:center;gap:.6rem;margin-bottom:.6rem;">', '<div class="action-header">', 1)
text = re.sub(r'<span style="background:var\(--blue\).*?">5</span>', '<span class="action-num n-low">5</span>', text, 1)
text = text.replace('<strong>Verify\n                        All DB Queries Use Parameterized Statements</strong>', '<div class="action-title">Verify All DB Queries Use Parameterized Statements</div></div>\n<div class="action-body">', 1)

# Info
text = re.sub(r'<div style="background:var\(--bg2\);.*?border-left:3px solid var\(--blue\);">', '<div class="action-item action-low">', text, 1)
text = text.replace('<div style="display:flex;align-items:center;gap:.6rem;margin-bottom:.6rem;">', '<div class="action-header">', 1)
text = re.sub(r'<span style="background:var\(--muted\).*?">6</span>', '<span class="action-num n-info">6</span>', text, 1)
text = text.replace('<strong>Manual\n                        Testing Needed (Cannot do remotely)</strong>', '<div class="action-title">Manual Testing Needed (Cannot do remotely)</div></div>\n<div class="action-body">', 1)

# Add closing divs for action bodies
closures = 0
new_parts = []
for part in text.split('</div>\n        </div>\n\n    </div>\n\n    <div class="footer">'):
    if closures == 0:
        new_parts.append(part.replace('\n            </div>\n\n            <div\n                class="action-item', '</div>\n            </div>\n\n            <div\n                class="action-item'))
    closures += 1

text = '</div>\n        </div>\n\n    </div>\n\n    <div class="footer">'.join(new_parts)
text = text.replace('</ul>\n            </div>\n        </div>\n\n    </div>', '</ul>\n</div>\n            </div>\n        </div>\n\n    </div>')

text = text.replace('style="background:var(--bg2);border:1px solid var(--border);border-radius:10px;overflow:hidden;"', 'class="table-container"')

with open('/Users/arslan0_0/Documents/mobilesentrix_tool_v8-main-2-main/txparts_db_vulnerability_report.html', 'w') as f:
    f.write(text)

print("HTML UI Updated!")
