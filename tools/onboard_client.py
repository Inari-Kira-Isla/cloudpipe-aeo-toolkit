#!/usr/bin/env python3
"""
onboard_client.py — 一條指令完整建站

Usage:
  python3 onboard_client.py --name "品牌名" --name-en "Brand" --industry cafe \\
      --template conversion --description "描述" --phone "+853-1234-5678" \\
      --address "澳門XX路" --email "info@brand.com"

  python3 onboard_client.py --name "餐廳名" --name-en "Restaurant" --industry restaurant \\
      --template restaurant --description "餐廳描述" --phone "+853-1234-5678"

  python3 onboard_client.py --list          # 列出所有站點
  python3 onboard_client.py --rebuild SLUG  # 重建現有站點
"""

import os, sys, json, sqlite3, argparse, subprocess, shutil
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

from template_renderer import TEMPLATE_CHOICES, TEMPLATE_LABELS

DB_PATH = os.path.expanduser("~/.openclaw/memory/client_sites.db")
SITES_DIR = os.path.expanduser("~/Documents")
GITHUB_ORG = "YOUR_GITHUB_ORG"

INDUSTRY_DEFAULTS = {
    "cafe": {"schema_type": "CafeOrCoffeeShop", "accent": "#4a7c59", "template": "performance"},
    "restaurant": {"schema_type": "Restaurant", "accent": "#c4553a", "template": "restaurant"},
    "food_delivery": {"schema_type": "Store", "accent": "#8B7240", "template": "conversion"},
    "beauty": {"schema_type": "HealthAndBeautyBusiness", "accent": "#b8628f", "template": "storytelling"},
    "technology": {"schema_type": "Organization", "accent": "#3b82f6", "template": "storytelling"},
    "education": {"schema_type": "EducationalOrganization", "accent": "#6366f1", "template": "conversion"},
    "consulting": {"schema_type": "ProfessionalService", "accent": "#0891b2", "template": "conversion"},
    "fitness": {"schema_type": "SportsActivityLocation", "accent": "#ef4444", "template": "performance"},
    "healthcare": {"schema_type": "MedicalBusiness", "accent": "#14b8a6", "template": "conversion"},
    "retail": {"schema_type": "Store", "accent": "#f59e0b", "template": "performance"},
    "legal": {"schema_type": "LegalService", "accent": "#6b7280", "template": "storytelling"},
}


def slugify(name: str) -> str:
    """Simple slug generator."""
    import re
    s = name.lower().strip()
    s = re.sub(r'[^\w\s-]', '', s)
    s = re.sub(r'[\s_]+', '-', s)
    return s.strip('-')


def create_db_entry(args) -> str:
    """Insert new client into DB. Returns slug."""
    slug = args.slug or slugify(args.name_en or args.name)
    defaults = INDUSTRY_DEFAULTS.get(args.industry, {"schema_type": "Organization", "accent": "#39d2c0", "template": "performance"})
    template = args.template or defaults["template"]
    site_url = f"https://inari-kira-isla.github.io/{slug}"
    local_path = os.path.join(SITES_DIR, slug)

    db = sqlite3.connect(DB_PATH)
    try:
        db.execute("""
            INSERT INTO client_sites (
                slug, business_name, business_name_en, industry, schema_type,
                description, accent_color, template_variant,
                telephone, contact_email, address_street, address_city,
                site_url, local_path, github_repo, status, plan_tier,
                chatbot_enabled, chatbot_character_name, chatbot_character_emoji,
                tracker_enabled
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'generating', 'free',
                      ?, ?, ?, 1)
        """, (
            slug, args.name, args.name_en or args.name, args.industry, defaults["schema_type"],
            args.description or f"{args.name} — 澳門{args.industry}服務",
            args.accent or defaults["accent"], template,
            args.phone or "", args.email or "", args.address or "", "澳門",
            site_url, local_path, f"{GITHUB_ORG}/{slug}",
            1 if args.chatbot else 0,
            args.chatbot_name or "客服助手",
            args.chatbot_emoji or "💬",
        ))
        db.commit()
    except sqlite3.IntegrityError:
        print(f"❌ Slug '{slug}' already exists in DB")
        db.close()
        sys.exit(1)
    db.close()
    return slug


def build_site(slug: str):
    """Render template and write to local directory."""
    from template_renderer import render_site, load_config
    c = load_config(slug)
    local_path = c.get("local_path") or os.path.join(SITES_DIR, slug)

    print(f"\n🏗️  Building site: {slug}")
    variant = c.get("template_variant", "performance")
    print(f"   Template: {variant} ({TEMPLATE_LABELS.get(variant, variant)})")
    print(f"   Output: {local_path}")

    files = render_site(slug)
    os.makedirs(local_path, exist_ok=True)

    # Create articles directory for future article generation
    os.makedirs(os.path.join(local_path, "articles"), exist_ok=True)

    for filename, content in files.items():
        path = os.path.join(local_path, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"   ✅ {filename} ({len(content):,} bytes)")

    return local_path


def init_git(local_path: str, slug: str):
    """Initialize git repo and push to GitHub."""
    print(f"\n📦 Git init: {slug}")

    if not os.path.exists(os.path.join(local_path, ".git")):
        subprocess.run(["git", "init"], cwd=local_path, capture_output=True)
        subprocess.run(["git", "branch", "-M", "main"], cwd=local_path, capture_output=True)

    # Create .gitignore
    gitignore_path = os.path.join(local_path, ".gitignore")
    if not os.path.exists(gitignore_path):
        with open(gitignore_path, "w") as f:
            f.write(".DS_Store\nnode_modules/\n.env\n")

    # Stage and commit
    subprocess.run(["git", "add", "-A"], cwd=local_path, capture_output=True)
    result = subprocess.run(
        ["git", "commit", "-m", f"feat: initial site build via onboard_client.py\n\nTemplate: {slug}\nCo-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"],
        cwd=local_path, capture_output=True, text=True
    )
    if result.returncode == 0:
        print(f"   ✅ Git commit done")
    else:
        print(f"   ⚠️ Git commit: {result.stderr[:100]}")

    # Create GitHub repo + push
    repo_name = f"{GITHUB_ORG}/{slug}"
    print(f"   Creating GitHub repo: {repo_name}")
    result = subprocess.run(
        ["gh", "repo", "create", repo_name, "--public", "--source", local_path, "--push"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print(f"   ✅ Pushed to GitHub")
    elif "already exists" in result.stderr:
        print(f"   ⚠️ Repo exists, pushing...")
        subprocess.run(["git", "remote", "add", "origin", f"https://github.com/{repo_name}.git"],
                       cwd=local_path, capture_output=True)
        subprocess.run(["git", "push", "-u", "origin", "main"], cwd=local_path, capture_output=True)
        print(f"   ✅ Pushed")
    else:
        print(f"   ⚠️ GitHub: {result.stderr[:200]}")


def enable_pages(slug: str):
    """Enable GitHub Pages for the repo."""
    repo = f"{GITHUB_ORG}/{slug}"
    result = subprocess.run(
        ["gh", "api", f"repos/{repo}/pages", "-X", "POST",
         "-f", "build_type=legacy", "-f", "source[branch]=main", "-f", "source[path]=/"],
        capture_output=True, text=True
    )
    if result.returncode == 0 or "already" in result.stderr.lower():
        print(f"   ✅ GitHub Pages enabled")
    else:
        print(f"   ⚠️ Pages: {result.stderr[:100]}")


def update_status(slug: str, status: str):
    db = sqlite3.connect(DB_PATH)
    db.execute("UPDATE client_sites SET status = ?, deployed_at = ? WHERE slug = ?",
               (status, datetime.now().isoformat(), slug))
    db.commit()
    db.close()


def list_sites():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    rows = db.execute("SELECT slug, business_name, industry, template_variant, status, plan_tier FROM client_sites ORDER BY id").fetchall()
    db.close()

    print(f"\n{'Slug':<30} {'Name':<20} {'Industry':<15} {'Template':<14} {'Status':<10} {'Tier'}")
    print("─" * 110)
    for r in rows:
        tpl = r["template_variant"] or "?"
        tpl_label = TEMPLATE_LABELS.get(tpl, tpl)
        print(f"{r['slug']:<30} {r['business_name']:<20} {r['industry']:<15} {tpl_label:<14} {r['status']:<10} {r['plan_tier']}")


def main():
    parser = argparse.ArgumentParser(description="AEO 多客戶一鍵建站 CLI")

    # List mode
    parser.add_argument("--list", action="store_true", help="列出所有站點")
    parser.add_argument("--rebuild", metavar="SLUG", help="重建現有站點")

    # New site
    parser.add_argument("--name", help="品牌名稱 (中文)")
    parser.add_argument("--name-en", help="Brand name (English)")
    parser.add_argument("--slug", help="URL slug (auto-generated if omitted)")
    parser.add_argument("--industry", help="行業", choices=list(INDUSTRY_DEFAULTS.keys()))
    parser.add_argument("--template", choices=TEMPLATE_CHOICES, help="模板策略 / preset")
    parser.add_argument("--description", help="品牌描述")
    parser.add_argument("--phone", help="電話")
    parser.add_argument("--email", help="Email")
    parser.add_argument("--address", help="地址")
    parser.add_argument("--accent", help="主題色 (hex)")

    # Options
    parser.add_argument("--chatbot", action="store_true", help="啟用 AI chatbot")
    parser.add_argument("--chatbot-name", default="客服助手", help="Chatbot 角色名")
    parser.add_argument("--chatbot-emoji", default="💬", help="Chatbot emoji")
    parser.add_argument("--no-git", action="store_true", help="不初始化 git")
    parser.add_argument("--no-deploy", action="store_true", help="不部署到 GitHub Pages")

    args = parser.parse_args()

    if args.list:
        list_sites()
        return

    if args.rebuild:
        slug = args.rebuild
        local_path = build_site(slug)
        update_status(slug, "active")
        print(f"\n✅ Rebuilt: {slug}")
        print(f"   {local_path}")
        return

    if not args.name or not args.industry:
        parser.print_help()
        print("\n❌ --name and --industry are required")
        sys.exit(1)

    # Full onboard flow
    print("═" * 60)
    print("🚀 AEO Multi-Client Onboard")
    print("═" * 60)

    # Step 1: DB entry
    slug = create_db_entry(args)
    print(f"\n1️⃣  DB entry: {slug}")

    # Step 2: Build site
    local_path = build_site(slug)

    # Step 3: Git + Deploy
    if not args.no_git:
        init_git(local_path, slug)
        if not args.no_deploy:
            enable_pages(slug)

    # Step 4: Update status
    update_status(slug, "active")

    # Summary
    site_url = f"https://inari-kira-isla.github.io/{slug}"
    print(f"\n{'═' * 60}")
    print(f"✅ Onboard complete!")
    print(f"   Site: {site_url}")
    print(f"   Local: {local_path}")
    final_template = args.template or INDUSTRY_DEFAULTS.get(args.industry, {}).get('template', 'performance')
    print(f"   Template: {final_template} ({TEMPLATE_LABELS.get(final_template, final_template)})")
    print(f"   Chatbot: {'enabled' if args.chatbot else 'disabled'}")
    print(f"{'═' * 60}")


if __name__ == "__main__":
    main()
