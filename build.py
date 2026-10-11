"""AW Jobs Hub builder (v2).
Pulls free public job feeds (Greenhouse, Lever, Ashby, SmartRecruiters - no API keys), reads each job
description, keeps India roles at every experience level (tagged Fresher / 1-3 / 3-5 / 5+ yrs), tags skills, merges multi-city
duplicates, marks what's new since the last run, and writes jobs.json, index.html and whatsapp_post.txt.
Run: python build.py"""
import json, re, os, sys, html, hashlib, urllib.request, concurrent.futures as cf
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))
NOW = datetime.now(IST); TODAY = NOW.strftime("%Y-%m-%d")
CITIES = ["india","bangalore","bengaluru","pune","hyderabad","mumbai","gurgaon","gurugram","noida","chennai","delhi","kolkata","ahmedabad","kochi","jaipur","coimbatore"]
LEADERSHIP = r"\b(chief|cxo|ceo|cfo|cto|coo|svp|evp|senior vice president|executive vice president|director|head of|head,|head -|country head|general manager|managing director|partner)\b"
SENIOR_HINT = r"\b(senior|sr\.?|staff|principal|lead|manager|architect|expert|iii|iv|vp|avp|vice president)\b"
MID_HINT = r"\b(ii|2|intermediate)\b"
SR_LIMIT = 120
EXCLUDE_LEAD = False
SENIOR = r"\b(senior|sr\.?|staff|principal|lead|leader|manager|director|head|vp|vice president|architect|chief|expert|dgm|gm|agm|supervisor|sme|iii|iv|3|4|account executive|sales engineer|mgr|intermediate)\b"
VERTICALS = [  # order matters: first match wins
 ("Internships", r"\bintern(ship)?\b|trainee|apprentice"),
 ("AI / ML", r"\bai\b|machine learning|\bml\b|nlp|llm|genai|deep learning|computer vision|\bvision\b"),
 ("Data & Analytics", r"statistic|business analy|pricing|optimi[sz]ation|revenue intelligence|\bdata\b|analyst|analytics|business intelligence|\bbi\b|insights?|\bmis\b|reporting|research"),
 ("Healthcare & Life Sciences", r"clinical|medical|scientific affairs|(?<!computer )(?<!applied )scientist|patient|pharmacovigilance|pharmacist|pharmacy|microbiology|life science|biolog|chemist|\bdrug|\behr\b|health records|regulatory affairs|physician|\bgmp\b|batch release"),
 ("HR & People", r"\bhr|human resources|recruit|talent|people|rewards|learning|sourcer"),
 ("Sales & Marketing", r"territory|therapy business|area business|business manager|modern trade|key account|account lead|partner lead|account specialist|marketplace|campaign|account executive|account manag|key account|\bkam\b|relationship manager|revenue manager|category|alliance|corporate development|\bcopy\b|sales|marketing|growth|brand|content|seo|business development|account development|partnership|renewal|\bsdr\b|\bbdr\b|counsel+or"),
 ("Finance & Fintech Ops", r"money laundering|transfer agency|cash management|valuation|investment|fiduciary|banking|trading|incentive compensation|vendor income|remedial|forecasting|payroll|fp&a|balance sheet|billing|intercompany|capital processing|consolidation|deal desk|affordability|financ|accountant|accounting|accounts payable|accounts receivable|audit|tax|treasury|reconcil|risk|credit|collections|payments?|compliance|fraud|wealth|portfolio|kyc|\baml\b|sanctions"),
 ("Supply Chain & Manufacturing", r"supply|planner|planning|procurement|purchase|sourcing|vendor|transportation|logistic|warehouse|last mile|manufactur|production|quality|\bqms\b|inspection|assembl|\bplant\b|operational excellence|material|\bmrp\b|inventory|store planner|facilities"),
 ("Operations & Support", r"warehouse|last mile|logistics|operation manager|order management|area manager|city head|cluster head|workplace|workforce|retail|process trainer|support|customer|success|onboarding|escalation|operations|\bops\b|service|process associate|coordinator|\btse\b|\bcst\b"),
 ("Software & Tech", r"\bsoc\b|silicon|firmware|\bssd\b|middleware|oracle|\bdba\b|database|\bsap\b|workday|information technology|information systems|\bit\b|end user compute|ansible|technolog|application|systems|ecad|electrical|technician|computer scientist|vulnerability|release management|implementation|techno-functional|\bbsa\b|\bsme\b|architect|tech lead|mlops|dataops|c\+\+|hardware|\bcpu\b|adas|applied scien|powertrain|diagnostic|documentation|platform|engineer|developer|software|sde|devops|qa|test|security|cloud|sre|frontend|backend|full ?stack|csirt|technical writer|network|\bsap\b|consultant"),
 ("Product, Design & Strategy", r"project manag|project management|\bpmo\b|agile|transformation|engagement manager|user experience|product|design|strategy|strategist|program|gtm|copywrit|video|creative"),
 ("Legal & Admin", r"counsel|regulatory|legal|contract|controller|procurement|vigilance|forensic|investigation|assistant|administrator"),
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
INDIA_RX = re.compile(r"\b(" + "|".join(CITIES) + r")\b(?!(n|na|polis))", re.I)   # whole words: "India", not "Indiana"/"Indianapolis"
def india(loc): return bool(INDIA_RX.search(loc or ""))

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
WD_PAGES = 6
def wd_req(url, body=None, base=""):
    h = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36",
         "Accept": "application/json", "Accept-Language": "en-US", "Origin": base, "Referer": base}
    if body is not None: h["Content-Type"] = "application/json"
    for attempt in range(2):
        try:
            r = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None, headers=h)
            with urllib.request.urlopen(r, timeout=30) as f: return json.load(f)
        except Exception as e:
            if attempt == 0 and getattr(e, "code", None) in (429, 500, 502, 503): __import__("time").sleep(3); continue
            print("  ! skipped", url.split("?")[0][:90], "-", e); return None
def workday(spec, name):
    """Workday career sites (big MNCs): spec = tenant/wdN/site, e.g. nvidia/wd5/NVIDIAExternalCareerSite"""
    ten, wd, site = spec.split("/"); base = f"https://{ten}.{wd}.myworkdayjobs.com"; api = f"{base}/wday/cxs/{ten}/{site}"
    posts = []
    for page in range(WD_PAGES):
        d = wd_req(f"{api}/jobs", {"appliedFacets": {}, "limit": 20, "offset": page * 20, "searchText": "India"}, base) or {}
        posts += d.get("jobPostings", [])
        if len(d.get("jobPostings", [])) < 20: break
    def detail(p): return (wd_req(api + p["externalPath"], None, base) or {}).get("jobPostingInfo") or {}
    with cf.ThreadPoolExecutor(6) as ex: dets = list(ex.map(detail, posts))
    for p, det in zip(posts, dets):
        if not det: continue
        country = ((det.get("country") or {}).get("descriptor") or "")
        loc = det.get("location") or p.get("locationsText") or ""
        if country == "India" and not india(loc): loc = f"{loc}, India"
        posted = det.get("startDate") or ""
        if not posted:
            m = re.search(r"(\d+)\+? Days? Ago", det.get("postedOn") or p.get("postedOn") or "")
            days = 0 if "Today" in (det.get("postedOn") or "") else int(m.group(1)) if m else 30
            posted = (NOW - timedelta(days=days)).strftime("%Y-%m-%d")
        yield dict(company=name, title=det.get("title") or p["title"], location=loc,
                   url=det.get("externalUrl") or base + "/" + site + p["externalPath"], posted=posted[:10], desc=text(det.get("jobDescription")))
def workable(tok, name):
    lv = {"Entry level":"Fresher","Internship":"Internship"}
    for j in (req(f"https://apply.workable.com/api/v1/widget/accounts/{tok}?details=true") or {}).get("jobs", []):
        loc = ", ".join(x for x in (j.get("city"), j.get("state"), j.get("country")) if x)
        yield dict(company=name, title=j["title"], location=loc, url=j.get("url") or j.get("shortlink"),
                   posted=(j.get("published_on") or j.get("created_at") or "")[:10], fixed_level=lv.get(j.get("experience")),
                   desc=text(j.get("description")) + " " + (j.get("education") or ""))
def smartrecruiters(tok, name):
    keep = {"entry_level":"Fresher","internship":"Internship","associate":None,"mid_senior_level":None,"not_applicable":None}
    if not EXCLUDE_LEAD: keep.update(director=None, executive=None)
    off, picks = 0, []
    while off < 1000:
        d = req(f"https://api.smartrecruiters.com/v1/companies/{tok}/postings?country=in&limit=100&offset={off}") or {}
        for p in d.get("content", []):
            lvl = (p.get("experienceLevel") or {}).get("id")
            if lvl in keep and not (EXCLUDE_LEAD and re.search(LEADERSHIP, p["name"].lower())): picks.append((p, keep[lvl]))
        off += 100
        if off >= d.get("totalFound", 0): break
    picks.sort(key=lambda x: x[0].get("releasedDate") or "", reverse=True)
    picks = picks[:SR_LIMIT]                                  # newest roles first; enough to fill the per-company cap
    with cf.ThreadPoolExecutor(8) as ex: dets = list(ex.map(lambda x: req(x[0]["ref"]) or {}, picks))
    for (p, lvl), det in zip(picks, dets):
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
    nums = [int(m.group(1)) for m in EXP.finditer(desc or "") if int(m.group(1)) <= 30]
    return min(nums) if nums else None
def level(title, yrs, fixed=None):
    t = title.lower()
    if re.search(r"\bintern", t) or fixed == "Internship": return "Internship"
    if yrs is not None: return "Fresher" if yrs <= 1 else f"{yrs}+ yrs"   # the job description wins
    if fixed == "Fresher" or re.search(r"graduate|fresher|new grad|campus|trainee|entry level", t): return "Fresher"
    if re.search(LEADERSHIP, t): return "Leadership"
    if re.search(SENIOR_HINT, t) or re.search(MID_HINT, t): return "Experienced"
    return "Not stated"
def bands(title, yrs, lvl):
    """Experience filter buckets: i=intern, f=fresher (0-2), 1=1-3, 3=3-5, 5=5-10, 10=10-15, 15=15-20, 20=20+ yrs (boundary roles sit in both)."""
    t = title.lower()
    if lvl == "Internship": return ["i"]
    if yrs is not None:
        fixed_map = {0:["f"], 1:["f","1"], 2:["f","1"], 3:["1","3"], 4:["3"], 5:["3","5"], 10:["5","10"], 15:["10","15"], 20:["15","20"]}
        if yrs in fixed_map: return fixed_map[yrs]                # "Freshers" = 0-2 yrs, as before
        return ["5"] if yrs < 10 else ["10"] if yrs < 15 else ["15"] if yrs < 20 else ["20"]
    if re.search(r"\b(chief|cxo|ceo|cfo|cto|coo|svp|evp|senior vice president|executive vice president|managing director|country head)\b", t): return ["15","20"]
    if re.search(LEADERSHIP, t): return ["10","15"]
    if re.search(r"\b(avp|assistant vice president)\b", t): return ["3","5"]   # bank titles: AVP ~ 3-8 yrs
    if re.search(r"\b(vp|vice president)\b", t): return ["5","10"]          # bank VP ~ 6-12 yrs
    if lvl == "Fresher" or re.search(r"\b(junior|jr\.?|associate|trainee|graduate|entry)\b", t): return ["f"]
    if re.search(SENIOR_HINT, t): return ["3","5"]
    if re.search(MID_HINT, t): return ["1","3"]
    return ["f","1"]                                           # experience not stated: usually open to early-career applicants
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
    cfg = json.load(open("companies.json")); st = cfg.get("settings", {}); MAX = st.get("max_years", 30)
    global SR_LIMIT, EXCLUDE_LEAD; SR_LIMIT = int(st.get("max_per_company", 40)) * 3; EXCLUDE_LEAD = bool(st.get("exclude_leadership", False))
    global STALE; STALE = (NOW - timedelta(days=st.get("max_age_days", 90))).strftime("%Y-%m-%d")
    prev = json.load(open("jobs.json")) if os.path.exists("jobs.json") else {"jobs": []}
    first_seen = {norm(j["company"], j["title"]): j.get("firstSeen", TODAY) for j in prev["jobs"]}
    first_seen.update(prev.get("seen", {}))   # remembers roles even when they were hidden by the per-company cap
    RECENT = (NOW - timedelta(days=2)).strftime("%Y-%m-%d")      # a role we start tracking late is "new" only if it was posted recently
    fs = lambda key, default=TODAY: first_seen.get(hk(key)) or first_seen.get(key) or default

    tasks = [(f, t, n) for src, f in (("greenhouse",greenhouse),("lever",lever),("ashby",ashby),("smartrecruiters",smartrecruiters),("workable",workable),("workday",workday))
             for t, n in cfg.get(src, {}).items()]
    raw = []
    with cf.ThreadPoolExecutor(12) as ex:
        for jobs in ex.map(lambda a: list(a[0](a[1], a[2])), tasks): raw += jobs

    merged = {}
    for j in raw:
        j["title"] = clean_title(j["title"]); ok = india(j["location"]); j["location"] = city_names(clean_loc(j["location"])); t = j["title"].lower()
        if not ok or (EXCLUDE_LEAD and re.search(LEADERSHIP, t)): continue
        if "default template" in t: continue                  # placeholder postings
        if j["posted"] and j["posted"] < STALE: continue          # very old listings rarely respond
        m = TITLE_EXP.search(t); yrs = min_years(j["desc"])
        if (m and int(m.group(1)) > MAX) or (yrs is not None and yrs > MAX): continue
        key = norm(j["company"], j["title"])
        if key in merged:                                   # same role in several cities -> one card
            merged[key]["location"] = " / ".join(dict.fromkeys(merged[key]["location"].split(" / ") + j["location"].split(" / ")))
            continue
        merged[key] = dict(company=j["company"], title=j["title"], location=j["location"], url=j["url"], posted=j["posted"],
                           vertical=vertical(j["title"]), level=(lv := level(j["title"], yrs, j.get("fixed_level"))), band=bands(j["title"], yrs, lv),
                           years=yrs, tags=skills(j["title"], j["desc"]), degrees=degrees(j["desc"]), batch=batches(j["title"], j["desc"]), source="auto", firstSeen=fs(key, TODAY if not j["posted"] or j["posted"] >= RECENT else j["posted"]))
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
                        "band": m.get("band") or bands(m["title"], None, m.get("level") or level(m["title"], None)),
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
        ed = max(0, int(st.get("early_access_days", 7)))
        cut = (NOW - timedelta(days=ed - 1)).strftime("%Y-%m-%d") if ed else "9999-99-99"
        # A role is "new" by the company's own posting date; first-seen date only when the company doesn't publish one
        fresh = lambda j: j["posted"] or (j["firstSeen"] if has_history else "")
        early = [j for j in auto_all if fresh(j) and fresh(j) >= cut]
        eids = {id(j) for j in early}; public = [j for j in auto_all if id(j) not in eids]
        n = st.get("preview_per_track", 5); per = {}; preview = []; by_track = {}
        for j in public:
            per[j["vertical"]] = per.get(j["vertical"], 0) + 1
            by_track[j["vertical"]] = by_track.get(j["vertical"], 0) + 1
            if per[j["vertical"]] <= n: preview.append(j)
        # Application links live in their own protected row: AW students read it; free students open one at a time (daily limit)
        nolink = lambda L: [{**j, "url": ""} for j in L]
        push_supabase(st["supabase_url"], [
            {"id": "full", "data": {"updated": data["updated"], "today": TODAY, "jobs": nolink(public)}},
            {"id": "early", "data": {"updated": data["updated"], "today": TODAY, "jobs": nolink(early)}},
            {"id": "links", "data": {"public": {j["id"]: j["url"] for j in public}, "early": {j["id"]: j["url"] for j in early},
                                     "free_daily_applies": int(st.get("free_daily_applies", 3))}}])
        picks_n = supabase_count(st["supabase_url"], "aw_picks", f"active=is.true&added=gte.{(NOW - timedelta(days=st.get('curated_expiry_days', 30))).strftime('%Y-%m-%d')}")
        week_ago = (NOW - timedelta(days=7)).strftime("%Y-%m-%d")
        preview = [{**j, "url": ""} for j in preview]
        band_counts = {}
        for j in public:
            for b in j.get("band", []): band_counts[b] = band_counts.get(b, 0) + 1
        band_counts["pro"] = sum(1 for j in public if set(j.get("band", [])) & {"1", "3", "5", "10", "15", "20"})
        data["bandCounts"] = band_counts
        early_by_track = {}
        for j in early: early_by_track[j["vertical"]] = early_by_track.get(j["vertical"], 0) + 1
        data["earlyByTrack"] = early_by_track
        data.update(jobs=preview, gated=True, total=len(public), byTrack=by_track, earlyCount=len(early), earlyDays=ed, picksCount=picks_n,
                    freeApplies=int(st.get("free_daily_applies", 3)),
                    stats={"roles": len(public), "cos": len({j["company"] for j in public}),
                           "week": sum(1 for j in public if j["posted"] and j["posted"] >= week_ago),
                           "weekAll": sum(1 for j in public + early if (j["posted"] or j["firstSeen"]) >= week_ago)})
        went_public = (NOW - timedelta(days=ed)).strftime("%Y-%m-%d")
        club_fresh = [j for j in public if fresh(j) == went_public]   # early-access roles reach the AW Club when they go public
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
    is_early_career = lambda j: bool(set(j.get("band", ["f"])) & {"f", "i"})
    is_pro = lambda j: bool(set(j.get("band", [])) & {"1", "3", "5", "10", "15", "20"}) and not set(j.get("band", [])) & {"f", "i"}
    write_whatsapp([j for j in club_fresh if is_early_career(j)], [j for j in club_all if is_early_career(j)],
                   sum(1 for j in club_all if is_early_career(j)), hub, locals().get("link"))
    write_whatsapp([j for j in club_fresh if is_pro(j)], [j for j in club_all if is_pro(j)],
                   sum(1 for j in club_all if is_pro(j)), hub.rstrip("/") + "/#exp=pro" if hub else hub, locals().get("link"),
                   file="whatsapp_post_experienced.txt", title="💼 *EXPERIENCED ROLES (1+ YEARS)* 💼", what="roles for working professionals")
    print(f"Built {len(jobs)} roles ({new_today} new) from {len(raw)} scanned")

def write_whatsapp(fresh, all_jobs, total, hub, link=None, file="whatsapp_post.txt", title="🌟 *EXCITING JOB OPPORTUNITIES* 🌟", what="fresher roles"):
    # AW Club post: only roles that are new to the public board today (newest roles as a fallback)
    pool = fresh or sorted(all_jobs, key=lambda j: j.get("posted") or "", reverse=True)
    pri = {"Data & Analytics":0,"Finance & Fintech Ops":1,"Internships":2,"AI / ML":3,"Operations & Support":4}
    pool = sorted(pool, key=lambda j: (j["source"] != "curated", j["level"] == "Not stated", pri.get(j["vertical"], 9)))[:6]
    lines = [title, f"📅 {NOW.strftime('%d %b %Y')}", ""]
    for j in pool:
        lines += ["━━━━━━━━━━", f"💼 *{j['company'].upper()}*", f"*Role:* {j['title']}" + (f" ({' / '.join(j['tags'][:3])})" if j.get("tags") else ""),
                  f"🔰 *Experience:* {j['level'] if j['level'] != 'Not stated' else 'Not specified'}", f"📍 *Location:* {j['location']}", f"📌 *Apply 👇*" if not link else "📌 *Details & apply (free sign-in) 👇*", link(j) if link else j["url"], ""]
    lines += ["━━━━━━━━━━", f"🔎 *See all {total} {what}, sorted by career track:*", hub, "",
              "⏳ Openings can close without notice — apply early!", "💬 *All the best! You've got this* 💪🎯", "",
              "Join The AW Club for daily updates: https://chat.whatsapp.com/DPtoJSrsLSu0IbDagfuJz5"]
    open(file, "w", encoding="utf-8").write("\n".join(lines))

if __name__ == "__main__": main()
