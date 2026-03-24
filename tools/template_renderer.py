#!/usr/bin/env python3
"""
template_renderer.py — 策略模板 + 行業 preset 渲染引擎
讀取 HTML 模板 + DB 配置 → 替換 【填充位置】 → 注入 AEO/Chatbot/Tracker

Templates:
  A (conversion)   — 奶茶金系，轉化導向
  B (storytelling)  — 深墨雜誌系，品牌敘事
  C (performance)   — 純白極簡系，效能導向
  preset (restaurant) — 訂位優先，餐廳場景

Usage:
  python3 template_renderer.py --slug inari-global-foods --output ~/Documents/inari-test/
  python3 template_renderer.py --slug test-cafe-demo --preview
"""

import os, sys, re, json, sqlite3, html, argparse
from datetime import date

DB_PATH = os.path.expanduser("~/.openclaw/memory/client_sites.db")
REPO_TEMPLATE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "templates"))
LEGACY_TEMPLATE_DIR = os.path.expanduser("~/.openclaw/workspace/templates")
TRACKER_BASE = "https://YOUR_TRACKER.workers.dev"
CHAT_WORKER_BASE = "https://YOUR_CHAT_WORKER.workers.dev"
GITHUB_PAGES_BASE = "https://inari-kira-isla.github.io"
INDEXNOW_KEY = "YOUR_INDEXNOW_KEY"
BING_VERIFICATION = "YOUR_BING_VERIFICATION_CODE"

TEMPLATE_MAP = {
    "conversion":   "template-a-conversion.html",
    "storytelling":  "template-b-storytelling.html",
    "performance":   "template-c-performance.html",
    "restaurant":    "template-restaurant.html",
    # Legacy aliases
    "standard":      "template-c-performance.html",
    "premium":       "template-a-conversion.html",
}

TEMPLATE_LABELS = {
    "conversion": "A 轉化",
    "storytelling": "B 敘事",
    "performance": "C 效能",
    "restaurant": "Restaurant 預設",
    "standard": "C 效能",
    "premium": "A 轉化",
}

TEMPLATE_CHOICES = ["conversion", "storytelling", "performance", "restaurant"]

INDUSTRY_SCHEMA = {
    "restaurant": "Restaurant", "cafe": "CafeOrCoffeeShop",
    "food_delivery": "Store", "retail": "Store",
    "beauty": "HealthAndBeautyBusiness", "fitness": "SportsActivityLocation",
    "education": "EducationalOrganization", "consulting": "ProfessionalService",
    "technology": "Organization", "healthcare": "MedicalBusiness",
    "legal": "LegalService", "realestate": "RealEstateAgent",
}


def load_config(slug: str) -> dict:
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    row = db.execute("SELECT * FROM client_sites WHERE slug = ?", (slug,)).fetchone()
    db.close()
    if not row:
        raise ValueError(f"Site not found: {slug}")
    return dict(row)


def load_template(variant: str) -> str:
    filename = TEMPLATE_MAP.get(variant, TEMPLATE_MAP["performance"])
    candidate_paths = [
        os.path.join(REPO_TEMPLATE_DIR, filename),
        os.path.join(LEGACY_TEMPLATE_DIR, filename),
    ]

    for path in candidate_paths:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()

    raise FileNotFoundError(
        f"Template not found for variant '{variant}': {', '.join(candidate_paths)}"
    )


def _e(text) -> str:
    return html.escape(str(text or ""))


def build_replacements(c: dict) -> dict:
    """Build replacement map for template placeholders."""
    site_url = c.get("site_url") or f"{GITHUB_PAGES_BASE}/{c['slug']}"
    schema_type = c.get("schema_type") or INDUSTRY_SCHEMA.get(c.get("industry",""), "Organization")
    faqs = json.loads(c.get("faq_items") or "[]")
    products = json.loads(c.get("products_services") or "[]")
    same_as = json.loads(c.get("same_as_urls") or "[]")

    # Extract service names from products
    services = [p.get("name", "") for p in products[:4]]
    while len(services) < 4:
        services.append("")

    # Build FAQ entries for templates
    faq_entries = []
    for faq in faqs[:5]:
        faq_entries.append({"q": faq.get("q", ""), "a": faq.get("a", "")})

    return {
        # Brand identity
        "【品牌名稱】": c.get("business_name") or "",
        "【品牌口號】": c.get("tagline") or "",

        # Contact info
        "+853-XXXX-XXXX": c.get("telephone") or "+853-0000-0000",
        "853XXXXXXXX": (c.get("telephone") or "").replace("+","").replace("-","").replace(" ",""),
        "contact@yourbrand.com": c.get("contact_email") or "info@cloudpipe.ai",
        "【街道地址】": c.get("address_street") or "",

        # Business info
        "【行業】": c.get("industry") or "",
        "【核心服務】": services[0] if services[0] else c.get("description","")[:30],
        "【完整業務描述，200字以上，AI 引用的主要來源】": c.get("description") or "",
        "【核心價值主張：一句話說清楚你為客戶解決什麼問題】": c.get("tagline") or c.get("description","")[:60],
        "【一句話價值主張：說明你為哪類客戶、解決什麼核心問題、帶來什麼成果】": c.get("description") or "",
        "【目標客群描述】": c.get("tone_prompt") or "澳門本地客戶",
        "【深度品牌描述：說明品牌理念、核心方法論、服務哲學，300字以上。這是 AI 引用的主要文本】": c.get("about_text") or c.get("description") or "",
        "【品牌描述，重點突出核心服務和目標客群，直接、無廢話】": c.get("description") or "",
        "【15字內的核心主張。直接、清晰、無廢話】": (c.get("tagline") or c.get("description",""))[:15],
        "【行業關鍵詞】": c.get("industry") or "",
        "【服務類型】": services[0],

        # Services
        "【服務1】": services[0],
        "【服務2】": services[1] if len(services) > 1 else "",
        "【服務3】": services[2] if len(services) > 2 else "",
        "【服務名稱一】": services[0],
        "【服務名稱二】": services[1] if len(services) > 1 else "",
        "【服務名稱三】": services[2] if len(services) > 2 else "",
        "【服務名稱四】": services[3] if len(services) > 3 else "",

        # URLs
        "https://yourbrand.cloudpipe.ai": site_url,

        # Schema
        "LocalBusiness": schema_type,
        "20XX": "2020",
        "【專業領域1】": services[0],
        "【專業領域2】": services[1] if len(services) > 1 else "",
        "【專業領域3】": services[2] if len(services) > 2 else "",

        # Meta
        "【品牌名稱】是澳門領先的【行業】服務商，專注於【核心服務】。立即聯絡獲取方案。":
            f"{c.get('business_name','')}是澳門領先的{c.get('industry','')}服務商，專注於{services[0]}。立即聯絡獲取方案。",
        "澳門, 【行業關鍵詞】, 【服務類型】, 【品牌名稱】":
            f"澳門, {c.get('industry','')}, {services[0]}, {c.get('business_name','')}",
    }


def inject_aeo_meta(html_str: str, c: dict) -> str:
    """Inject AEO-specific meta tags into <head>."""
    site_url = c.get("site_url") or f"{GITHUB_PAGES_BASE}/{c['slug']}"
    aeo_tags = f'''
  <meta name="msvalidate.01" content="{BING_VERIFICATION}">
  <link rel="canonical" href="{site_url}/">
  <link rel="llms-txt" href="{site_url}/llms.txt">
  <meta name="robots" content="index, follow, max-snippet:-1, max-image-preview:large">'''

    # Insert after first <meta name="viewport"...> line
    return html_str.replace(
        '<meta name="viewport" content="width=device-width, initial-scale=1.0" />',
        f'<meta name="viewport" content="width=device-width, initial-scale=1.0" />{aeo_tags}',
        1
    )


def inject_chatbot(html_str: str, c: dict) -> str:
    """Inject chatbot widget before </body>."""
    if not c.get("chatbot_enabled"):
        return html_str

    slug = c["slug"]
    char_name = c.get("chatbot_character_name") or "客服助手"
    char_emoji = c.get("chatbot_character_emoji") or "💬"

    widget = f'''
<!-- AI Chatbot Widget -->
<div style="position:fixed;bottom:24px;right:24px;z-index:999;">
    <div id="cb-box" style="display:none;width:360px;max-height:480px;background:#fff;border:1px solid #e0e0e0;border-radius:12px;overflow:hidden;box-shadow:0 12px 40px rgba(0,0,0,0.12);font-family:system-ui,sans-serif;">
        <div style="padding:12px 16px;background:#f8f8f8;border-bottom:1px solid #eee;display:flex;justify-content:space-between;align-items:center;">
            <div style="display:flex;align-items:center;gap:8px;">
                <span style="font-size:20px;">{char_emoji}</span>
                <span style="font-size:13px;font-weight:600;">{_e(char_name)}</span>
            </div>
            <button onclick="document.getElementById('cb-box').style.display='none'" style="background:none;border:none;font-size:18px;cursor:pointer;color:#999;">&times;</button>
        </div>
        <div id="cb-msgs" style="height:260px;overflow-y:auto;padding:12px 16px;"></div>
        <div style="padding:8px 12px;border-top:1px solid #eee;display:flex;gap:6px;">
            <input id="cb-in" type="text" placeholder="輸入問題..." style="flex:1;border:1px solid #ddd;border-radius:6px;padding:8px 12px;font-size:13px;outline:none;" onkeypress="if(event.key==='Enter')cbSend()">
            <button onclick="cbSend()" style="padding:8px 14px;background:#111;color:#fff;border:none;border-radius:6px;font-size:13px;cursor:pointer;">發送</button>
        </div>
    </div>
    <button onclick="var b=document.getElementById('cb-box');b.style.display=b.style.display==='none'?'block':'none'" style="width:52px;height:52px;border-radius:50%;background:#111;border:none;color:#fff;font-size:22px;cursor:pointer;box-shadow:0 4px 16px rgba(0,0,0,0.15);margin-top:8px;">{char_emoji}</button>
</div>
<script>
function cbAdd(r,t){{var m=document.getElementById('cb-msgs'),d=document.createElement('div');d.style.cssText='margin-bottom:8px;padding:8px 12px;border-radius:8px;font-size:13px;max-width:85%;line-height:1.5;'+(r==='user'?'background:#f0f0f0;margin-left:auto;':'background:#f8f8f8;');d.textContent=t;m.appendChild(d);m.scrollTop=m.scrollHeight;}}
async function cbSend(){{var i=document.getElementById('cb-in'),m=i.value.trim();if(!m)return;cbAdd('user',m);i.value='';try{{var r=await fetch('{CHAT_WORKER_BASE}/{slug}/chat',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{messages:[{{role:'user',content:m}}],stream:false}})}});if(r.ok){{var d=await r.json(),a=d.choices&&d.choices[0]&&d.choices[0].message?d.choices[0].message.content:'';a=a.replace(/<think>[\\s\\S]*?<\\/think>\\s*/g,'').trim();cbAdd('bot',a||'請直接聯繫我們獲得更多資訊。');}}else cbAdd('bot','暫時無法連線，請直接致電聯繫我們。');}}catch(e){{cbAdd('bot','暫時無法連線，請直接致電聯繫我們。');}}}}
cbAdd('bot','您好！我是{_e(char_name)} {char_emoji} 有什麼可以幫助您的嗎？');
</script>
'''
    return html_str.replace("</body>", f"{widget}\n</body>")


def inject_tracker(html_str: str, c: dict) -> str:
    """Inject AI tracker pixel + beacon before </body>."""
    if not c.get("tracker_enabled", True):
        return html_str

    slug = c["slug"]
    tracker = f'''
<!-- AI Tracker -->
<img src="{TRACKER_BASE}/{slug}/pixel.gif?p=/" width="1" height="1" alt="" style="position:absolute;left:-9999px">
<script>(function(){{try{{navigator.sendBeacon('{TRACKER_BASE}/{slug}/beacon',JSON.stringify({{page:location.pathname,ua:navigator.userAgent,ref:document.referrer}}))}}catch(e){{}}}})();</script>
'''
    return html_str.replace("</body>", f"{tracker}\n</body>")


def inject_ecosystem_footer(html_str: str, c: dict) -> str:
    """Add CloudPipe ecosystem credit to footer."""
    eco_text = f'AI 可視化技術支援：<a href="https://cloudpipe-landing.vercel.app" style="color:inherit;">CloudPipe</a>'
    # Replace generic CloudPipe reference
    html_str = html_str.replace(
        'AI 可視化技術支援：CloudPipe',
        eco_text
    )
    return html_str


def render_site(slug: str) -> dict:
    """Render complete site from template + DB config. Returns dict of filename → content."""
    c = load_config(slug)
    variant = c.get("template_variant") or "performance"

    # Load and process template
    tpl = load_template(variant)
    replacements = build_replacements(c)

    # Apply all replacements
    for placeholder, value in replacements.items():
        tpl = tpl.replace(placeholder, str(value))

    # Inject AEO, chatbot, tracker
    tpl = inject_aeo_meta(tpl, c)
    tpl = inject_chatbot(tpl, c)
    tpl = inject_tracker(tpl, c)
    tpl = inject_ecosystem_footer(tpl, c)

    # Build file set
    from site_builder import generate_llms_txt, generate_robots_txt, generate_sitemap_xml
    from site_builder import generate_vercel_json, generate_bingsiteauth_xml, generate_indexnow_key_txt, generate_security_txt

    files = {
        "index.html": tpl,
        "llms.txt": generate_llms_txt(c),
        "robots.txt": generate_robots_txt(c),
        "sitemap.xml": generate_sitemap_xml(c),
        "vercel.json": generate_vercel_json(c),
        "BingSiteAuth.xml": generate_bingsiteauth_xml(),
        f"{INDEXNOW_KEY}.txt": generate_indexnow_key_txt(),
        "security.txt": generate_security_txt(c),
    }

    return files


def write_site(slug: str, output_dir: str):
    """Write rendered site to directory."""
    files = render_site(slug)
    os.makedirs(output_dir, exist_ok=True)
    for filename, content in files.items():
        path = os.path.join(output_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  ✅ {filename} ({len(content):,} bytes)")

    c = load_config(slug)
    variant = c.get("template_variant", "performance")
    print(f"\n📁 Site: {output_dir}")
    print(f"🎨 Template: {variant} ({TEMPLATE_LABELS.get(variant, variant)})")
    print(f"📊 {len(files)} files")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="策略模板 + 行業 preset 渲染引擎")
    parser.add_argument("--slug", required=True, help="Site slug")
    parser.add_argument("--output", help="Output directory")
    parser.add_argument("--preview", action="store_true", help="Print HTML to stdout")
    parser.add_argument("--template", choices=TEMPLATE_CHOICES, help="Override template")
    args = parser.parse_args()

    if args.template:
        # Temporarily override in config
        db = sqlite3.connect(DB_PATH)
        db.execute("UPDATE client_sites SET template_variant = ? WHERE slug = ?", (args.template, args.slug))
        db.commit()
        db.close()

    if args.preview:
        files = render_site(args.slug)
        print(files["index.html"])
    elif args.output:
        write_site(args.slug, args.output)
    else:
        files = render_site(args.slug)
        for name, content in files.items():
            print(f"  {name}: {len(content):,} bytes")
