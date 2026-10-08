"""AW Jobs Hub builder (v2).
Pulls free public job feeds (Greenhouse, Lever, Ashby, SmartRecruiters - no API keys), reads each job
description, keeps India roles needing <= max_years experience, tags skills, merges multi-city
duplicates, marks what's new since the last run, and writes jobs.json, index.html and whatsapp_post.txt.
Run: python build.py"""
import json, re, os, sys, html, hashlib, urllib.request, concurrent.futures as cf
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))
NOW = datetime.now(IST); TODAY = NOW.strftime("%Y-%m-%d")
CITIES = ["india","bangalore","bengaluru","pune","hyderabad","mumbai","gurgaon","gurugram","noida","chennai","delhi","kolkata","ahmedabad","kochi","jaipur","coimbatore"]
SENIOR = r"\b(senior|sr\.?|staff|principal|lead|leader|manager|director|head|vp|vice president|architect|chief|expert|dgm|gm|agm|supervisor|sme|iii|iv|3|4|account executive|sales engineer|mgr|intermediate)\b"
VERTICALS = [  # order matters: first match wins
 ("Internships", r"\bintern(ship)?\b|trainee|apprentice"),
 ("AI / ML", r"\bai\b|machine learning|\bml\b|nlp|llm|genai|deep learning|computer vision|\bvision\b"),
 ("Data & Analytics", r"\bdata\b|analyst|analytics|business intelligence|\bbi\b|insights?|\bmis\b|reporting|research"),
 ("HR & People", r"\bhr|human resources|recruit|talent|people|rewards|learning|sourcer"),
 ("Sales & Marketing", r"sales|marketing|growth|brand|content|seo|business development|account development|partnership|renewal|\bsdr\b|\bbdr\b|counsel+or"),
 ("Finance & Fintech Ops", r"financ|accountant|accounting|accounts payable|accounts receivable|audit|tax|treasury|reconcil|risk|credit|collections|payments?|compliance|fraud|wealth|portfolio|kyc|\baml\b|sanctions"),
 ("Operations & Support", r"support|customer|success|onboarding|escalation|operations|\bops\b|service|process associate|coordinator|\btse\b|\bcst\b"),
 ("Software & Tech", r"engineer|developer|software|sde|devops|qa|test|security|cloud|sre|frontend|backend|full ?stack|csirt|technical writer|network|\bsap\b|consultant"),
 ("Product, Design & Strategy", r"product|design|strategy|strategist|program|gtm|copywrit|video|creative"),
 ("Legal & Admin", r"legal|contract|controller|procurement|vigilance|forensic|investigation|assistant|administrator"),
]
SKILLS = [("Excel",r"\bexcel\b|spreadsheet"),("SQL",r"\bsql\b"),("Python",r"\bpython\b"),("Power BI",r"power ?bi"),
 ("Tableau",r"tableau"),("Statistics",r"statistic"),("Machine Learning",r"machine learning|\bml\b"),("GenAI",r"genai|generative ai|\bllm"),
 ("Java",r"\bjava\b"),("JavaScript",r"javascript|typescript|react|node\.?js"),("Cloud",r"\baws\b|azure|\bgcp\b|google cloud"),
 ("Salesforce",r"salesforce"),("SAP",r"\bsap\b"),
 ("Financial Analysis",r"financial (?:model|analysis|statement|planning)|valuation|fp&a|budgeting|forecasting"),
 ("Accounting",r"\baccounting\b|tally|\bgst\b|tds|reconciliation|bookkeeping|ledger"),
 ("Digital Marketing",r"\bseo\b|\bsem\b|google ads|meta ads|social media marketing|digital marketing|performance marketing"),
 ("Communication",r"(?:excellent|strong|good) (?:verbal |written )?communication")]
EXP = re.compile(r"(\d{1,2})\s*(?:\+|plus)?\s*(?:(?:-|–|to)\s*\d{1,2})?\s*\+?\s*(?:years?|yrs)(?!\s*(?:ahead|old|ago|of age|of history|in business|warranty))", re.I)
TITLE_EXP = re.compile(r"(\d+)\s*(?:\+|-|to|–)?\s*\d*\s*(?:yrs|years)", re.I)

def req(url, body=None):
    try:
        r = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                                   headers={"User-Agent":"Mozilla/5.0 AWJobsHub","Content-Type":"application/json"})
        with urllib.request.urlopen(r, timeout=30) as f: return json.load(f)
    except Exception as e:
        print("  ! skipped", url.split("?")[0], "-", e); return None
def text(h): return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(html.unescape(h or ""))))
def india(loc): return any(k in (loc or "").lower() for k in CITIES)

# ---- sources: each yields dicts with company,title,location,url,posted,desc,fixed_level ----
def greenhouse(tok, name):
    for j in (req(f"https://boards-api.greenhouse.io/v1/boards/{tok}/jobs?content=true") or {}).get("jobs", []):
        yield dict(company=name, title=j["title"], location=(j.get("location") or {}).get("name",""), url=j["absolute_url"],
                   posted=(j.get("first_published") or j.get("updated_at") or "")[:10], desc=text(j.get("content")))
def lever(tok, name):
    d = req(f"https://api.lever.co/v0/postings/{tok}?mode=json")
    for j in d if isinstance(d, list) else []:
        c = j.get("categories", {}); ts = j.get("createdAt")
        yield dict(company=name, title=j["text"], location=c.get("location") or ", ".join(c.get("allLocations") or []),
                   url=j["hostedUrl"], posted=datetime.fromtimestamp(ts/1000, IST).strftime("%Y-%m-%d") if ts else "",
                   desc=(j.get("descriptionPlain") or "") + " " + " ".join(text(l.get("content")) for l in j.get("lists", [])))
def ashby(tok, name):
    for j in (req(f"https://api.ashbyhq.com/posting-api/job-board/{tok}") or {}).get("jobs", []):
        locs = [j.get("location") or ""] + [s.get("location","") for s in j.get("secondaryLocations") or []]
        yield dict(company=name, title=j["title"], location=" / ".join(x for x in locs if x), url=j["jobUrl"],
                   posted=(j.get("publishedAt") or "")[:10], desc=j.get("descriptionPlain") or "")
def workable(tok, name):
    lv = {"Entry level":"Fresher","Internship":"Internship"}
    for j in (req(f"https://apply.workable.com/api/v1/widget/accounts/{tok}?details=true") or {}).get("jobs", []):
        loc = ", ".join(x for x in (j.get("city"), j.get("state"), j.get("country")) if x)
        yield dict(company=name, title=j["title"], location=loc, url=j.get("url") or j.get("shortlink"),
                   posted=(j.get("published_on") or j.get("created_at") or "")[:10], fixed_level=lv.get(j.get("experience")),
                   desc=text(j.get("description")) + " " + (j.get("education") or ""))
def smartrecruiters(tok, name):
    keep = {"entry_level":"Fresher","internship":"Internship","associate":None,"not_applicable":None}
    off, picks = 0, []
    while off < 1000:
        d = req(f"https://api.smartrecruiters.com/v1/companies/{tok}/postings?country=in&limit=100&offset={off}") or {}
        for p in d.get("content", []):
            lvl = (p.get("experienceLevel") or {}).get("id")
            if lvl in keep and not re.search(SENIOR, p["name"].lower()): picks.append((p, keep[lvl]))  # skip senior titles before fetching details
        off += 100
        if off >= d.get("totalFound", 0): break
    for p, lvl in picks:
        det = req(p["ref"]) or {}
        secs = (det.get("jobAd") or {}).get("sections") or {}
        yield dict(company=name, title=p["name"], location=(p.get("location") or {}).get("fullLocation",""),
                   url=det.get("postingUrl") or f"https://jobs.smartrecruiters.com/{tok}/{p['id']}",
                   posted=(p.get("releasedDate") or "")[:10], fixed_level=lvl,
                   desc=text(" ".join((secs.get(k) or {}).get("text","") for k in ("jobDescription","qualifications"))))

DEGREES = [("Any graduate", r"any graduate|any degree|graduate in any|degree in any|any discipline|any stream", 0),
 ("BCom", r"\bb\.?\s?com\b|bachelor'?s? (?:degree )?(?:of|in) commerce|commerce graduate|degree in commerce|degree in accounting|accounting degree|\bm\.?\s?com\b", 0),
 ("BBA", r"\bbba\b|\bbbm\b|business administration|management studies", 0),
 ("MBA", r"\bmba\b|\bpgdm\b|post ?graduate diploma in management", 0),
 ("BTech/BE", r"\bb\.?\s?tech\b|\bbca\b|\bmca\b|computer science|bachelor of engineering|degree in engineering|engineering degree|information technology", 0),
 ("BTech/BE", r"\bB\.E\b|\bBE\b(?= ?[/,(]| in)", 1),
 ("BSc/Stats/Econ", r"\bb\.?\s?sc\b|\bm\.?\s?sc\b|statistics|mathematics|economics", 0),
 ("CA/CMA", r"chartered accountant|\bCA\b|\bCMA\b|\bACCA\b|\bCFA\b", 1)]
BATCH = [re.compile(r"\b(202[4-8])\s*(?:[/&-]\s*20\d\d\s*)?(?:batch|pass[- ]?outs?|graduates?|graduating|grads?)\b", re.I),
         re.compile(r"(?:batch|class|graduating|graduation|pass[- ]?out)(?: year)?(?: of| in|:)?\s*(202[4-8])", re.I)]
def degrees(desc):
    d = desc or ""; out = []
    for name, pat, case in DEGREES:
        if name not in out and re.search(pat, d if case else d.lower()): out.append(name)
    return out
def batches(title, desc):
    t = (title or "") + " " + (desc or "")
    return sorted({m.group(1) for rx in BATCH for m in rx.finditer(t)})
def vertical(title):
    t = title.lower()
    for name, pat in VERTICALS:
        if re.search(pat, t): return name
    return "Other"
def min_years(desc):
    nums = [int(m.group(1)) for m in EXP.finditer(desc or "") if int(m.group(1)) <= 15]
    return min(nums) if nums else None
def level(title, yrs, fixed=None):
    t = title.lower()
    if re.search(r"\bintern", t) or fixed == "Internship": return "Internship"
    if yrs is not None: return "Fresher" if yrs <= 1 else f"{yrs}+ yrs"   # the job description wins
    if fixed == "Fresher" or re.search(r"graduate|fresher|new grad|campus|trainee|entry level", t): return "Fresher"
    return "Not stated"
def clean_title(t):
    t = re.sub(r"^(IN|BGSW|RBEI|RBIC)_", "", " ".join(t.split())).replace("_", " ").strip()
    return t[0].upper() + t[1:] if t.islower() else t
def clean_loc(loc):
    parts = []
    for p in re.split(r"\s*[;/|]\s*", loc or ""):
        p = ", ".join((x.strip().title() if x.strip().islower() else x.strip()) for x in p.split(",") if x.strip())
        if p and p not in parts: parts.append(p)
    return " / ".join(parts)
CANON = [("Bengaluru",r"bangalore|bengaluru"),("Hyderabad",r"hyderabad"),("Pune",r"pune"),("Mumbai",r"mumbai|navi mumbai|thane"),
 ("Gurugram",r"gurgaon|gurugram"),("Noida",r"noida"),("Delhi",r"new delhi|\bdelhi\b"),("Chennai",r"chennai"),("Kolkata",r"kolkata"),
 ("Ahmedabad",r"ahmedabad"),("Coimbatore",r"coimbatore"),("Kochi",r"kochi|cochin"),("Jaipur",r"jaipur")]
def city_names(loc):
    l = (loc or "").lower(); out = [c for c, p in CANON if re.search(p, l)]
    if "remote" in l: out.append("Remote")
    return " / ".join(out) if out else ("India" if "india" in l else loc)
def norm(company, title): return company + "|" + re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()
def skills(title, desc):
    t = (title + " " + (desc or "")).lower()
    return [s for s, pat in SKILLS if re.search(pat, t)][:6]

def hk(k): return hashlib.sha1(k.encode()).hexdigest()[:16]   # role ids stored as hashes, so jobs.json doesn't list the full board

def push_supabase(base, rows):
    """Upload the full board to Supabase (only signed-in students can read it there)."""
    key = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
    if not key:
        print("::warning::SUPABASE_SERVICE_KEY secret is missing - the full board was not uploaded"); return False
    h = {"apikey": key, "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates,return=minimal"}
    if key.startswith("eyJ"): h["Authorization"] = "Bearer " + key
    try:
        urllib.request.urlopen(urllib.request.Request(base.rstrip("/") + "/rest/v1/snapshots?on_conflict=id",
            data=json.dumps(rows, ensure_ascii=False).encode(), headers=h, method="POST"), timeout=60)
        print("  uploaded full board to Supabase"); return True
    except Exception as e:
        body = e.read().decode()[:300] if hasattr(e, "read") else ""
        print(f"::warning::Supabase upload failed: {e} {body}"); return False

def supabase_count(base, table, filt):
    key = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
    if not key: return 0
    h = {"apikey": key, "Prefer": "count=exact", "Range": "0-0"}
    if key.startswith("eyJ"): h["Authorization"] = "Bearer " + key
    try:
        r = urllib.request.urlopen(urllib.request.Request(f"{base.rstrip('/')}/rest/v1/{table}?select=id&{filt}", headers=h), timeout=30)
        return int((r.headers.get("Content-Range") or "*/0").split("/")[-1] or 0)
    except Exception as e:
        print("::warning::could not count", table, e); return 0

def main():
    cfg = json.load(open("companies.json")); st = cfg.get("settings", {}); MAX = st.get("max_years", 3)
    global STALE; STALE = (NOW - timedelta(days=st.get("max_age_days", 90))).strftime("%Y-%m-%d")
    prev = json.load(open("jobs.json")) if os.path.exists("jobs.json") else {"jobs": []}
    first_seen = {norm(j["company"], j["title"]): j.get("firstSeen", TODAY) for j in prev["jobs"]}
    first_seen.update(prev.get("seen", {}))   # remembers roles even when they were hidden by the per-company cap
    fs = lambda key, default=TODAY: first_seen.get(hk(key)) or first_seen.get(key) or default

    tasks = [(f, t, n) for src, f in (("greenhouse",greenhouse),("lever",lever),("ashby",ashby),("smartrecruiters",smartrecruiters),("workable",workable))
             for t, n in cfg.get(src, {}).items()]
    raw = []
    with cf.ThreadPoolExecutor(12) as ex:
        for jobs in ex.map(lambda a: list(a[0](a[1], a[2])), tasks): raw += jobs

    merged = {}
    for j in raw:
        j["title"] = clean_title(j["title"]); ok = india(j["location"]); j["location"] = city_names(clean_loc(j["location"])); t = j["title"].lower()
        if not ok or re.search(SENIOR, t): continue
        if j["posted"] and j["posted"] < STALE: continue          # very old listings rarely respond
        m = TITLE_EXP.search(t); yrs = min_years(j["desc"])
        if (m and int(m.group(1)) > MAX) or (yrs is not None and yrs > MAX): continue
        key = norm(j["company"], j["title"])
        if key in merged:                                   # same role in several cities -> one card
            merged[key]["location"] = " / ".join(dict.fromkeys(merged[key]["location"].split(" / ") + j["location"].split(" / ")))
            continue
        merged[key] = dict(company=j["company"], title=j["title"], location=j["location"], url=j["url"], posted=j["posted"],
                           vertical=vertical(j["title"]), level=level(j["title"], yrs, j.get("fixed_level")),
                           years=yrs, tags=skills(j["title"], j["desc"]), degrees=degrees(j["desc"]), batch=batches(j["title"], j["desc"]), source="auto", firstSeen=fs(key))
    jobs = list(merged.values())

    # hand-picked roles: expire after N days; drop if the link is gone (404/410)
    cut = (NOW - timedelta(days=st.get("curated_expiry_days", 30))).strftime("%Y-%m-%d"); curated = []
    for m in json.load(open("manual_jobs.json")):
        if m.get("added", TODAY) < cut: print("  - expired pick:", m["title"]); continue
        try: urllib.request.urlopen(urllib.request.Request(m["url"], headers={"User-Agent":"Mozilla/5.0"}), timeout=20)
        except Exception as e:
            if getattr(e, "code", None) in (404, 410): print("  - closed pick:", m["title"]); continue
        key = norm(m["company"], m["title"])
        curated.append({**m, "vertical": m.get("vertical") or vertical(m["title"]), "posted": m.get("posted", ""),
                        "source": "curated", "firstSeen": fs(key, m.get("added", TODAY))})
        merged.pop(key, None)
    urls = {c["url"] for c in curated}; cap = st.get("max_per_company", 40); per = {}; auto = []
    for j in sorted([j for j in merged.values() if j["url"] not in urls], key=lambda j: (j["level"] != "Not stated", j["firstSeen"], j["posted"]), reverse=True):
        per[j["company"]] = per.get(j["company"], 0) + 1
        if per[j["company"]] <= cap: auto.append(j)
    jobs = curated + sorted(auto, key=lambda j: (j["firstSeen"], j["posted"]), reverse=True)

    # safety net: if feeds broke and we lost more than half the roles, keep yesterday's board
    prev_n = prev.get("count") or len(prev["jobs"])
    if prev_n and len(jobs) < 0.5 * prev_n:
        sys.exit(f"Only {len(jobs)} roles vs {prev_n} last time - keeping the old board. Check the feeds.")

    has_history = any(j.get("firstSeen", TODAY) < TODAY for j in prev["jobs"]) or any(v < TODAY for v in prev.get("seen", {}).values())
    new_today = sum(1 for j in jobs if j["firstSeen"] == TODAY) if has_history else 0
    seen = {hk(k): v["firstSeen"] for k, v in merged.items()}
    seen.update({hk(norm(c["company"], c["title"])): c["firstSeen"] for c in curated})
    data = {"updated": NOW.strftime("%d %b %Y, %I:%M %p IST"), "today": TODAY, "count": len(jobs), "newToday": new_today, "jobs": jobs, "seen": seen,
            "config": {k: st.get(k, "") for k in ("aw_url", "ga4_id", "club_url", "supabase_url", "supabase_anon_key", "priority_group_url")}}

    # Sign-in mode: public page = preview; free accounts = full board; AW students = full + early access + picks + prep kits
    hub = st.get("hub_url", "")
    if st.get("supabase_url") and st.get("supabase_anon_key"):
        if any(j["source"] == "curated" for j in jobs):
            print("::notice::Sign-in mode: AW Picks now live in Supabase (table aw_picks). Roles in manual_jobs.json are not shown.")
        auto_all = [j for j in jobs if j["source"] == "auto"]
        for j in auto_all: j["id"] = hk(j["url"])
        ed = max(0, int(st.get("early_access_days", 2)))
        cut = (NOW - timedelta(days=ed - 1)).strftime("%Y-%m-%d") if ed else "9999-99-99"
        early = [j for j in auto_all if has_history and j["firstSeen"] >= cut]
        eids = {id(j) for j in early}; public = [j for j in auto_all if id(j) not in eids]
        n = st.get("preview_per_track", 5); per = {}; preview = []; by_track = {}
        for j in public:
            per[j["vertical"]] = per.get(j["vertical"], 0) + 1
            by_track[j["vertical"]] = by_track.get(j["vertical"], 0) + 1
            if per[j["vertical"]] <= n: preview.append(j)
        push_supabase(st["supabase_url"], [
            {"id": "full", "data": {"updated": data["updated"], "today": TODAY, "jobs": public}},
            {"id": "early", "data": {"updated": data["updated"], "today": TODAY, "jobs": early}}])
        picks_n = supabase_count(st["supabase_url"], "aw_picks", f"active=is.true&added=gte.{(NOW - timedelta(days=st.get('curated_expiry_days', 30))).strftime('%Y-%m-%d')}")
        week_ago = (NOW - timedelta(days=7)).strftime("%Y-%m-%d")
        preview = [{**j, "url": ""} for j in preview]
        early_by_track = {}
        for j in early: early_by_track[j["vertical"]] = early_by_track.get(j["vertical"], 0) + 1
        data["earlyByTrack"] = early_by_track
        data.update(jobs=preview, gated=True, total=len(public), byTrack=by_track, earlyCount=len(early), earlyDays=ed, picksCount=picks_n,
                    stats={"roles": len(public), "cos": len({j["company"] for j in public}),
                           "week": sum(1 for j in public if j["posted"] and j["posted"] >= week_ago),
                           "weekAll": sum(1 for j in public + early if (j["posted"] or j["firstSeen"]) >= week_ago)})
        went_public = (NOW - timedelta(days=ed)).strftime("%Y-%m-%d")
        club_fresh = [j for j in public if has_history and j["firstSeen"] == went_public]   # early-access roles reach the AW Club when they go public
        club_all, club_total = public, len(public)
        if st.get("club_post_links", "hub") == "hub":          # AW Club post links to the board, so every applicant signs up
            link = lambda j: f"{hub.rstrip('/')}/#job={j['id']}"
    else:
        club_fresh = [j for j in jobs if (j["source"] == "curated" and j.get("added") == TODAY) or (has_history and j["source"] == "auto" and j["firstSeen"] == TODAY)]
        club_all, club_total = [j for j in jobs if j["source"] == "auto"], len(jobs)
    json.dump(data, open("jobs.json", "w"), ensure_ascii=False, indent=1)
    if os.path.exists("template.html"):
        blob = json.dumps({k: v for k, v in data.items() if k != "seen"}, ensure_ascii=False).replace("</", "<\\/")
        open("index.html", "w", encoding="utf-8").write(open("template.html", encoding="utf-8").read().replace("/*__JOBS_DATA__*/null", blob))
    write_whatsapp(club_fresh, club_all, club_total, hub, locals().get("link"))
    print(f"Built {len(jobs)} roles ({new_today} new) from {len(raw)} scanned")

def write_whatsapp(fresh, all_jobs, total, hub, link=None):
    # AW Club post: only roles that are new to the public board today (newest roles as a fallback)
    pool = fresh or sorted(all_jobs, key=lambda j: j.get("posted") or "", reverse=True)
    pri = {"Data & Analytics":0,"Finance & Fintech Ops":1,"Internships":2,"AI / ML":3,"Operations & Support":4}
    pool = sorted(pool, key=lambda j: (j["source"] != "curated", j["level"] == "Not stated", pri.get(j["vertical"], 9)))[:6]
    lines = ["🌟 *EXCITING JOB OPPORTUNITIES* 🌟", f"📅 {NOW.strftime('%d %b %Y')}", ""]
    for j in pool:
        lines += ["━━━━━━━━━━", f"💼 *{j['company'].upper()}*", f"*Role:* {j['title']}" + (f" ({' / '.join(j['tags'][:3])})" if j.get("tags") else ""),
                  f"🔰 *Experience:* {j['level'] if j['level'] != 'Not stated' else 'Not specified'}", f"📍 *Location:* {j['location']}", f"📌 *Apply 👇*" if not link else "📌 *Details & apply (free sign-in) 👇*", link(j) if link else j["url"], ""]
    lines += ["━━━━━━━━━━", f"🔎 *See all {total} roles, sorted by career track:*", hub, "",
              "⏳ Openings can close without notice — apply early!", "💬 *All the best! You've got this* 💪🎯", "",
              "Join The AW Club for daily updates: https://chat.whatsapp.com/DPtoJSrsLSu0IbDagfuJz5"]
    open("whatsapp_post.txt", "w", encoding="utf-8").write("\n".join(lines))

if __name__ == "__main__": main()
