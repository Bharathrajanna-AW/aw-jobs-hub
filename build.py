"""AW Jobs Hub builder (v2).
Pulls free public job feeds (Greenhouse, Lever, Ashby, SmartRecruiters - no API keys), reads each job
description, keeps India roles at every experience level (tagged Fresher / 1-3 / 3-5 / 5+ yrs), tags skills, merges multi-city
duplicates, marks what's new since the last run, and writes jobs.json, index.html and whatsapp_post.txt.
Run: python build.py"""
import json, re, os, sys, html, hashlib, time, random, threading, urllib.request, concurrent.futures as cf
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
 # second pass: only reached when nothing above matched (these used to land in "Other")
 ("Operations & Support", r"trust (?:&|and) safety|content moderat|new associate|supervisor|\bshift\b|in-?charge|field (?:service|technician|engineer|operator)|machinist|operator|maintenance|site (?:lead|manager|head)|service delivery|team member|back office|front office|client service|incident|helpdesk|help desk|reservation|ticketing|safety executive|\bdriver\b"),
 ("Finance & Fintech Ops", r"\bcash\b|collateral|settlement|lending|mortgage|\btrade\b|claims|equity|asset (?:management|servic)|custody|\bfunds?\b|securities|derivatives|underwrit|actuar|insurance|\bloans?\b|clearing|brokerage|middle office|\bcfo\b|controllership|collection|stock plan|equity plan"),
 ("Healthcare & Life Sciences", r"\bpv\b|pharmacovig|scientific|\bstudy\b|\bheva\b|health economics|medical writ|safety (?:physician|scientist|data)|biostat|\blab\b|laborator|healthcare|hospital|nurse|dental|veterin|\bcra\b|central monitor|\bsite monitor"),
 ("Software & Tech", r"\bjava\b|layout|\basic\b|verification|\bhbm\b|\beng\b|\bmts\b|cyber|identity|detection|automation|scrum master|technical|\btech\b|\bitao?\b|devsecops|\bvlsi\b|\brtl\b|embedded|mainframe|salesforce|servicenow|\berp\b|\bcrm\b|digital twin|\bdigital\b|access management|\.net\b|algorithm|deployment|development team|functional safety|\bfusa\b"),
 ("Supply Chain & Manufacturing", r"buyer|distribution|\bocean\b|freight|\bproc\b|sc&o|\bscm\b|commodity|machining|tooling|\bcnc\b|welding|mechanical|\bplant\b|shipping|customs|import|export|supplier|welder|wiper|tool ?maker|press tool|fitter|electrician"),
 ("Sales & Marketing", r"account|\brep\b|representative|commercial|\bmarket|communications|community|client partner|\brelations\b|advocacy|public relations|\bevents?\b|sponsor"),
 ("HR & People", r"benefits|employee|organi[sz]ational|engagement|culture|\bdei\b|diversity|compensation|workforce"),
 ("Product, Design & Strategy", r"business management|chief of staff|consult|advis|strateg|\bchange\b|governance|excellence|project|enablement|solutions?\b|delivery|initiative|writer|writing|editor|art director|government affairs|competitive intelligence|public policy"),
 ("Legal & Admin", r"\badmin|office|secretar|receptionist|front desk|facilit|travel desk|executive assistant|\bcontrols?\b|\bsme\b|subject matter expert"),
]
SKILLS = [  # (skill, words that show it, group shown in the "My skills" picker)
 ("Excel",r"\bexcel\b(?! (?:in|at|as|within)\b)|spreadsheet|vlookup|pivot table","Data & AI"),("SQL",r"\bsql\b|mysql|postgres|pl/sql|t-sql","Data & AI"),
 ("Python",r"\bpython\b|pandas|numpy","Data & AI"),("R",r"\br programming|\brstudio\b|\bin r\b|python,? (?:and |or )?r\b|\br,? (?:and |or )?python","Data & AI"),
 ("Power BI",r"power ?bi|\bdax\b","Data & AI"),("Tableau",r"tableau","Data & AI"),("Data Visualization",r"data visuali[sz]|dashboard (?:development|design|creation)|build(?:ing)? (?:interactive )?dashboards|looker|qlik","Data & AI"),
 ("Statistics",r"statistic|hypothesis test|regression (?:analysis|model)|a/b test","Data & AI"),("Machine Learning",r"machine learning|\bml\b|deep learning|scikit|tensorflow|pytorch","Data & AI"),
 ("GenAI",r"genai|generative ai|\bllms?\b|prompt engineering|\brag\b|langchain","Data & AI"),
 ("Data Engineering",r"\bspark\b|hadoop|databricks|airflow|kafka|\betl\b|data pipeline|snowflake|bigquery|redshift|\bdbt\b|data warehous","Data & AI"),
 ("Java",r"\bjava\b|spring boot","Software"),("JavaScript",r"javascript|typescript|\breact(?:\.?js)?\b|node\.?js|\bangular\b|\bvue\b","Software"),
 ("C / C++",r"\bc\+\+|\bc programming|embedded c\b|\bc/c\+\+","Software"),("C# / .NET",r"\bc#|\.net\b|asp\.net","Software"),("Go",r"\bgolang\b","Software"),
 ("Web Development",r"\bhtml|\bcss\b|front-?end|web development","Software"),("Mobile Apps",r"android|\bios\b|kotlin|swiftui|swift (?:developer|programming)|flutter|react native","Software"),
 ("APIs & Microservices",r"rest(?:ful)? api|microservice|graphql|api (?:development|design)","Software"),
 ("Cloud",r"\baws\b|azure|\bgcp\b|google cloud","Software"),("DevOps",r"docker|kubernetes|\bk8s\b|jenkins|terraform|ci/cd|devops|ansible","Software"),
 ("Linux",r"linux|unix|shell script|\bbash\b","Software"),("Testing & QA",r"selenium|test automation|manual testing|\bqa\b|cypress|playwright|jmeter|test cases","Software"),
 ("Cybersecurity",r"cyber ?security|\bsiem\b|penetration test|vulnerabilit|firewall|identity and access|\biam\b|threat","Software"),
 ("Networking",r"tcp/ip|routing|switching|\bccna\b|\bbgp\b|network protocols","Software"),
 ("Embedded & VLSI",r"embedded (?:systems?|software|c\b|linux|developer|engineer)|firmware|\bvlsi\b|verilog|systemverilog|\brtl\b|\basic\b|\bfpga\b","Software"),
 ("Salesforce",r"salesforce","Software"),("SAP",r"\bsap\b","Software"),
 ("Financial Analysis",r"financial (?:model|analysis|statement|planning|reporting)|\bvaluation|fp&a|\bbudgeting\b|financial forecasting","Business & Finance"),
 ("Accounting",r"\baccounting\b|tally|\bgst\b|\btds\b|reconciliation|bookkeeping|ledger|\bifrs\b|us gaap","Business & Finance"),
 ("Taxation",r"income tax|direct tax|indirect tax|transfer pricing|tax compliance|tax return","Business & Finance"),
 ("Risk & Compliance",r"risk management|regulatory compliance|compliance (?:monitoring|testing|program|risk)|\bkyc\b|\baml\b|regulatory reporting|internal audit|\bsox\b|credit risk|market risk","Business & Finance"),
 ("Business Analysis",r"business analysis|requirements? gathering|\bbrd\b|process mapping|gap analysis|user stories","Business & Finance"),
 ("Project Management",r"project management|\bpmp\b|prince2|scrum master|project plan","Business & Finance"),
 ("Product Management",r"product management|product roadmap|\bprd\b|product strategy","Business & Finance"),
 ("Supply Chain",r"supply chain|procurement|inventory management|logistics|demand planning|s&op|vendor management","Business & Finance"),
 ("Lean & Six Sigma",r"six sigma|\blean (?:manufacturing|principles|methodolog|six)|kaizen|value stream","Business & Finance"),
 ("Digital Marketing",r"\bseo\b|\bsem\b|google ads|meta ads|social media marketing|digital marketing|performance marketing|google analytics","Business & Finance"),
 ("Sales",r"b2b sales|inside sales|lead generation|pipeline management|sales targets?|\bquota\b|cold call|crm (?:tools|software|systems)","Business & Finance"),
 ("Customer Support",r"customer support|customer service|ticketing tool|zendesk|freshdesk","Business & Finance"),
 ("HR & Recruitment",r"recruitment (?:process|cycle|life ?cycle|drives?|strategy|coordinat|metrics)|end-to-end recruit|talent acquisition|\bhrms\b|payroll (?:process|management|operations)|employee relations|hr operations|hr policies","Business & Finance"),
 ("Clinical Research",r"clinical trial|clinical research|pharmacovigilance|\bicsr\b|clinical data|\bich-gcp\b|good clinical practice","Business & Finance"),
 ("UI/UX Design",r"figma|ui/ux|\bux design|\bui design|wireframe|adobe xd|ux research|user research|interaction design","Business & Finance"),
 ("Content Writing",r"content writing|copywriting|technical writing|proofread","Business & Finance"),
 ("PowerPoint",r"powerpoint|presentation skills|\bppt\b","Business & Finance"),
 ("Communication",r"(?:excellent|strong|good|effective) (?:verbal |written |oral )?(?:and (?:written|verbal) )?communication","Business & Finance")]
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
WD_MAX_JOBS = 1000   # Workday: read up to this many India postings per company (20 per request)
# Workday sites slow down or refuse requests when too many arrive at once from one computer (GitHub's robot shares
# its address with many others). So: at most WD_PARALLEL Workday requests at a time, patient retries, and a note of
# any company that was only partly read, so it gets a second, slower try at the end.
START = time.time()
WD_PARALLEL = 16; WD_DETAIL_THREADS = 6; WD_GATE = threading.BoundedSemaphore(WD_PARALLEL); WD_STATUS = {}
def wd_req(url, body=None, base=""):
    h = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36",
         "Accept": "application/json", "Accept-Language": "en-US", "Origin": base, "Referer": base}
    if body is not None: h["Content-Type"] = "application/json"
    waits = [2, 6, 15, 30]
    for attempt in range(len(waits) + 1):
        try:
            r = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None, headers=h)
            with WD_GATE, urllib.request.urlopen(r, timeout=40) as f: return json.load(f)
        except Exception as e:
            code = getattr(e, "code", None)
            if code in (400, 404, 410) or attempt == len(waits):   # a real "not found", or out of retries
                print("  ! skipped", url.split("?")[0][:90], "-", e); return None
            ra = 0
            try: ra = int((getattr(e, "headers", None) or {}).get("Retry-After") or 0)
            except Exception: pass
            time.sleep(min(max(ra, waits[attempt]), 45) + random.random() * 2)
def workday(spec, name):
    """Workday career sites (big MNCs): spec = tenant/wdN/site, e.g. nvidia/wd5/NVIDIAExternalCareerSite"""
    ten, wd, site = spec.split("/"); base = f"https://{ten}.{wd}.myworkdayjobs.com"; api = f"{base}/wday/cxs/{ten}/{site}"
    # Use the site's own "Country: India" filter when it has one. A text search for "India" also returns
    # Indiana (US) roles and ranks them oddly, so real India roles used to fall past the pages we read.
    first = wd_req(f"{api}/jobs", {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": ""}, base) or {}
    facet = None
    def find_india(fs, param=None):
        for f in fs or []:
            pm = f.get("facetParameter") or param
            for v in f.get("values") or []:
                if (v.get("descriptor") or "").strip().lower() == "india" and v.get("id"): return pm, v["id"], v.get("count") or 0
                hit = find_india([{"facetParameter": v.get("facetParameter") or pm, "values": v.get("values")}], pm) if v.get("values") else None
                if hit: return hit
    st = WD_STATUS.setdefault(name, {"spec": spec})
    if not first:   # the site didn't answer even after retries: leave it for the second try
        st.update(ok=False, got=0, expected=None); return
    facet = find_india(first.get("facets"))
    query = ({"appliedFacets": {facet[0]: [facet[1]]}, "searchText": ""} if facet else {"appliedFacets": {}, "searchText": "India"})
    posts, off, expected, broke = [], 0, (facet[2] if facet else None), False
    while off < WD_MAX_JOBS:
        d = wd_req(f"{api}/jobs", dict(query, limit=20, offset=off), base)
        if d is None: broke = True; break          # a page failed after retries: we only have part of the list
        batch = d.get("jobPostings", [])
        if off == 0 and d.get("total"): expected = d["total"]
        posts += [p for p in batch if p.get("externalPath")]   # skip odd entries with no link
        off += 20
        if len(batch) < 20 or (d.get("total") and off >= d["total"]): break
    want = min(expected or 0, WD_MAX_JOBS)
    st.update(ok=not broke and (not want or len(posts) >= want * 0.9), got=len(posts), expected=expected)
    def detail(p): return (wd_req(api + p["externalPath"], None, base) or {}).get("jobPostingInfo") or {}
    with cf.ThreadPoolExecutor(WD_DETAIL_THREADS) as ex: dets = list(ex.map(detail, posts))
    for p, det in zip(posts, dets):
        # if the detail page didn't load, still list the role from the search result (nothing is dropped)
        country = ((det.get("country") or {}).get("descriptor") or "")
        loc = det.get("location") or p.get("locationsText") or ""
        if (country == "India" or (facet and not country)) and not india(loc): loc = f"{loc}, India"   # the India filter guarantees it
        posted = det.get("startDate") or ""
        if not posted:
            po = det.get("postedOn") or p.get("postedOn") or ""; m = re.search(r"(\d+)\+? Days? Ago", po)
            days = 0 if "Today" in po else 1 if "Yesterday" in po else int(m.group(1)) if m else 30
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
    while off < 3000:
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
EXP_CTX = re.compile(r"experi|\bexp\b|work(?:ing)?\b|industry|relevant|professional|hands[- ]on|background|track record", re.I)
HISTORY = re.compile(r"past|last|over the|since|founded|history|legacy|anniversar|innovation|celebrat|serving|in business|trusted", re.I)
def min_years(desc, title=""):
    """Years of experience the role asks for. The title wins ("Analyst (2-5 yrs)"). Otherwise we read every
    "N years of experience" in the description and take the HIGHEST one: "5+ years, including 2 years of SQL"
    is a 5-year role, not a 2-year one (taking the lowest number used to push senior roles into Freshers)."""
    m = TITLE_EXP.search(title or "")
    if m and int(m.group(1)) <= 30: return int(m.group(1))
    d = desc or ""; in_ctx, every = [], []
    for m in EXP.finditer(d):
        v = int(m.group(1))
        if v > 30: continue
        before, after = d[max(0, m.start() - 50):m.start()], d[m.end():m.end() + 60]
        if v >= 15 and HISTORY.search(before[-25:] + after[:30]) and not re.search(r"experi", after[:45], re.I): continue   # "over 25 years of innovation"
        every.append(v)
        if EXP_CTX.search(before + after): in_ctx.append(v)
    nums = in_ctx or every
    return max(nums) if nums else None
def level(title, yrs, fixed=None):
    t = title.lower()
    if re.search(r"\bintern", t) or fixed == "Internship": return "Internship"
    if yrs is not None: return "Fresher" if yrs == 0 else f"{yrs}+ yrs"   # the job description wins
    if fixed == "Fresher" or re.search(r"graduate|fresher|new grad|campus|trainee|entry level", t): return "Fresher"
    if re.search(LEADERSHIP, t): return "Leadership"
    if re.search(SENIOR_HINT, t) or re.search(MID_HINT, t): return "Experienced"
    return "Not stated"
def bands(title, yrs, lvl):
    """Experience filter buckets: i=intern, f=fresher (no experience needed), 1=1-3, 3=3-5, 5=5-10, 10=10-15, 15=15-20, 20=20+ yrs (boundary roles sit in both)."""
    t = title.lower(); senior = re.search(SENIOR_HINT, t) or re.search(LEADERSHIP, t) or re.search(r"\b(leader|fellow)\b", t)
    if lvl == "Internship": return ["i"]
    if yrs is not None:
        fixed_map = {0:["f"], 1:["1"], 2:["1"], 3:["1","3"], 4:["3"], 5:["3","5"], 10:["5","10"], 15:["10","15"], 20:["15","20"]}
        if yrs == 0 and senior: return ["1"]                      # "0-2 yrs" on a Team Lead role is not a fresher role
        if yrs in fixed_map: return fixed_map[yrs]                # "Freshers" = roles that ask for no experience (0 yrs)
        return ["5"] if yrs < 10 else ["10"] if yrs < 15 else ["15"] if yrs < 20 else ["20"]
    if re.search(r"\b(chief|cxo|ceo|cfo|cto|coo|svp|evp|senior vice president|executive vice president|managing director|country head)\b", t): return ["15","20"]
    if re.search(LEADERSHIP, t): return ["10","15"]
    if re.search(r"\b(avp|assistant vice president)\b", t): return ["3","5"]   # bank titles: AVP ~ 3-8 yrs
    if re.search(r"\b(vp|vice president)\b", t): return ["5","10"]          # bank VP ~ 6-12 yrs
    if senior: return ["3","5"]                                # checked before "associate", so "Senior Associate" isn't a fresher role
    if re.search(MID_HINT, t): return ["1","3"]                 # "Associate II" is a step above entry level
    if lvl == "Fresher" or re.search(r"\b(junior|jr\.?|associate|trainee|graduate|entry)\b", t): return ["f"]
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
def skills(title, desc):   # every skill the role mentions (cards show the first 8; the hiring report counts all)
    t = (title + " " + (desc or "")).lower()
    return [s for s, pat, _ in SKILLS if re.search(pat, t)]

def strip_boilerplate(raw):
    """Remove the 'About the company' / benefits / equal-opportunity text a company pastes into every posting,
    so a logistics firm's roles aren't all tagged 'Supply Chain' just because its intro says so."""
    from collections import Counter, defaultdict
    split = lambda d: [x.strip() for x in re.split(r"(?<=[.!?])\s+|\s{3,}|•", d or "") if len(x.strip()) > 25]
    by_co = defaultdict(list)
    for j in raw: by_co[j["company"]].append(j)
    for co, L in by_co.items():
        if len(L) < 5: continue
        seen = Counter(s for j in L for s in set(split(j.get("desc"))))
        common = {s for s, c in seen.items() if c >= max(3, 0.3 * len(L))}
        if not common: continue
        for j in L:
            parts = split(j.get("desc"))
            if parts: j["desc"] = " ".join(x for x in parts if x not in common)

def hk(k): return hashlib.sha1(k.encode()).hexdigest()[:16]   # role ids stored as hashes, so jobs.json doesn't list the full board

def push_supabase(base, rows):
    """Upload the full board to Supabase (only signed-in students can read it there)."""
    key = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
    if not key:
        print("::warning::SUPABASE_SERVICE_KEY secret is missing - the full board was not uploaded"); return False
    h = {"apikey": key, "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates,return=minimal"}
    if key.startswith("eyJ"): h["Authorization"] = "Bearer " + key
    try:
        for row in rows:   # one row per request keeps each upload small, even with thousands of roles
            body = json.dumps([row], ensure_ascii=False, separators=(",", ":")).encode()
            urllib.request.urlopen(urllib.request.Request(base.rstrip("/") + "/rest/v1/snapshots?on_conflict=id",
                data=body, headers=h, method="POST"), timeout=180)
            print(f"  uploaded '{row['id']}' ({len(body)//1024} KB)")
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

def pack(L):   # compact form: repeated words (company, city, track...) are stored once, so the upload stays small
    D = {k: [] for k in ("company", "location", "vertical", "level", "tags", "degrees")}; ix = {k: {} for k in D}
    def code(k, v):
        if v not in ix[k]: ix[k][v] = len(D[k]); D[k].append(v)
        return ix[k][v]
    rows = [[code("company", j["company"]), j["title"], code("location", j["location"]), j["posted"], code("vertical", j["vertical"]),
             code("level", j["level"]), j.get("band", []), [code("tags", t) for t in j.get("tags", [])],
             [code("degrees", d) for d in j.get("degrees", [])], j.get("batch", []), j["firstSeen"], j["id"], j.get("openings", 1)] for j in L]
    return {"v": 2, "dict": D, "rows": rows}

# ---- India hiring report: what the open roles ask for (free summary on /report; the deep dives need a free account) ----
REPORT_CITIES = [("bengaluru", "Bengaluru", r"bengaluru|bangalore"), ("hyderabad", "Hyderabad", r"hyderabad"), ("pune", "Pune", r"pune"),
                 ("mumbai", "Mumbai", r"mumbai|thane"), ("ncr", "Delhi NCR", r"delhi|gurugram|gurgaon|noida"), ("chennai", "Chennai", r"chennai"),
                 ("kolkata", "Kolkata", r"kolkata"), ("ahmedabad", "Ahmedabad", r"ahmedabad|gandhinagar"), ("kochi", "Kochi / Trivandrum", r"kochi|cochin|thiruvananthapuram|trivandrum"),
                 ("coimbatore", "Coimbatore", r"coimbatore"), ("jaipur", "Jaipur", r"jaipur"), ("remote", "Remote", r"remote")]
REPORT_BANDS = [("i", "Internships"), ("f", "Freshers"), ("1", "1–3 years"), ("3", "3–5 years"), ("5", "5–10 years"), ("10", "10–15 years"), ("15", "15–20 years"), ("20", "20+ years")]
def hiring_report(roles, hist_path="report_history.json"):
    from collections import Counter
    n = len(roles) or 1
    pct = lambda c, N: round(100 * c / (N or 1), 1)
    def top(counter, N, k): return [[x, c, pct(c, N)] for x, c in counter.most_common(k)]
    def city_keys(j): l = (j.get("location") or "").lower(); return [k for k, _, rx in REPORT_CITIES if re.search(rx, l)]
    def counts(L):
        sk, co, ci, tr, bd = Counter(), Counter(), Counter(), Counter(), Counter()
        for j in L:
            sk.update(set(j.get("tags", []))); co[j["company"]] += 1; tr[j["vertical"]] += 1
            ci.update(city_keys(j)); bd.update(set(j.get("band", [])))
        return sk, co, ci, tr, bd
    sk, co, ci, tr, bd = counts(roles)
    month_ago = (NOW - timedelta(days=30)).strftime("%Y-%m-%d")
    fresher = [j for j in roles if set(j.get("band", [])) & {"f", "i"}]
    fsk, fco, fci, ftr, _ = counts(fresher)
    label = dict((k, l) for k, l, _ in REPORT_CITIES)
    # month-by-month history, so "rising skills" can compare with last month
    hist = {"months": {}}
    try: hist = json.load(open(hist_path))
    except Exception: pass
    mk = NOW.strftime("%Y-%m"); months = hist.setdefault("months", {})
    snap = {"roles": len(roles), "updated": TODAY, "skills": {k: pct(v, n) for k, v in sk.items()},
            "tracks": dict(tr), "cities": dict(ci),
            "trackSkills": {t: {k: pct(v, c) for k, v in counts([j for j in roles if j["vertical"] == t])[0].items()} for t, c in tr.items() if c >= 30}}
    # a day when some job sites failed to load shouldn't overwrite a fuller day of the same month
    if not months.get(mk) or len(roles) >= 0.85 * months[mk].get("roles", 0): months[mk] = snap
    prev_keys = sorted(k for k in months if k < mk); prev = months[prev_keys[-1]] if prev_keys else None
    def moves(now_sk, prev_sk, min_pct=3):
        out = [[k, v, prev_sk.get(k, 0), round(v - prev_sk.get(k, 0), 1)] for k, v in now_sk.items() if max(v, prev_sk.get(k, 0)) >= min_pct]
        out.sort(key=lambda x: -x[3]); return {"up": [x for x in out if x[3] > 0][:6], "down": [x for x in out[::-1] if x[3] < 0][:4]}
    month_name = lambda k: datetime.strptime(k + "-01", "%Y-%m-%d").strftime("%B %Y")
    free = {"asof": NOW.strftime("%d %b %Y"), "month": month_name(mk), "roles": len(roles), "openings": sum(j.get("openings", 1) for j in roles),
            "companies": len(co), "new30": sum(1 for j in roles if (j.get("posted") or j.get("firstSeen") or "") >= month_ago),
            "skills": top(sk, n, 12), "tracks": [[t, c, pct(c, n)] for t, c in tr.most_common() if t != "Other"],
            "cities": [[k, label[k], c, pct(c, n)] for k, c in ci.most_common(8)],
            "exp": [[b, l, bd.get(b, 0), pct(bd.get(b, 0), n)] for b, l in REPORT_BANDS],
            "companiesTop": top(co, n, 10),
            "fresher": {"roles": len(fresher), "companies": top(fco, len(fresher), 5), "skills": top(fsk, len(fresher), 5)},
            "rising": moves(snap["skills"], prev["skills"]) if prev else None, "prevMonth": month_name(prev_keys[-1]) if prev else "",
            "tracksLocked": [t for t, c in tr.most_common() if c >= 30 and t != "Other"]}
    detail = {"tracks": {}, "cities": {}, "byExp": {}, "pairs": {}}
    for t in free["tracksLocked"]:
        L = [j for j in roles if j["vertical"] == t]; a, b, c, _, e = counts(L); N = len(L)
        detail["tracks"][t] = {"roles": N, "skills": top(a, N, 10), "companies": top(b, N, 8), "cities": [[k, label[k], v, pct(v, N)] for k, v in c.most_common(6)],
                               "exp": [[x, l, e.get(x, 0), pct(e.get(x, 0), N)] for x, l in REPORT_BANDS], "freshers": sum(1 for j in L if set(j.get("band", [])) & {"f", "i"}),
                               "rising": moves(snap["trackSkills"].get(t, {}), (prev or {}).get("trackSkills", {}).get(t, {}), 5) if prev and t in (prev.get("trackSkills") or {}) else None}
    for k, l, _ in REPORT_CITIES:
        L = [j for j in roles if k in city_keys(j)]; N = len(L)
        if N < 30: continue
        a, b, _, d, _ = counts(L)
        detail["cities"][k] = {"label": l, "roles": N, "tracks": [[x, v, pct(v, N)] for x, v in d.most_common(6) if x != "Other"], "skills": top(a, N, 8), "companies": top(b, N, 8)}
    for x, l in REPORT_BANDS:
        L = [j for j in roles if x in j.get("band", [])]; N = len(L)
        if N >= 20: detail["byExp"][x] = {"label": l, "roles": N, "skills": top(counts(L)[0], N, 8)}
    for s_, c_, _ in [x for x in free["skills"] if x[0] != "Communication"][:10]:   # which skills are asked for together
        L = [j for j in roles if s_ in j.get("tags", [])]; pair = Counter()
        for j in L: pair.update(t for t in set(j.get("tags", [])) if t != s_)
        detail["pairs"][s_] = top(pair, len(L), 4)
    deg = Counter(d for j in fresher for d in set(j.get("degrees", [])))
    detail["fresher"] = {"roles": len(fresher), "companies": top(fco, len(fresher), 15), "skills": top(fsk, len(fresher), 12),
                         "cities": [[k, label[k], v, pct(v, len(fresher))] for k, v in fci.most_common(8)],
                         "tracks": [[x, v, pct(v, len(fresher))] for x, v in ftr.most_common(8) if x != "Other"], "degrees": top(deg, len(fresher), 6)}
    json.dump(hist, open(hist_path, "w"), ensure_ascii=False, separators=(",", ":"))
    return free, detail

def write_report_post(free, hub):
    url = (hub or "https://jobs.analyticswallah.com").rstrip("/") + "/report?src=linkedin-report"
    sk = " · ".join(f"{s} {round(p)}%" for s, _, p in free["skills"][:5])
    fr = free["fresher"]
    lines = [f"📊 What India's top employers are hiring for: {free['month']}", "",
             f"I looked at {free['roles']:,} open roles from {free['companies']} companies' official career pages (as of {free['asof']}).", "",
             f"🔥 Most-asked skills: {sk}"]
    if fr["roles"]:
        lines += [f"🎓 Freshers: {fr['roles']:,} open roles. Most openings at {', '.join(c for c, _, _ in fr['companies'][:3])}.",
                  f"   Skills freshers are asked for: {', '.join(s for s, _, _ in fr['skills'][:4])}"]
    if free["cities"]: lines.append("📍 Most jobs: " + ", ".join(f"{l} ({c:,})" for _, l, c, _ in free["cities"][:4]))
    if free.get("rising") and free["rising"]["up"]:
        lines.append(f"📈 Rising since {free['prevMonth'].split()[0]}: " + ", ".join(f"{s} (+{d} pts)" for s, _, _, d in free["rising"]["up"][:3]))
    lines += ["", f"Full report, by career track and city (free): {url}", "", "#hiring #jobs #freshers #careers #India #AnalyticsWallah"]
    open("report_post.txt", "w", encoding="utf-8").write("\n".join(lines) + "\n")

# ---- Job agent (AW Students): score each member against today's jobs and keep their best 20 ----
# Plain rules, no AI: skills count most, then experience, city and preferred role. Personal details go from
# Supabase to Supabase only; nothing about members is ever written to the files in this repository.
AGENT_KEEP, AGENT_DAYS, AGENT_MIN = 20, 15, 40
BAND_YEARS = {"i": (0, 1), "f": (0, 1), "1": (1, 3), "3": (3, 5), "5": (5, 10), "10": (10, 15), "15": (15, 20), "20": (20, 45)}
AGENT_CITY = {k: rx for k, _, rx in REPORT_CITIES}

class SB:
    """Tiny Supabase (PostgREST) client using the secret key from the GitHub secret."""
    def __init__(self, base, key):
        self.base = base.rstrip("/") + "/rest/v1/"; self.h = {"apikey": key, "Content-Type": "application/json"}
        if key.startswith("eyJ"): self.h["Authorization"] = "Bearer " + key
    def call(self, method, path, body=None, prefer=None):
        h = dict(self.h, **({"Prefer": prefer} if prefer else {}))
        data = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode() if body is not None else None
        with urllib.request.urlopen(urllib.request.Request(self.base + path, data=data, headers=h, method=method), timeout=120) as r:
            txt = r.read().decode() or "null"
            return json.loads(txt)
    def all(self, path):   # read every row, 1000 at a time
        out, off = [], 0
        while True:
            sep = "&" if "?" in path else "?"
            page = self.call("GET", f"{path}{sep}limit=1000&offset={off}") or []
            out += page; off += 1000
            if len(page) < 1000: return out

def agent_score(p, j):
    """Score one member against one job, 0-100, with the reason shown on the site."""
    skills = set(p.get("skills") or []); tags = list(dict.fromkeys(j.get("tags") or []))
    have = [t for t in tags if t in skills]; missing = sorted([t for t in tags if t not in skills], key=lambda t: t == "Communication")
    if not [t for t in have if t != "Communication"]: return None   # needs at least one real job skill in common
    cover = len(have) / max(3, min(len(tags), 6))   # a job asking for 1 skill can't score as high as one where you match 4 of 5
    pts = 55 * min(1.0, cover)
    yrs = p.get("exp_years"); bands = j.get("band") or []
    if yrs is None or yrs == "" or not bands: pts += 10
    else:
        y = float(yrs); gaps = [0 if lo - 1 <= y <= hi + 1 else min(abs(y - lo), abs(y - hi)) for lo, hi in (BAND_YEARS[b] for b in bands if b in BAND_YEARS)]
        g = min(gaps) if gaps else 3
        pts += 20 if g == 0 else 10 if g <= 2 else 0
    cities = [c for c in (p.get("pref_cities") or []) if c in AGENT_CITY]; loc = (j.get("location") or "").lower()
    city_ok = (not cities) or "remote" in loc or any(re.search(AGENT_CITY[c], loc) for c in cities)
    pts += 15 if city_ok else 0
    roles = p.get("pref_roles") or []
    pts += 5 if not roles else 10 if j.get("vertical") in roles else 0
    score = int(round(pts))
    why = "Matches " + ", ".join(have[:4]) + (f"; missing {', '.join(missing[:3])}" if missing else "; you have every skill it asks for")
    return score, why, have, missing

def run_job_agent(st, public, early):
    key = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
    if not key or not st.get("supabase_url"): print("Job agent: skipped (no Supabase secret key)"); return None
    sb = SB(st["supabase_url"], key)
    members = {(m.get("email") or "").strip().lower() for m in sb.all("members?select=email")}
    people = [p for p in sb.all("profiles?select=id,email,skills,exp_years,pref_cities,pref_roles,agent_on&agent_on=is.true")
              if (p.get("email") or "").strip().lower() in members]
    rd = int(st.get("recent_days", 90) or 0); rcut = (NOW - timedelta(days=rd)).strftime("%Y-%m-%d") if rd > 0 else ""
    pool = {j["id"]: dict(j, early=False) for j in public if not rcut or not j["posted"] or j["posted"] >= rcut}
    pool.update({j["id"]: dict(j, early=True) for j in early})
    old = {}
    for m in sb.all("matches?select=user_id,job_id,found_on"): old.setdefault(m["user_id"], {})[m["job_id"]] = m["found_on"]
    tracked = {}
    for t in sb.all("tracker?select=user_id,url"): tracked.setdefault(t["user_id"], set()).add(t["url"])
    # jobs a member has already had as a match for 15 days are not shown to them again (kept privately in one robot-only row)
    seen_row = sb.call("GET", "snapshots?select=data&id=eq.agent_seen") or []
    seen = (seen_row[0]["data"] if seen_row else {}) or {}
    expire = (NOW - timedelta(days=AGENT_DAYS)).strftime("%Y-%m-%d")
    ids = {p["id"] for p in people}; rows, drop, new_total, matched, new_by = [], {}, 0, 0, {}
    for p in people:
        mine_old = old.get(p["id"], {}); done = seen.get(p["id"], {})
        for jid, d in mine_old.items():
            if d < expire: done[jid] = d                            # 15 days are up: retire it
        cand = []
        for jid, j in pool.items():
            if jid in done or j.get("url") in tracked.get(p["id"], ()): continue   # retired, or already in their tracker
            r = agent_score(p, j)
            if r and r[0] >= AGENT_MIN: cand.append((r[0], j.get("posted") or "", jid, r))
        cand.sort(key=lambda x: (x[0], x[1]), reverse=True)        # best score first, newest first on ties
        keep = cand[:AGENT_KEEP]; keep_ids = {c[2] for c in keep}
        for score, _, jid, (sc, why, have, missing) in keep:
            j = pool[jid]; found = mine_old.get(jid) or TODAY
            if jid not in mine_old: new_total += 1; new_by.setdefault(p["id"], []).append({"title": j["title"], "company": j["company"], "score": sc})
            rows.append({"user_id": p["id"], "job_id": jid, "score": sc, "reason": why, "have": have, "missing": missing,
                         "title": j["title"], "company": j["company"], "location": j.get("location", ""), "vertical": j.get("vertical", ""),
                         "level": j.get("level", ""), "posted": j.get("posted", ""), "url": j.get("url", ""), "early": j["early"], "found_on": found})
        gone = [jid for jid in mine_old if jid not in keep_ids]      # weaker, closed or expired
        if gone: drop[p["id"]] = gone
        if keep: matched += 1
        seen[p["id"]] = {jid: d for jid, d in done.items() if jid in pool}   # forget jobs that have closed
    for uid in old:                                                  # agent switched off, or no longer an AW Student
        if uid not in ids: drop[uid] = list(old[uid]); seen.pop(uid, None)
    for uid, gone in drop.items():
        for k in range(0, len(gone), 100):
            sb.call("DELETE", f"matches?user_id=eq.{uid}&job_id=in.({','.join(gone[k:k+100])})", prefer="return=minimal")
    for k in range(0, len(rows), 500):
        sb.call("POST", "matches?on_conflict=user_id,job_id", rows[k:k+500], prefer="resolution=merge-duplicates,return=minimal")
    sb.call("POST", "snapshots?on_conflict=id", [{"id": "agent_seen", "data": {u: v for u, v in seen.items() if v}}], prefer="resolution=merge-duplicates,return=minimal")
    print(f"Job agent: {len(people)} AW Students with the agent on, {matched} matched, {new_total} new matches today")
    return {"people": len(people), "matched": matched, "new": new_total, "new_by": new_by}

# ---- Daily alerts: "X new jobs match you today" (email via Resend, WhatsApp via Meta). OFF until you switch them on ----
# Switch on in companies.json -> settings: "alerts_email": true and/or "alerts_whatsapp": true,
# and add the keys as GitHub secrets: RESEND_API_KEY (email) / WHATSAPP_TOKEN + WHATSAPP_PHONE_ID (WhatsApp).
# ---------- Google search pages: "Data Analyst jobs in Bengaluru" and friends ----------
# Plain, fast pages (no sign-in needed to read) that list real open roles and send people to the board.
SEO_CITIES = [("bengaluru", "Bengaluru", r"bengaluru|bangalore", "Bengaluru (Bangalore)"), ("hyderabad", "Hyderabad", r"hyderabad", "Hyderabad"), ("pune", "Pune", r"pune", "Pune"),
              ("mumbai", "Mumbai", r"mumbai|thane", "Mumbai"), ("ncr", "Delhi NCR", r"delhi|gurugram|gurgaon|noida", "Delhi NCR (Delhi, Gurugram, Noida)"),
              ("chennai", "Chennai", r"chennai", "Chennai"), ("kolkata", "Kolkata", r"kolkata", "Kolkata"), ("ahmedabad", "Ahmedabad", r"ahmedabad|gandhinagar", "Ahmedabad"), ("remote", "Remote", r"remote", "Remote (work from home)")]
SEO_ROLES = [("data-analyst", "Data Analyst", r"\bdata analy|\banalytics analyst|\bmis (executive|analyst)|\b(bi|business intelligence) analyst"), ("business-analyst", "Business Analyst", r"business analy"),
             ("financial-analyst", "Financial Analyst", r"financ\w* analy|fp&a|finance associate"), ("data-scientist", "Data Scientist", r"data scien"), ("data-engineer", "Data Engineer", r"data engineer"),
             ("software-engineer", "Software Engineer", r"software (engineer|developer)|\bsde\b"), ("accountant", "Accountant", r"accountant|accounts (executive|payable|receivable)"),
             ("product-manager", "Product Manager", r"product manager"), ("hr", "HR", r"\bhr\b|human resources|talent acquisition|recruiter")]
SEO_SKILLS = ["SQL", "Power BI", "Python", "Excel", "Tableau"]
def _slug(x): return re.sub(r"[^a-z0-9]+", "-", x.lower()).strip("-")
def _esc(x): return html.escape(str(x or ""), quote=True)

SEO_CSS = """*{box-sizing:border-box}body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,Arial,sans-serif;background:#fbfbfd;color:#1d1d1f;line-height:1.5;-webkit-font-smoothing:antialiased}
a{color:#0071e3;text-decoration:none}a:hover{text-decoration:underline}.w{max-width:980px;margin:0 auto;padding:0 18px}
.nav{position:sticky;top:0;z-index:5;background:rgba(251,251,253,.9);backdrop-filter:blur(14px);border-bottom:1px solid rgba(0,0,0,.08)}
.nav .w{display:flex;align-items:center;justify-content:space-between;gap:10px;height:56px}.logo{font-weight:800;font-size:18px;color:#1d1d1f;letter-spacing:-.02em}.logo span{color:#0071e3}.logo small{font-weight:600;font-size:12px;color:#0071e3;background:#eef4ff;border-radius:999px;padding:3px 9px;margin-left:8px}
.btn{display:inline-block;background:#0071e3;color:#fff;font-weight:600;border-radius:980px;padding:10px 20px;font-size:15px}.btn:hover{background:#0077ed;text-decoration:none}.btn.sm{padding:8px 14px;font-size:14px}.btn.gh{background:#fff;color:#0071e3;border:1px solid rgba(0,113,227,.3)}
.crumb{font-size:13px;color:#6e6e73;margin:18px 0 6px}.crumb a{color:#6e6e73}
h1{font-size:clamp(26px,5vw,40px);line-height:1.1;letter-spacing:-.03em;margin:0 0 10px}h2{font-size:clamp(19px,3vw,24px);letter-spacing:-.02em;margin:34px 0 12px}
.lead{font-size:17px;color:#424245;margin:0 0 16px;max-width:680px}.hero{padding:6px 0 22px}.acts{display:flex;flex-wrap:wrap;gap:10px;align-items:center}.upd{font-size:13px;color:#6e6e73}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:#34c759;margin-right:6px;animation:pl 1.8s ease-out infinite}@keyframes pl{from{box-shadow:0 0 0 0 rgba(52,199,89,.55)}to{box-shadow:0 0 0 8px rgba(52,199,89,0)}}
.job{transition:border-color .25s,box-shadow .25s,transform .25s}.job:hover{transform:translateY(-1px)}.go{transition:transform .25s}.job:hover .go{transform:translateX(3px)}
@media(prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
.facts{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:rgba(0,0,0,.08);border:1px solid rgba(0,0,0,.08);border-radius:16px;overflow:hidden;margin:6px 0 4px}
.facts div{background:#fff;padding:14px 10px;text-align:center}.facts b{display:block;font-size:22px;letter-spacing:-.02em}.facts span{font-size:12px;color:#6e6e73}
.jobs{display:grid;gap:10px;margin:0;padding:0;list-style:none}
.job{display:grid;grid-template-columns:44px minmax(0,1fr) auto;gap:12px;align-items:center;background:#fff;border:1px solid rgba(0,0,0,.08);border-radius:16px;padding:12px 14px;color:inherit}
.job:hover{border-color:rgba(0,113,227,.35);box-shadow:0 8px 24px rgba(0,60,140,.08);text-decoration:none}
.av{width:44px;height:44px;border-radius:12px;background:#eef4ff;color:#0071e3;font-weight:800;display:grid;place-items:center;font-size:15px}
.job b{display:block;font-size:15.5px;line-height:1.3}.job .m{font-size:13.5px;color:#424245}.job .t{font-size:12.5px;color:#6e6e73;margin-top:2px}
.go{font-size:13.5px;font-weight:600;color:#0071e3;white-space:nowrap}
.chips{display:flex;flex-wrap:wrap;gap:8px}.chips a,.chips span{background:#fff;border:1px solid rgba(0,0,0,.1);border-radius:999px;padding:7px 13px;font-size:14px;color:#1d1d1f}.chips a:hover{border-color:#0071e3;color:#0071e3;text-decoration:none}.chips i{font-style:normal;color:#6e6e73;margin-left:4px}
.cta{margin:34px 0;border-radius:22px;padding:26px 22px;background:linear-gradient(135deg,#0071e3,#2997ff);color:#fff}.cta h2{margin:0 0 6px;color:#fff}.cta p{margin:0 0 16px;opacity:.95}.cta .btn{background:#fff;color:#0071e3}
.faq p{color:#424245;margin:4px 0 14px}.faq b{display:block}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:8px}.grid a{background:#fff;border:1px solid rgba(0,0,0,.08);border-radius:12px;padding:10px 12px;font-size:14.5px;color:#1d1d1f;display:flex;justify-content:space-between;gap:8px}.grid a i{font-style:normal;color:#6e6e73}
footer{border-top:1px solid rgba(0,0,0,.08);margin-top:40px;padding:22px 0 40px;font-size:12.5px;color:#6e6e73}
@media(max-width:560px){.facts{grid-template-columns:repeat(2,1fr)}.job{grid-template-columns:38px minmax(0,1fr)}.av{width:38px;height:38px;font-size:13px}.go{display:none}.nav .btn{padding:8px 12px;font-size:13.5px}.logo small{display:none}}"""

def _seo_shell(title, desc, canon, body, ga="", ld=None):
    g = (f'<script async src="https://www.googletagmanager.com/gtag/js?id={_esc(ga)}"></script><script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments)}}gtag("js",new Date());gtag("config","{_esc(ga)}");</script>') if ga else ""
    l = f'<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False).replace("</", "<\\/")}</script>' if ld else ""
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(title)}</title><meta name="description" content="{_esc(desc)}"><link rel="canonical" href="{_esc(canon)}">
<meta property="og:title" content="{_esc(title)}"><meta property="og:description" content="{_esc(desc)}"><meta property="og:type" content="website"><meta property="og:url" content="{_esc(canon)}">
<meta property="og:image" content="https://jobs.analyticswallah.com/og-image.png"><meta name="twitter:card" content="summary_large_image"><meta name="theme-color" content="#fbfbfd">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='8' fill='%230071e3'/%3E%3Ctext x='16' y='22' font-family='Arial' font-weight='900' font-size='15' fill='white' text-anchor='middle'%3EAW%3C/text%3E%3C/svg%3E">
<style>{SEO_CSS}</style>{l}{g}</head><body>
<div class="nav"><div class="w"><a class="logo" href="/">Analytics<span>Wallah</span><small>Jobs Hub</small></a><a class="btn sm" href="/?src=seo">Open the job board</a></div></div>
{body}
<footer><div class="w">AW Jobs Hub by <a href="https://analyticswallah.com">Analytics Wallah</a>. Every role comes from the company's official careers page and the Apply button takes you there. Analytics Wallah never charges for job listings or referrals. <a href="/jobs/">All job searches</a> · <a href="/report">India hiring report</a></div></footer>
</body></html>"""

def write_seo_pages(roles, st, updated, min_roles=8, show=40):
    """Writes jobs/<slug>.html, jobs/index.html, sitemap.xml and robots.txt. Returns [[slug, label, count], ...] for the home page footer."""
    hub = (st.get("hub_url") or "https://jobs.analyticswallah.com").rstrip("/"); ga = st.get("ga4_id", "")
    month = NOW.strftime("%B %Y"); day = NOW.strftime("%d %b %Y")
    city_rx = [(k, lab, re.compile(rx, re.I), long) for k, lab, rx, long in SEO_CITIES]
    for j in roles: j["_c"] = {k for k, _, rx, _ in city_rx if rx.search(j["location"] or "")}
    kinds = []   # (slug, name, group, filter, board hash)
    for sl, lab, rx in SEO_ROLES:
        r = re.compile(rx, re.I); kinds.append((sl, lab, "Roles", (lambda j, r=r: bool(r.search(j["title"]))), "q=" + urllib.parse.quote(lab.lower())))
    kinds.append(("fresher", "Fresher", "Experience", lambda j: "f" in (j.get("band") or []), "exp=f"))
    kinds.append(("internship", "Internship", "Experience", lambda j: "i" in (j.get("band") or []) or j.get("level") == "Internship", "exp=i"))
    for sk in SEO_SKILLS: kinds.append((_slug(sk), sk, "Skills", (lambda j, sk=sk: sk in (j.get("tags") or [])), "skill=" + urllib.parse.quote(sk)))
    for tr in sorted({j["vertical"] for j in roles} - {"Other", "Internships"}):
        kinds.append((_slug(tr.replace("&", "and")), tr, "Career tracks", (lambda j, tr=tr: j["vertical"] == tr), "track=" + urllib.parse.quote(tr)))
    pages = []
    for sl, lab, grp, f, hsh in kinds:
        base = [j for j in roles if f(j)]
        for ck, clab, _, clong in [("", "India", None, "India")] + city_rx:
            L = [j for j in base if not ck or ck in j["_c"]]
            if len(L) < min_roles: continue
            pages.append(dict(slug=f"remote-{sl}-jobs" if ck == "remote" else f"{sl}-jobs-in-{'india' if not ck else _slug(clab)}", kind=sl, label=lab, group=grp, city=ck, clab=clab, clong=clong, jobs=L,
                              hash=hsh + (f"&city={ck}" if ck else "")))
    by_kind, by_city = {}, {}
    for p in pages: by_kind.setdefault(p["kind"], []).append(p); by_city.setdefault(p["city"], []).append(p)
    os.makedirs("jobs", exist_ok=True)
    for f in os.listdir("jobs"):
        if f.endswith(".html"): os.remove(os.path.join("jobs", f))   # yesterday's pages; today's are written fresh
    lvl = lambda j: {"Not stated": "Experience not stated"}.get(j.get("level"), j.get("level") or "")
    def ago(d):
        try: n = (NOW.date() - datetime.strptime(d, "%Y-%m-%d").date()).days
        except Exception: return ""
        return "Posted today" if n <= 0 else "Posted yesterday" if n == 1 else f"Posted {n} days ago" if n < 31 else f"Posted {n // 30} month{'s' if n // 30 > 1 else ''} ago"
    for p in pages:
        L = sorted(p["jobs"], key=lambda j: (j.get("posted") or j.get("firstSeen") or ""), reverse=True); n = len(L)
        cos, sk = {}, {}
        for j in L:
            cos[j["company"]] = cos.get(j["company"], 0) + j.get("openings", 1)
            for t in (j.get("tags") or []): sk[t] = sk.get(t, 0) + 1
        top_cos = sorted(cos.items(), key=lambda x: -x[1])[:12]; top_sk = [x for x in sorted(sk.items(), key=lambda x: -x[1]) if x[0] != "Communication"][:10]
        fresher_n = sum(1 for j in L if set(j.get("band") or []) & {"f", "i"}); week_n = sum(1 for j in L if (j.get("posted") or "") >= (NOW - timedelta(days=7)).strftime("%Y-%m-%d"))
        what = f"{p['label']} jobs" if p["group"] != "Career tracks" else f"{p['label']} jobs"
        h1 = f"Remote {what} in India" if p["city"] == "remote" else f"{what} in {p['clab']}"; p["h1"] = h1; canon = f"{hub}/jobs/{p['slug']}"; board = f"/?src=seo-{p['slug'][:30]}#{p['hash']}"
        # a role page searches the board by words, which finds a few more jobs than this page lists, so its buttons don't promise a number
        see_all = "Search these jobs on the board and apply free" if p["group"] == "Roles" else f"See all {n:,} jobs and apply free"
        see_more = f"See more {what} on the board →" if p["group"] == "Roles" else f"Show the other {n - show:,} jobs →"
        title = f"{h1}: {n} open now ({month}) | AW Jobs Hub"
        desc = f"{n} {what.lower() if p['group'] != 'Skills' else what} open in {p['clong']} at {', '.join(c for c, _ in top_cos[:4])} and more. Read from official company career pages and updated {day}. Apply free on AW Jobs Hub."
        def row(j):
            av = "".join(w[0] for w in re.findall(r"[A-Za-z0-9]+", j["company"])[:2]).upper()
            meta = " · ".join(x for x in (lvl(j), ago(j.get("posted")), ", ".join((j.get("tags") or [])[:4])) if x)
            return (f'<li><a class="job" href="/?src=seo#job={_esc(j.get("id", ""))}"><span class="av">{_esc(av)}</span><span><b>{_esc(j["title"])}</b>'
                    f'<span class="m">{_esc(j["company"])} · {_esc(j["location"])}</span><span class="t" style="display:block">{_esc(meta)}</span></span><span class="go">View &amp; apply →</span></a></li>')
        items = "".join(row(j) for j in L[:show])
        same_kind = [q for q in by_kind[p["kind"]] if q is not p]; same_city = [q for q in by_city[p["city"]] if q is not p and q["group"] != "Career tracks"][:14]
        chips = lambda Q, name: "".join(f'<a href="/jobs/{q["slug"]}">{_esc(name(q))}<i>{len(q["jobs"])}</i></a>' for q in Q)
        body = f"""<main class="w"><div class="crumb"><a href="/">AW Jobs Hub</a> › <a href="/jobs/">Job searches</a> › {_esc(h1)}</div>
<section class="hero"><h1>{_esc(h1)}</h1>
<p class="lead">{n:,} {_esc(what)} are open in {_esc(p['clong'])} right now, from {len(cos)} companies. Every role is read from the company's own careers page, so there are no fake or expired agency listings.</p>
<div class="acts"><a class="btn" href="{_esc(board)}">{_esc(see_all)}</a><span class="upd"><span class="dot"></span>Updated {day}</span></div></section>
<div class="facts"><div><b>{n:,}</b><span>open jobs</span></div><div><b>{len(cos)}</b><span>companies hiring</span></div>{f"<div><b>{week_n:,}</b><span>posted this week</span></div>" if week_n else "<div><b>Daily</b><span>checked every morning</span></div>"}<div><b>{fresher_n:,}</b><span>for freshers and interns</span></div></div>
<h2>Latest {_esc(h1)}</h2><ul class="jobs">{items}</ul>
{f'<p style="margin:14px 0 0"><a class="btn gh" href="{_esc(board)}">{_esc(see_more)}</a></p>' if n > show else ''}
<h2>Companies hiring for {_esc(h1)}</h2><div class="chips">{"".join(f"<span>{_esc(c)}<i>{k}</i></span>" for c, k in top_cos)}</div>
{f'<h2>Skills these jobs ask for most</h2><div class="chips">{"".join(f"<span>{_esc(t)}<i>{round(100 * k / n)}%</i></span>" for t, k in top_sk)}</div><p class="upd" style="margin-top:8px">Share of these {n:,} jobs that mention each skill.</p>' if top_sk else ''}
<div class="cta"><h2>Apply to these jobs free</h2><p>Sign in with Google to open the company's application page. A free account gives you {int(st.get('free_daily_applies', 3))} applications every day. No fees, ever.</p><a class="btn" href="{_esc(board)}">Open these jobs on the board</a></div>
{f'<h2>{_esc(what)} in other cities</h2><div class="chips">{chips(same_kind, lambda q: q["clab"])}</div>' if same_kind else ''}
{f'<h2>More {_esc("remote jobs" if p["city"] == "remote" else "jobs in " + p["clab"])}</h2><div class="chips">{chips(same_city, lambda q: q["label"] + " jobs")}</div>' if same_city else ''}
<div class="faq"><h2>Good to know</h2>
<b>Are these {_esc(what)} real?</b><p>Yes. Each one comes straight from the hiring company's official careers page, and the Apply button takes you there. The list is refreshed every morning.</p>
<b>Do I have to pay to apply?</b><p>No. AW Jobs Hub is free and Analytics Wallah never charges for job listings or referrals.</p>
<b>Can freshers apply?</b><p>{f"{fresher_n:,} of these {n:,} jobs are tagged for freshers or interns." if fresher_n else "Most of these jobs ask for some experience."} On the board you can filter by experience, from fresher to 20+ years.</p></div></main>"""
        ld = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "AW Jobs Hub", "item": hub + "/"}, {"@type": "ListItem", "position": 2, "name": "Job searches", "item": hub + "/jobs/"}, {"@type": "ListItem", "position": 3, "name": h1, "item": canon}]}
        open(f"jobs/{p['slug']}.html", "w", encoding="utf-8").write(_seo_shell(title, desc, canon, body, ga, ld))
    # one page that lists every search, so people and Google can reach them all
    groups = {}
    for p in pages: groups.setdefault(p["group"], []).append(p)
    sec = "".join(f'<h2>{_esc(g)}</h2><div class="grid">' + "".join(f'<a href="/jobs/{q["slug"]}">{_esc(("Remote " + q["label"] + " jobs") if q["city"] == "remote" else (q["label"] + " jobs in " + q["clab"]))}<i>{len(q["jobs"]):,}</i></a>' for q in sorted(groups[g], key=lambda q: (q["label"], q["city"] != "", -len(q["jobs"])))) + "</div>"
                  for g in ("Roles", "Experience", "Skills", "Career tracks") if g in groups)
    body = f"""<main class="w"><div class="crumb"><a href="/">AW Jobs Hub</a> › Job searches</div><section class="hero"><h1>Jobs in India by role, skill and city</h1>
<p class="lead">{len(roles):,} open jobs from official company career pages, sorted into {len(pages)} ready-made searches. Pick one, or open the board and filter it your way.</p>
<div class="acts"><a class="btn" href="/?src=seo-index">Open the job board</a><span class="upd"><span class="dot"></span>Updated {day}</span></div></section>{sec}</main>"""
    open("jobs/index.html", "w", encoding="utf-8").write(_seo_shell(f"Jobs in India by role, skill and city ({month}) | AW Jobs Hub", f"{len(roles):,} open jobs in India from official company career pages: data analyst, business analyst, finance, fresher and internship jobs by city. Updated {day}.", hub + "/jobs/", body, ga))
    urls = [hub + "/", hub + "/report", hub + "/jobs/"] + [f"{hub}/jobs/{p['slug']}" for p in pages]
    open("sitemap.xml", "w", encoding="utf-8").write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "".join(f"<url><loc>{_esc(u)}</loc><lastmod>{TODAY}</lastmod></url>\n" for u in urls) + "</urlset>\n")
    open("robots.txt", "w", encoding="utf-8").write(f"User-agent: *\nAllow: /\nSitemap: {hub}/sitemap.xml\n")
    for j in roles: j.pop("_c", None)
    # the home page footer links to the most useful searches
    want = ["data-analyst", "business-analyst", "financial-analyst", "fresher", "internship", "sql", "power-bi", "data-scientist"]
    foot = [p for k in want for p in by_kind.get(k, []) if p["city"] in ("", "bengaluru", "hyderabad", "pune", "mumbai", "ncr")]
    return [[p["slug"], f"{p['label']} jobs in {p['clab']}", len(p["jobs"])] for p in foot][:24], len(pages)

def _post_json(url, body, headers):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=dict({"Content-Type": "application/json"}, **headers), method="POST")
    with urllib.request.urlopen(req, timeout=30) as r: return r.status

def send_alerts(st, res):
    em, wa = bool(st.get("alerts_email")), bool(st.get("alerts_whatsapp"))
    if not (em or wa): return "off"
    if not res or not res.get("new_by"): return "on, nobody had new matches"
    rk, wt, wp = (os.environ.get(k, "").strip() for k in ("RESEND_API_KEY", "WHATSAPP_TOKEN", "WHATSAPP_PHONE_ID"))
    sender = (st.get("alert_from") or "").strip()
    if em and not (rk and sender): print("::warning::Email alerts are on but RESEND_API_KEY secret or alert_from setting is missing"); em = False
    if wa and not (wt and wp): print("::warning::WhatsApp alerts are on but WHATSAPP_TOKEN / WHATSAPP_PHONE_ID secrets are missing"); wa = False
    if not (em or wa): return "on, but keys are missing"
    sb = SB(st["supabase_url"], os.environ.get("SUPABASE_SERVICE_KEY", "").strip())
    hub = (st.get("hub_url") or "https://jobs.analyticswallah.com").rstrip("/")
    link = hub + "/?src=alert"
    cap = int(st.get("alert_daily_cap", 90) or 90)   # Resend's free plan sends 100 emails a day
    uids = list(res["new_by"]); profs = []
    for k in range(0, len(uids), 100):
        profs += sb.call("GET", f"profiles?select=id,name,email,phone,consent,last_alert&id=in.({','.join(uids[k:k+100])})") or []
    sent_e = sent_w = failed = 0
    for p in profs:
        if not p.get("consent") or p.get("last_alert") == TODAY: continue   # only people who agreed, once a day
        new = res["new_by"].get(p["id"]) or []
        n = len(new); first = (p.get("name") or "there").split()[0]
        if not n: continue
        top = sorted(new, key=lambda x: -x["score"])[:3]
        ok = False
        if em and sent_e < cap and p.get("email"):
            items = "".join(f"<li><b>{html.escape(x['title'])}</b> at {html.escape(x['company'])} ({x['score']}% match)</li>" for x in top)
            body = {"from": sender, "to": [p["email"]], "subject": f"{n} new job{'s' if n > 1 else ''} match you today",
                    "html": f"<p>Hi {html.escape(first)},</p><p>Your AW job agent found <b>{n} new job{'s' if n > 1 else ''}</b> that match your skills today:</p><ul>{items}</ul>"
                            f"<p><a href='{link}'>See all your matches on AW Jobs Hub</a></p><p style='color:#888;font-size:12px'>You get this because you turned on job alerts. To stop, untick alerts in your AW Jobs Hub details.</p>",
                    "text": f"Hi {first}, your AW job agent found {n} new job matches today. See them: {link}"}
            try: _post_json("https://api.resend.com/emails", body, {"Authorization": "Bearer " + rk}); sent_e += 1; ok = True
            except Exception as e: failed += 1; print("  ! email alert failed:", str(e)[:80])
        digits = re.sub(r"\D", "", p.get("phone") or "")[-10:]
        if wa and len(digits) == 10:
            body = {"messaging_product": "whatsapp", "to": "91" + digits, "type": "template",
                    "template": {"name": st.get("whatsapp_template", "new_job_matches"), "language": {"code": st.get("whatsapp_lang", "en")},
                                 "components": [{"type": "body", "parameters": [{"type": "text", "text": first}, {"type": "text", "text": str(n)}, {"type": "text", "text": link}]}]}}
            try: _post_json(f"https://graph.facebook.com/{st.get('whatsapp_api_version', 'v23.0')}/{wp}/messages", body, {"Authorization": "Bearer " + wt}); sent_w += 1; ok = True
            except Exception as e: failed += 1; print("  ! WhatsApp alert failed:", str(e)[:80])
        if ok: sb.call("PATCH", f"profiles?id=eq.{p['id']}", {"last_alert": TODAY}, prefer="return=minimal")
    print(f"Alerts: {sent_e} emails, {sent_w} WhatsApp messages sent" + (f", {failed} failed" if failed else ""))
    return f"{sent_e} emails, {sent_w} WhatsApp" + (f", {failed} failed" if failed else "")

PROBLEMS = []   # anything here turns the GitHub run red (and GitHub emails you)
def main():
    cfg = json.load(open("companies.json")); st = cfg.get("settings", {}); MAX = st.get("max_years", 30)
    global SR_LIMIT, EXCLUDE_LEAD; SR_LIMIT = int(st.get("max_per_company", 2000)) * 3; EXCLUDE_LEAD = bool(st.get("exclude_leadership", False))
    global STALE; age = int(st.get("max_age_days", 0) or 0); STALE = (NOW - timedelta(days=age)).strftime("%Y-%m-%d") if age > 0 else ""   # 0 = show every open role, however old
    prev = json.load(open("jobs.json")) if os.path.exists("jobs.json") else {"jobs": []}
    first_seen = {norm(j["company"], j["title"]): j.get("firstSeen", TODAY) for j in prev["jobs"]}
    first_seen.update(prev.get("seen", {}))   # remembers roles even when they were hidden by the per-company cap
    RECENT = (NOW - timedelta(days=2)).strftime("%Y-%m-%d")      # a role we start tracking late is "new" only if it was posted recently
    fs = lambda key, default=TODAY: first_seen.get(hk(key)) or first_seen.get(key) or default

    tasks = [(f, t, n) for src, f in (("greenhouse",greenhouse),("lever",lever),("ashby",ashby),("smartrecruiters",smartrecruiters),("workable",workable),("workday",workday))
             for t, n in cfg.get(src, {}).items()]
    raw = []
    def safe(a):   # one broken company feed must never stop the whole board
        try: return list(a[0](a[1], a[2]))
        except Exception as e: print("  ! skipped", a[2], "-", repr(e)[:120]); return []
    with cf.ThreadPoolExecutor(20) as ex:   # 20 companies at a time
        got = list(ex.map(safe, tasks))
    # second try, one company at a time, for Workday sites that didn't answer or were only partly read
    global WD_DETAIL_THREADS
    retry = [i for i, t in enumerate(tasks) if t[0] is workday and not WD_STATUS.get(t[2], {}).get("ok", True)]
    if retry:
        print(f"Second try for {len(retry)} Workday companies: " + ", ".join(tasks[i][2] for i in retry)); time.sleep(20)
        WD_DETAIL_THREADS = 3
        for i in retry:
            if time.time() - START > 50 * 60: print("::warning::Out of time for second tries; skipped the rest"); break
            before = (WD_STATUS[tasks[i][2]].get("got") or 0, len(got[i]))
            again = safe(tasks[i])
            if len(again) >= before[1]: got[i] = again
            else: WD_STATUS[tasks[i][2]].update(got=before[0])   # keep the better of the two reads
    for jobs in got: raw += jobs
    WD_SHORT = sorted((n, s.get("got") or 0, s.get("expected")) for n, s in WD_STATUS.items() if not s.get("ok", True))
    if WD_SHORT: print("::warning::Workday sites only partly read: " + "; ".join(f"{n} {g}/{e or '?'}" for n, g, e in WD_SHORT))

    merged = {}
    strip_boilerplate(raw)
    for j in raw:
        j["title"] = clean_title(j["title"]); ok = india(j["location"]); j["location"] = city_names(clean_loc(j["location"])); t = j["title"].lower()
        if not ok or (EXCLUDE_LEAD and re.search(LEADERSHIP, t)): continue
        if "default template" in t: continue                  # placeholder postings
        if j["posted"] and j["posted"] < STALE: continue          # very old listings rarely respond
        m = TITLE_EXP.search(t); yrs = min_years(j["desc"], j["title"])
        if (m and int(m.group(1)) > MAX) or (yrs is not None and yrs > MAX): continue
        key = norm(j["company"], j["title"])
        if key in merged:   # same company + same title -> one card that says how many openings there are (and all their cities)
            m = merged[key]
            locs = list(dict.fromkeys(m["location"].split(" / ") + j["location"].split(" / ")))
            m["location"] = " / ".join([l for l in locs if l != "India"] or locs)   # "Mumbai / Pune", not "Mumbai / Pune / India"
            if j["url"] and j["url"] != m["url"]:
                m["openings"] = m.get("openings", 1) + 1
                if j["posted"] and (not m["posted"] or j["posted"] < m["posted"]): m["posted"], m["url"] = j["posted"], j["url"]   # keep the oldest opening: its link stays the same day to day
            continue
        merged[key] = dict(company=j["company"], title=j["title"], location=j["location"], url=j["url"], posted=j["posted"],
                           vertical=vertical(j["title"]), level=(lv := level(j["title"], yrs, j.get("fixed_level"))), band=bands(j["title"], yrs, lv),
                           years=yrs, tags=skills(j["title"], j["desc"]), degrees=degrees(j["desc"]), batch=batches(j["title"], j["desc"]), source="auto", openings=1, firstSeen=fs(key, TODAY if not j["posted"] or j["posted"] >= RECENT else j["posted"]))
    for key, m in merged.items():   # a grouped card is "new" only if its oldest opening is new
        if m["firstSeen"] == TODAY and m["posted"] and m["posted"] < RECENT and not (first_seen.get(hk(key)) or first_seen.get(key)):
            m["firstSeen"] = m["posted"]
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
    urls = {c["url"] for c in curated}; cap = st.get("max_per_company", 2000); per = {}; auto = []
    for j in sorted([j for j in merged.values() if j["url"] not in urls], key=lambda j: (j["level"] in ("Fresher", "Internship"), j["level"] != "Not stated", j["firstSeen"], j["posted"]), reverse=True):   # fresher & intern roles are never cut by the cap
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
            "skillList": [[n, pat, grp] for n, pat, grp in SKILLS],   # the page uses this for the skill picker and resume reading
            "config": {k: st.get(k, "") for k in ("aw_url", "ga4_id", "club_url", "supabase_url", "supabase_anon_key", "priority_group_url", "recent_days", "club_members", "social_proof_min")}}

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
        # the board opens on roles from the last `recent_days` (default 90); older roles that are still open sit behind a switch
        rd = int(st.get("recent_days", 90) or 0); rcut = (NOW - timedelta(days=rd)).strftime("%Y-%m-%d") if rd > 0 else ""
        recent = [j for j in public if not j["posted"] or j["posted"] >= rcut]
        n = st.get("preview_per_track", 5); per = {}; preview = []; by_track = {}
        for j in recent:
            per[j["vertical"]] = per.get(j["vertical"], 0) + 1
            by_track[j["vertical"]] = by_track.get(j["vertical"], 0) + 1
            if per[j["vertical"]] <= n: preview.append(j)
        # Application links live in their own protected row: AW students read it; free students open one at a time (daily limit)
        # the report counts every open role posted in the last `recent_days`, including the newest week AW Students see first
        rep_free, rep_detail = hiring_report(recent + early)
        rep_free.update(earlyIncluded=len(early), visibleRoles=len(recent), olderRoles=len(public) - len(recent))
        uploaded = push_supabase(st["supabase_url"], [
            {"id": "full", "data": {"updated": data["updated"], "today": TODAY, **pack(public), "report": rep_detail}},
            {"id": "early", "data": {"updated": data["updated"], "today": TODAY, **pack(early)}},
            {"id": "links", "data": {"public": {j["id"]: j["url"] for j in public}, "early": {j["id"]: j["url"] for j in early},
                                     "free_daily_applies": int(st.get("free_daily_applies", 3))}}])
        if not uploaded: PROBLEMS.append("The full board could not be uploaded to Supabase, so signed-in students still see yesterday's roles.")
        try:
            AGENT_RESULT = run_job_agent(st, public, early)
            try: ALERTS_TXT = send_alerts(st, AGENT_RESULT)
            except Exception as e: ALERTS_TXT = "failed"; print("::warning::Alerts step failed:", str(e)[:120])
        except Exception as e:
            body = e.read().decode()[:200] if hasattr(e, "read") else ""
            AGENT_RESULT = None; PROBLEMS.append(f"The job agent step failed ({str(e)[:80]} {body}). The board itself was updated normally.")
        picks_n = supabase_count(st["supabase_url"], "aw_picks", f"active=is.true&added=gte.{(NOW - timedelta(days=st.get('curated_expiry_days', 30))).strftime('%Y-%m-%d')}")
        week_ago = (NOW - timedelta(days=7)).strftime("%Y-%m-%d")
        preview = [{**j, "url": ""} for j in preview]
        band_counts = {}
        for j in recent:
            for b in j.get("band", []): band_counts[b] = band_counts.get(b, 0) + 1
        band_counts["pro"] = sum(1 for j in recent if set(j.get("band", [])) & {"1", "3", "5", "10", "15", "20"})
        data["bandCounts"] = band_counts
        early_by_track = {}
        for j in early: early_by_track[j["vertical"]] = early_by_track.get(j["vertical"], 0) + 1
        data["earlyByTrack"] = early_by_track
        # visitors can search every recent public role (no application links, no early-access roles); applying needs a free account
        month_ago = (NOW - timedelta(days=30)).strftime("%Y-%m-%d")
        data["pub"] = pack(recent)
        wf = open(".github/workflows/daily.yml", encoding="utf-8").read() if os.path.exists(".github/workflows/daily.yml") else ""
        tpl = open("template.html", encoding="utf-8").read() if os.path.exists("template.html") else ""
        SPLIT = "board.json" in wf and "boardFile" in tpl
        if SPLIT:
            json.dump({"updated": data["updated"], "today": TODAY, **data["pub"]}, open("board.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
            data["boardFile"] = "board.json"
        if "sitemap.xml" in wf:
            try: data["seo"], SEO_N = write_seo_pages(recent, st, data["updated"])
            except Exception as e: print("::warning::Google search pages were not written:", repr(e)[:160])
        data["signups30"] = supabase_count(st["supabase_url"], "profiles", f"created_at=gte.{month_ago}")
        data["signupsAll"] = supabase_count(st["supabase_url"], "profiles", "id=not.is.null")
        data.update(jobs=preview, gated=True, total=len(recent), olderCount=len(public) - len(recent), byTrack=by_track, earlyCount=len(early), earlyDays=ed, picksCount=picks_n,
                    freeApplies=int(st.get("free_daily_applies", 3)),
                    stats={"roles": len(recent), "cos": len({j["company"] for j in recent}), "cosAll": len({j["company"] for j in recent + early}),
                           "week": sum(1 for j in public if j["posted"] and j["posted"] >= week_ago),
                           "weekAll": sum(1 for j in public + early if (j["posted"] or j["firstSeen"]) >= week_ago)})
        went_public = (NOW - timedelta(days=ed)).strftime("%Y-%m-%d")
        club_fresh = [j for j in public if fresh(j) == went_public]   # early-access roles reach the AW Club when they go public
        club_all, club_total = recent, len(recent)   # WhatsApp posts only point to recent roles
        if st.get("club_post_links", "hub") == "hub":          # AW Club post links to the board, so every applicant signs up
            link = lambda j: f"{hub.rstrip('/')}/#job={j['id']}"
    else:
        rep_free, rep_detail = hiring_report([j for j in jobs if j["source"] == "auto"]); rep_free["open"] = True; rep_free["detail"] = rep_detail
        club_fresh = [j for j in jobs if (j["source"] == "curated" and j.get("added") == TODAY) or (has_history and j["source"] == "auto" and j["firstSeen"] == TODAY)]
        club_all, club_total = [j for j in jobs if j["source"] == "auto"], len(jobs)
    json.dump(data, open("jobs.json", "w"), ensure_ascii=False, indent=1)
    if os.path.exists("template.html"):
        blob = json.dumps({k: v for k, v in data.items() if k != "seen" and not (k == "pub" and data.get("boardFile"))}, ensure_ascii=False).replace("</", "<\\/")
        open("index.html", "w", encoding="utf-8").write(open("template.html", encoding="utf-8").read().replace("/*__JOBS_DATA__*/null", blob))
    if os.path.exists("report_template.html"):
        rcfg = {k: st.get(k, "") for k in ("aw_url", "ga4_id", "supabase_url", "supabase_anon_key", "club_members")}
        rblob = json.dumps({"report": rep_free, "config": rcfg, "updated": data["updated"]}, ensure_ascii=False).replace("</", "<\\/")
        open("report.html", "w", encoding="utf-8").write(open("report_template.html", encoding="utf-8").read().replace("/*__REPORT_DATA__*/null", rblob))
    write_report_post(rep_free, hub)
    is_early_career = lambda j: bool(set(j.get("band", ["f"])) & {"f", "i"})
    is_pro = lambda j: bool(set(j.get("band", [])) & {"1", "3", "5", "10", "15", "20"}) and not set(j.get("band", [])) & {"f", "i"}
    write_whatsapp([j for j in club_fresh if is_early_career(j)], [j for j in club_all if is_early_career(j)],
                   sum(1 for j in club_all if is_early_career(j)), hub, locals().get("link"))
    write_whatsapp([j for j in club_fresh if is_pro(j)], [j for j in club_all if is_pro(j)],
                   sum(1 for j in club_all if is_pro(j)), hub.rstrip("/") + "/#exp=pro" if hub else hub, locals().get("link"),
                   file="whatsapp_post_experienced.txt", title="💼 *EXPERIENCED ROLES (1+ YEARS)* 💼", what="roles for working professionals")
    print(f"Built {len(jobs)} roles ({new_today} new) from {len(raw)} scanned")
    # health check: companies whose feed suddenly returns nothing
    now_counts = {}
    for j in jobs: now_counts[j["company"]] = now_counts.get(j["company"], 0) + 1
    was = prev.get("companyCounts", {})
    went_quiet = sorted(c for c, n in was.items() if n >= 10 and not now_counts.get(c) and c in {n2 for s2 in ("greenhouse","lever","ashby","smartrecruiters","workable","workday") for n2 in cfg.get(s2, {}).values()})
    if went_quiet: print("::warning::No roles today from: " + ", ".join(went_quiet))
    if was and len(went_quiet) > max(5, len(was) // 4): PROBLEMS.append(f"{len(went_quiet)} companies returned no roles today ({', '.join(went_quiet[:8])}...). A job site may have changed.")
    d2 = json.load(open("jobs.json")); d2["companyCounts"] = now_counts; json.dump(d2, open("jobs.json", "w"), ensure_ascii=False, indent=1)
    ar = locals().get("AGENT_RESULT")
    agent_txt = f"{ar['people']} AW Students with it on, {ar['matched']} matched, {ar['new']} new matches today" if ar else "not run"
    summary = [f"### AW Jobs Hub refresh: {NOW.strftime('%d %b %Y, %I:%M %p IST')}", "",
               f"- **{len(jobs):,} roles** from **{len(now_counts)} companies** ({new_today} new today)",
               f"- Companies with no roles today that had 10+ before: {', '.join(went_quiet) if went_quiet else 'none'}",
               f"- Job agent: {agent_txt}",
               f"- Alerts: {locals().get('ALERTS_TXT', 'off')}",
               f"- Google search pages: {locals().get('SEO_N', 0)} written" + ("" if locals().get("SPLIT") else " (fast loading is off until the new timer file and page are both uploaded)"),
               f"- Workday sites only partly read: {'; '.join(f'{n} {g} of {e or chr(63)}' for n, g, e in WD_SHORT) if WD_SHORT else 'none'}"]
    summary += [f"- ❌ {p}" for p in PROBLEMS] or ["- ✅ Everything uploaded"]
    if os.environ.get("GITHUB_STEP_SUMMARY"): open(os.environ["GITHUB_STEP_SUMMARY"], "a").write("\n".join(summary) + "\n")
    if PROBLEMS:   # files are already saved; failing here turns the run red so GitHub emails you
        for p in PROBLEMS: print("::error::" + p)
        sys.exit(1)

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
