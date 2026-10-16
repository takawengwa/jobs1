#!/usr/bin/env python3
"""Daily job alerts with source-page checks, sponsorship screening, deduplication and CV matching."""
import html, json, os, re, smtplib, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse, quote_plus
from zoneinfo import ZoneInfo

import feedparser
import requests
from bs4 import BeautifulSoup

GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS", "").strip()
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "").replace(" ", "").strip()
EMAIL_TO = os.getenv("EMAIL_TO", "takaengwa@gmail.com").strip()
PR_EMAIL_TO = os.getenv("PR_EMAIL_TO", "telmamtoko@gmail.com").strip()
PR_EMAIL_CC = os.getenv("PR_EMAIL_CC", "takaengwa@gmail.com").strip()
MAX_PER_CATEGORY = int(os.getenv("MAX_PER_CATEGORY", "8"))
LOOKBACK_DAYS = int(os.getenv("LOOKBACK_DAYS", "14"))
REQUIRE_FUTURE_DEADLINE = os.getenv("REQUIRE_FUTURE_DEADLINE", "false").lower() == "true"
STATE_FILE = Path(os.getenv("STATE_FILE", ".job-alert-state/state.json"))
LOCAL_TZ = ZoneInfo("Africa/Harare")

if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
    sys.exit("ERROR: Set GMAIL_ADDRESS and GMAIL_APP_PASSWORD in GitHub Actions secrets.")

SEARCHES = [
    ("Zimbabwe · IT & Technology", 'Zimbabwe ("IT Manager" OR "ICT Manager" OR "IT Officer" OR "IT Support" OR "Systems Administrator" OR "Software Developer" OR Django OR Python) (job OR vacancy OR careers)'),
    ("Zimbabwe · IT job boards", '(site:vacancymail.co.zw OR site:zimbojobs.com OR site:ipcjobs.org) (IT OR ICT OR software OR "systems administrator" OR support) Zimbabwe'),
    ("Zimbabwe · Data & Analytics", 'Zimbabwe ("Data Analyst" OR "Data Manager" OR "Business Intelligence" OR "Power BI" OR "Data Scientist" OR "Data Engineer" OR "Reporting Analyst") (job OR vacancy)'),
    ("Zimbabwe · Data/BI job boards", '(site:vacancymail.co.zw OR site:zimbojobs.com OR site:ipcjobs.org OR site:zw.linkedin.com/jobs/view) ("Data Analyst" OR "Data Manager" OR "Business Intelligence" OR "Power BI" OR SQL)'),
    ("Zimbabwe · PR & Communications", 'Zimbabwe ("Public Relations Manager" OR "Public Relations Officer" OR "Public Relations Specialist" OR "Public Relations" OR "PR Manager" OR "PR Officer" OR "Communications Manager" OR "Communications Officer" OR "Corporate Affairs Manager" OR "Media Relations" OR "Public Affairs Manager" OR "External Relations") (job OR vacancy OR careers)'),
    ("Remote · Zimbabwe eligible · IT/Software", '(remote OR "work from anywhere") ("open to applicants in Zimbabwe" OR "Africa time zones" OR "worldwide remote" OR "remote worldwide" OR "anywhere in Africa") (IT OR ICT OR Python OR Django OR software developer OR systems administrator) jobs'),
    ("Remote · Zimbabwe eligible · Data/BI", '(remote OR "work from anywhere") (Zimbabwe OR Africa OR worldwide) ("Data Analyst" OR "Data Engineer" OR "Business Intelligence" OR "Power BI" OR SQL OR analytics) jobs'),
    ("Remote · Zimbabwe eligible · Communications", '(remote OR "work from anywhere") (Zimbabwe OR Africa OR worldwide) ("Public Relations Manager" OR "Public Relations Officer" OR "Public Relations" OR "PR Manager" OR "PR Officer" OR "Communications Manager" OR "Communications Officer" OR "Corporate Affairs Manager" OR "Media Relations" OR "Public Affairs") jobs'),
    ("Australia · IT/Software sponsorship", 'site:au.seek.com OR site:linkedin.com/jobs/view Australia ("visa sponsorship" OR "482 visa" OR "Skills in Demand visa" OR "sponsor") (IT OR ICT OR "software developer" OR Python OR "systems administrator")'),
    ("Australia · Data/BI sponsorship", 'site:au.seek.com OR site:linkedin.com/jobs/view Australia ("visa sponsorship" OR "482 visa" OR "Skills in Demand visa" OR "sponsor") ("data analyst" OR "data engineer" OR "Power BI" OR SQL OR analytics)'),
    ("Australia · Communications sponsorship", 'Australia ("visa sponsorship" OR "482 visa" OR "Skills in Demand visa" OR sponsor) ("Public Relations Manager" OR "Public Relations Officer" OR "Public Relations" OR "PR Manager" OR "Communications Manager" OR "Corporate Affairs Manager" OR "Media Relations" OR "Public Affairs") jobs'),
    ("New Zealand · IT/Software sponsorship", 'site:nz.seek.com OR site:linkedin.com/jobs/view "New Zealand" ("visa sponsorship" OR "accredited employer" OR "work visa support" OR "visa support") (IT OR ICT OR "software developer" OR Python OR "systems administrator")'),
    ("New Zealand · Data/BI sponsorship", 'site:nz.seek.com OR site:linkedin.com/jobs/view "New Zealand" ("visa sponsorship" OR "accredited employer" OR "work visa support" OR "visa support") ("data analyst" OR "data engineer" OR "Power BI" OR SQL OR analytics)'),
    ("New Zealand · Communications sponsorship", '"New Zealand" ("visa sponsorship" OR "accredited employer" OR "work visa support" OR "visa support") ("Public Relations Manager" OR "Public Relations Officer" OR "Public Relations" OR "PR Manager" OR "Communications Manager" OR "Corporate Affairs Manager" OR "Media Relations" OR "Public Affairs") jobs'),

    ("Ireland · IT/Data work permits", 'site:irishjobs.ie OR site:indeed.com OR site:jobs.ie Ireland (visa sponsorship OR "Critical Skills Employment Permit" OR "employment permit" OR "relocation support") (IT OR ICT OR Python OR software OR data analyst OR "data engineer" OR "business intelligence")'),
    ("Ireland · Telma PR/Communications", 'site:irishjobs.ie OR site:indeed.com OR site:jobs.ie Ireland ("work permit" OR sponsorship OR "employment permit") ("public relations" OR communications OR marketing OR "media relations" OR "corporate affairs" OR producer)'),
    ("Canada · IT/Data international candidates", 'site:jobbank.gc.ca/jobsearch/jobposting Canada ("open to international candidates" OR "temporary foreign worker" OR LMIA OR "foreign candidates") (IT OR software OR Python OR data analyst OR "data engineer" OR "business intelligence")'),
    ("Canada · Telma PR/Communications", 'Canada ("LMIA" OR "visa sponsorship" OR "work permit support" OR "international candidates") ("public relations" OR communications OR marketing OR "media relations" OR "corporate affairs" OR producer) jobs'),
    ("Germany · IT/Data skilled worker visa", 'site:make-it-in-germany.com OR site:arbeitsagentur.de/jobsuche OR site:stepstone.de Germany (visa OR "EU Blue Card" OR "skilled worker" OR relocation) (IT OR software OR Python OR "data analyst" OR "data engineer" OR "business intelligence") jobs'),
    ("Germany · Telma PR/Communications", 'Germany (visa sponsorship OR "EU Blue Card" OR relocation OR work visa) ("public relations" OR communications OR marketing OR "media relations" OR "corporate affairs" OR producer) jobs'),
    ("Norway · International skilled jobs", 'Norway (visa OR "skilled worker" OR sponsorship OR relocation) (IT OR software OR data analyst OR "data engineer" OR communications OR marketing) jobs'),
    ("Denmark · International skilled jobs", 'Denmark (visa OR "work permit" OR "Pay Limit Scheme" OR "Positive List" OR relocation) (IT OR software OR data analyst OR "data engineer" OR communications OR marketing) jobs'),
    ("Switzerland · International skilled jobs", 'Switzerland (work permit OR sponsorship OR relocation OR "third-country nationals") (IT OR software OR data analyst OR "data engineer" OR communications OR marketing) jobs'),
    ("Luxembourg · International skilled jobs", 'Luxembourg (work permit OR sponsorship OR relocation OR "EU Blue Card") (IT OR software OR data analyst OR "data engineer" OR communications OR marketing) jobs'),
    ("Liechtenstein · International skilled jobs", 'Liechtenstein (work permit OR residence permit OR sponsorship OR relocation) (IT OR software OR data analyst OR communications OR marketing) jobs'),
    ("United Kingdom · IT/Software sponsorship", '(UK OR "United Kingdom" OR Britain) ("visa sponsorship" OR "Skilled Worker visa" OR "certificate of sponsorship" OR "licensed sponsor") (IT OR ICT OR "IT support" OR "systems administrator" OR Python OR Django OR software developer) jobs'),
    ("United Kingdom · Data/BI sponsorship", '(UK OR "United Kingdom" OR Britain) ("visa sponsorship" OR "Skilled Worker visa" OR "certificate of sponsorship" OR "licensed sponsor") ("data analyst" OR "data engineer" OR "business intelligence" OR "Power BI" OR SQL OR analytics) jobs'),
    ("United Kingdom · Telma PR/Communications", '(UK OR "United Kingdom" OR Britain) ("visa sponsorship" OR "Skilled Worker visa" OR "certificate of sponsorship" OR "licensed sponsor") ("public relations" OR "communications manager" OR "communications officer" OR "media relations" OR "corporate affairs" OR producer OR marketing) jobs'),
    ("Africa · IT/Software excluding South Africa", '(Kenya OR Uganda OR Tanzania OR Rwanda OR Ethiopia OR Ghana OR Nigeria OR Zambia OR Botswana OR Namibia OR Malawi OR Mozambique OR Mauritius OR Egypt OR Morocco OR Senegal OR Cameroon OR Angola OR Lesotho OR Eswatini OR Gambia OR Liberia OR Sierra Leone OR Côte d’Ivoire) ("IT manager" OR "ICT officer" OR "IT support" OR "systems administrator" OR software developer OR Python OR Django) (jobs OR vacancies OR careers) -"South Africa"'),
    ("Africa · Data/BI excluding South Africa", '(Kenya OR Uganda OR Tanzania OR Rwanda OR Ethiopia OR Ghana OR Nigeria OR Zambia OR Botswana OR Namibia OR Malawi OR Mozambique OR Mauritius OR Egypt OR Morocco OR Senegal OR Cameroon OR Angola OR Lesotho OR Eswatini OR Gambia OR Liberia OR Sierra Leone OR Côte d’Ivoire) ("data analyst" OR "data manager" OR "data scientist" OR "data engineer" OR "business intelligence" OR "Power BI" OR SQL OR analytics) (jobs OR vacancies OR careers) -"South Africa"'),
    ("Africa · Telma PR/Communications excluding South Africa", '(Kenya OR Uganda OR Tanzania OR Rwanda OR Ethiopia OR Ghana OR Nigeria OR Zambia OR Botswana OR Namibia OR Malawi OR Mozambique OR Mauritius OR Egypt OR Morocco OR Senegal OR Cameroon OR Angola OR Lesotho OR Eswatini OR Gambia OR Liberia OR Sierra Leone OR Côte d’Ivoire) ("public relations" OR "communications manager" OR "communications officer" OR "media relations" OR "corporate affairs" OR "public affairs" OR producer OR marketing) (jobs OR vacancies OR careers) -"South Africa"'),
    ("Africa · Regional and international organisations excluding South Africa", '(Africa OR "East Africa" OR "West Africa" OR "North Africa" OR "Central Africa") ("IT" OR ICT OR software OR "data analyst" OR "data management" OR "information management" OR communications OR "public relations") (NGO OR humanitarian OR development OR careers OR jobs) -"South Africa"'),
    ("Africa · Remote jobs open to African applicants excluding South Africa", '(remote OR "work from anywhere") (Africa OR Kenya OR Uganda OR Tanzania OR Rwanda OR Ghana OR Nigeria OR Zambia OR Namibia OR Botswana OR Malawi OR Mauritius OR Egypt OR Morocco) (software OR IT OR ICT OR "data analyst" OR "data engineer" OR "Power BI" OR communications) jobs -"South Africa"'),
    ("Development organisations · IT/ICT/Systems", '(UNICEF OR WHO OR UNDP OR "African Union" OR "United Nations" OR UNFPA OR WFP OR UNHCR OR IOM OR "World Bank" OR "African Development Bank" OR USAID OR "U.S. Government" OR USG OR "FHI 360" OR PATH OR Jhpiego OR "Save the Children" OR "World Vision" OR CARE OR IRC OR "International Rescue Committee" OR Palladium OR Chemonics OR DAI OR "Médecins Sans Frontières" OR MSF OR ICRC OR IFRC) ("IT Officer" OR "ICT Officer" OR "Information Systems" OR "Systems Administrator" OR "Digital Transformation" OR software OR technology) (jobs OR careers OR vacancy) Africa'),
    ("Development organisations · Data/MEAL/Information Management", '(UNICEF OR WHO OR UNDP OR "African Union" OR "United Nations" OR UNFPA OR WFP OR UNHCR OR IOM OR "World Bank" OR "African Development Bank" OR USAID OR "U.S. Government" OR USG OR "FHI 360" OR PATH OR Jhpiego OR "Save the Children" OR "World Vision" OR CARE OR IRC OR Palladium OR Chemonics OR DAI OR MSF OR ICRC OR IFRC) ("Data Analyst" OR "Data Manager" OR "Information Management Officer" OR "Monitoring and Evaluation" OR MEAL OR "Business Intelligence" OR "Research Data" OR statistician) (jobs OR careers OR vacancy) Africa'),
    ("Development organisations · Telma PR/Communications", '(UNICEF OR WHO OR UNDP OR "African Union" OR "United Nations" OR UNFPA OR WFP OR UNHCR OR IOM OR "World Bank" OR "African Development Bank" OR USAID OR "U.S. Government" OR USG OR "FHI 360" OR PATH OR Jhpiego OR "Save the Children" OR "World Vision" OR CARE OR IRC OR Palladium OR Chemonics OR DAI OR MSF OR ICRC OR IFRC) ("Communications Officer" OR "Communications Specialist" OR "Public Information Officer" OR "Media Relations" OR "Public Affairs" OR "External Relations" OR advocacy OR "communications manager" OR producer) (jobs OR careers OR vacancy) Africa'),
    ("UN and AU careers · IT/Data", '(site:careers.un.org OR site:unjobs.org OR site:jobs.unicef.org OR site:who.int/careers OR site:undp.org/jobs OR site:jobs.au.int OR site:african-union.org) (IT OR ICT OR data OR "information management" OR digital OR analytics) (Africa OR Zimbabwe OR regional)'),
    ("UN and AU careers · Telma PR/Communications", '(site:careers.un.org OR site:unjobs.org OR site:jobs.unicef.org OR site:who.int/careers OR site:undp.org/jobs OR site:jobs.au.int OR site:african-union.org) (communications OR media OR advocacy OR "public information" OR "external relations" OR public affairs) (Africa OR Zimbabwe OR regional)'),
    ("USG/USAID-funded implementers · IT/Data", '(USAID OR "U.S. Government" OR USG OR "US government funded" OR "USAID-funded" OR "State Department") ("IT Officer" OR ICT OR "data analyst" OR "data manager" OR MEL OR MEAL OR "information management") (Africa OR Zimbabwe) jobs careers'),
    ("USG/USAID-funded implementers · Telma PR/Communications", '(USAID OR "U.S. Government" OR USG OR "USAID-funded" OR "State Department") (communications OR "public affairs" OR advocacy OR "media relations" OR "strategic communications") (Africa OR Zimbabwe) jobs careers'),
    ("International NGOs · IT/Data/Operations", '("International NGO" OR humanitarian OR development OR "non-profit" OR nonprofit OR "civil society") ("IT Officer" OR ICT OR "data analyst" OR "data manager" OR "information management" OR "digital systems" OR "monitoring and evaluation") (Africa OR Zimbabwe) jobs careers'),
    ("International NGOs · Telma PR/Communications", '("International NGO" OR humanitarian OR development OR "non-profit" OR nonprofit OR "civil society") (communications OR advocacy OR "public information" OR "media relations" OR "external relations" OR "corporate communications") (Africa OR Zimbabwe) jobs careers'),
    ("Europe · International recruitment / work permit support", '(Ireland OR Canada OR Germany OR Norway OR Denmark OR Switzerland OR Luxembourg OR Liechtenstein) ("visa sponsorship" OR "work permit support" OR "critical skills" OR "EU Blue Card" OR LMIA OR "international applicants") (IT OR software OR data OR communications OR marketing) jobs'),
]

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; DailyJobAlerts/2.0; +https://github.com/)"}
CLOSED = ["no longer accepting applications", "applications closed", "position has been filled", "vacancy closed", "job expired", "applications are now closed", "this job is no longer available", "advertisement has closed"]
NO_SPONSOR = ["no visa sponsorship", "no sponsorship available", "unable to sponsor", "cannot sponsor", "we do not sponsor", "we are unable to provide sponsorship", "sponsorship is not available", "will not sponsor visas"]
WORK_RIGHTS = ["must have unrestricted work rights", "must have full working rights", "must already have the right to work", "existing right to work required", "without sponsorship", "no visa support is available", "must be legally entitled to work in australia without sponsorship", "must be legally entitled to work in new zealand without sponsorship", "only applicants with australian work rights", "only applicants with new zealand work rights", "valid australian working rights", "valid new zealand working rights"]
CONFIRMED_SPONSOR = ["critical skills employment permit", "employment permit sponsorship", "we support work permit applications", "we sponsor work visas", "lmia approved", "positive lmia", "lmia available", "open to international candidates", "recruiting foreign candidates", "visa sponsorship available", "visa sponsorship is available", "we offer visa sponsorship", "we provide visa sponsorship", "sponsorship available", "sponsorship will be provided", "will sponsor your visa", "visa sponsorship provided", "employer sponsored visa", "employer-sponsored visa", "482 visa sponsorship", "subclass 482 sponsorship", "skills in demand visa sponsorship", "visa sponsorship offered", "we can sponsor", "sponsor the successful candidate", "sponsorship considered"]
POTENTIAL_SPONSOR = ["eu blue card", "skilled worker visa support", "work permit support", "eligible for employment permit", "critical skills occupation", "positive list", "pay limit scheme", "lmia applied", "open to international applicants", "third-country nationals", "accredited employer", "relocation assistance", "relocation support", "visa support", "work visa support", "immigration support", "visa assistance", "sponsorship may be available", "may consider sponsorship", "sponsorship on a case-by-case basis"]
TRACKING_KEYS = {"gclid", "fbclid", "ref", "source", "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "trk", "trackingid"}
DATE_PATTERNS = [
    re.compile(r"(?i)(?:closing date|application deadline|apply by|applications close|closing on|deadline|expires?|applications must be received by)\s*[:\-]?\s*([A-Z][a-z]+\s+\d{1,2},?\s+\d{4})"),
    re.compile(r"(?i)(?:closing date|application deadline|apply by|applications close|closing on|deadline|expires?|applications must be received by)\s*[:\-]?\s*(\d{1,2}\s+[A-Z][a-z]+\s+\d{4})"),
    re.compile(r"(?i)(?:closing date|application deadline|apply by|applications close|closing on|deadline|expires?|applications must be received by)\s*[:\-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})"),
    re.compile(r"(?i)(?:closing date|application deadline|apply by|applications close|closing on|deadline|expires?|applications must be received by)\s*[:\-]?\s*(\d{4}-\d{2}-\d{2})"),
]

# Terms are drawn from the user's IT support, IT service management, software and data CVs.
CV_TERMS = {
    "IT / Service Management": ["it manager", "ict manager", "it support", "it officer", "it specialist", "itil", "service desk", "incident management", "windows", "microsoft 365", "linux", "active directory", "network", "infrastructure", "cybersecurity", "information security", "disaster recovery", "systems administrator", "technical support"],
    "Software / Systems": ["python", "django", "software developer", "software engineer", "api", "systems development", "requirements", "user acceptance testing", "uat", "automation", "database", "sql", "integration"],
    "Data / BI": ["data analyst", "data manager", "data scientist", "data engineer", "business intelligence", "power bi", "excel", "etl", "data quality", "data pipeline", "reporting analyst", "analytics", "data modelling", "data modeling", "r programming", "sql"],
    "Telma — PR / Communications": [
        "public relations", "public relations officer", "public relations manager", "communications specialist",
        "communications manager", "communications officer", "media relations", "social media management",
        "strategic planning", "team management", "content creation", "stakeholder engagement", "marketing",
        "commercial producer", "commercial production", "producer", "factual and entertainment", "creative direction",
        "executive producer", "brand narratives", "integrated marketing campaigns", "graphic design",
        "multimedia production", "media and alternative development", "advertising revenue", "client retention",
        "rebranding", "campaigns", "audience engagement", "visual content", "creative art and design"
    ]
}

def clean(value):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value or ""))).strip()

def local_today():
    return datetime.now(LOCAL_TZ).date()

def pubdate(value):
    try:
        dt = parsedate_to_datetime(value)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None

def parse_deadline(text):
    for pattern in DATE_PATTERNS:
        match = pattern.search(text or "")
        if not match:
            continue
        raw = match.group(1).strip()
        for fmt in ("%B %d, %Y", "%B %d %Y", "%b %d, %Y", "%b %d %Y", "%d %B %Y", "%d %b %Y", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y", "%m-%d-%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(raw, fmt).date(), raw
            except ValueError:
                pass
    return None, None

def normalize_url(url):
    try:
        p = urlparse(url)
        query = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if k.lower() not in TRACKING_KEYS and not k.lower().startswith("utm_")]
        return urlunparse((p.scheme.lower() or "https", p.netloc.lower().removeprefix("www."), p.path.rstrip("/"), "", urlencode(query), ""))
    except Exception:
        return (url or "").split("#", 1)[0]

def resolve_and_read(url):
    """Follow redirects to the original advert and extract visible page text where possible."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=12, allow_redirects=True)
        final_url = response.url or url
        content_type = response.headers.get("content-type", "").lower()
        if response.status_code >= 400 or (content_type and "html" not in content_type and "text" not in content_type):
            return final_url, "", False, f"HTTP {response.status_code}"
        soup = BeautifulSoup(response.text[:2_000_000], "html.parser")
        for tag in soup(["script", "style", "noscript", "svg", "nav", "footer"]):
            tag.decompose()
        page_text = clean(soup.get_text(" ", strip=True))
        canonical = soup.find("link", rel=lambda v: v and "canonical" in v.lower())
        if canonical and canonical.get("href"):
            can = canonical.get("href")
            if can.startswith("http"):
                final_url = can
        return final_url, page_text[:120_000], bool(response.status_code < 400 and len(page_text) > 250), f"HTTP {response.status_code}"
    except Exception as exc:
        return url, "", False, type(exc).__name__

def region(category):
    text = (category or "").lower()
    for country in ("Australia", "New Zealand", "Ireland", "Canada", "Germany", "Norway", "Denmark", "Switzerland", "Luxembourg", "Liechtenstein", "United Kingdom", "UK"):
        if country.lower() in text:
            return country
    if text.startswith("africa"):
        return "Africa"
    if text.startswith("remote"):
        return "Remote"
    return "Zimbabwe"

def sponsorship(text, region_name, source_verified):
    t = (text or "").lower()
    international_regions = ("Australia", "New Zealand", "Ireland", "Canada", "Germany", "Norway", "Denmark", "Switzerland", "Luxembourg", "Liechtenstein", "United Kingdom", "UK")
    if region_name == "Africa":
        return "Potential — cross-border work authorisation and local eligibility must be checked", False
    if region_name not in international_regions:
        return "Not applicable", False
    if any(phrase in t for phrase in NO_SPONSOR) or any(phrase in t for phrase in WORK_RIGHTS):
        return "Unavailable — explicit sponsorship/work-rights restriction; excluded", True
    # For UK roles, explicit sponsorship wording takes precedence over generic Skilled Worker / sponsor-register signals.
    if region_name in ("United Kingdom", "UK") and any(phrase in t for phrase in CONFIRMED_SPONSOR):
        if source_verified:
            return "Confirmed — explicit sponsorship wording on accessible source page", False
        return "Unverified — sponsorship wording found only in search result", False
    country_signal = {
        "United Kingdom": ["skilled worker visa", "certificate of sponsorship", "licensed sponsor"],
        "UK": ["skilled worker visa", "certificate of sponsorship", "licensed sponsor"],
        "Canada": ["lmia approved", "positive lmia", "lmia available", "open to international candidates", "recruiting foreign candidates", "temporary foreign worker"],
        "Ireland": ["critical skills employment permit", "general employment permit", "employment permit sponsorship", "work permit support"],
        "Germany": ["eu blue card", "visa support", "work permit support", "skilled worker visa"],
        "Norway": ["skilled worker visa", "work permit support", "visa sponsorship"],
        "Denmark": ["positive list", "pay limit scheme", "work permit support", "visa sponsorship"],
        "Switzerland": ["work permit support", "visa sponsorship", "third-country nationals"],
        "Luxembourg": ["eu blue card", "work permit support", "visa sponsorship"],
        "Liechtenstein": ["work permit support", "residence permit support", "visa sponsorship"],
    }
    if region_name in country_signal and any(phrase in t for phrase in country_signal[region_name]):
        if source_verified:
            return "Potential — country-specific permit/recruitment signal; verify employer sponsorship", False
        return "Unverified — permit/recruitment signal not confirmed on original advert", False
    if any(phrase in t for phrase in CONFIRMED_SPONSOR):
        if source_verified:
            return "Confirmed — explicit sponsorship wording on accessible source page", False
        return "Unverified — sponsorship wording found only in search result", False
    if any(phrase in t for phrase in POTENTIAL_SPONSOR):
        if source_verified:
            return "Potential — visa/relocation/accredited-employer wording; sponsorship not guaranteed", False
        return "Unverified — potential sponsorship wording; source page not verified", False
    if source_verified:
        return "Potential — no sponsorship statement found; ask employer before applying", False
    return "Unverified — original advert could not be checked", False

def match_score(title, text, category):
    combined = f"{title} {text}".lower()
    matched = []
    is_pr_category = any(token in (category or "").lower() for token in ("pr & communications", "communications sponsorship", "pr/communications", "telma pr"))
    # PR/communications vacancies are matched against Telma's attached CV, not Emmanuel's IT/data profile.
    if is_pr_category:
        profile_groups = {"Telma — PR / Communications": CV_TERMS["Telma — PR / Communications"]}
    else:
        profile_groups = {k: v for k, v in CV_TERMS.items() if k != "Telma — PR / Communications"}
    for group, terms in profile_groups.items():
        hits = [term for term in terms if term in combined]
        if hits:
            matched.append((group, hits[:6]))
    score = sum(min(4, len(hits)) * 2 for _, hits in matched)
    if any(word in combined for word in ("junior", "graduate", "entry level", "entry-level", "trainee", "assistant", "officer", "intern")):
        score += 1
    if any(word in combined for word in ("senior", "lead", "manager", "head of", "director", "specialist")):
        score += 1
    if any(word in combined for word in ("unpaid", "volunteer only")):
        score -= 4
    if region(category) in ("Australia", "New Zealand") and any(p in combined for p in CONFIRMED_SPONSOR):
        score += 3
    reasons = [f"{group}: {', '.join(hits)}" for group, hits in matched]
    return score, reasons

# Direct source checks complement Google News discovery. These are listing pages, not search snippets.
DIRECT_SOURCES = [
    ("VacancyMail", "https://www.vacancymail.co.zw/jobs/?ordering=new&page=1", "Zimbabwe"),
    ("VacancyMail", "https://www.vacancymail.co.zw/jobs/?ordering=new&page=2", "Zimbabwe"),
    ("VacancyMail", "https://www.vacancymail.co.zw/jobs/?ordering=new&page=3", "Zimbabwe"),
    ("ZimboJobs", "https://www.zimbojobs.com/jobs", "Zimbabwe"),
    ("IPC Jobs", "https://www.ipcjobs.org/", "Zimbabwe"),
    ("IPC Consultants", "https://www.ipcconsultants.com/jobs", "Zimbabwe"),
    ("Jobs Zimbabwe", "https://jobszimbabwe.co.zw/jobs/?display=list", "Zimbabwe"),
    ("Recruitment263", "https://recruitment263.co.zw/jobseekers", "Zimbabwe"),
    ("ZimJobSite", "https://www.zimjobsite.com/jobs", "Zimbabwe"),
    ("ZimJobsHub", "https://zimjobs.online/", "Zimbabwe"),
    ("Public Service Commission", "https://erecruitment.psc.gov.zw/", "Zimbabwe"),
]

RELEVANT_ROLE_TERMS = {
    "it": ["it manager", "ict manager", "it officer", "ict officer", "it support", "ict support", "systems administrator", "system administrator", "network administrator", "software developer", "software engineer", "django", "python developer", "information technology", "infrastructure", "service desk", "helpdesk", "help desk", "cybersecurity", "database administrator", "technical support", "technology manager", "digital transformation"],
    "data": ["data analyst", "data manager", "data scientist", "data engineer", "business intelligence", "power bi", "reporting analyst", "analytics", "data quality", "data officer", "database", "sql developer", "monitoring and evaluation", "m&e officer", "information management"],
    "pr": ["public relations", "pr manager", "pr officer", "pr specialist", "communications manager", "communications officer", "communications specialist", "corporate affairs", "media relations", "public affairs", "external relations", "stakeholder relations", "stakeholder engagement", "strategic communications", "marketing communications", "brand communications", "press officer", "media officer"],
}

def category_for_direct(title, summary, source_name):
    text = f"{title} {summary}".lower()
    if any(term in text for term in RELEVANT_ROLE_TERMS["pr"]):
        return "Zimbabwe · PR & Communications"
    if any(term in text for term in RELEVANT_ROLE_TERMS["data"]):
        return "Zimbabwe · Data & Analytics"
    if any(term in text for term in RELEVANT_ROLE_TERMS["it"]):
        return "Zimbabwe · IT & Technology"
    return None

def looks_like_vacancy_url(href, source_name):
    path = urlparse(href).path.lower()
    if source_name == "VacancyMail":
        return "/jobs/" in path and path.rstrip("/") != "/jobs"
    if source_name == "ZimboJobs":
        return any(x in path for x in ("/job/", "/jobs/", "/opening/", "/position/", "/job-details/")) and path.rstrip("/") != "/jobs"
    if source_name in ("IPC Jobs", "IPC Consultants"):
        return any(x in path for x in ("/job/", "/jobs/", "/vacancy/", "/opportunity/")) and path.rstrip("/") not in ("/jobs", "/job")
    if source_name == "Jobs Zimbabwe":
        return any(x in path for x in ("/job/", "/jobs/", "/vacancy/")) and path.rstrip("/") not in ("/jobs", "/job")
    if source_name == "Recruitment263":
        return any(x in path for x in ("/job/", "/jobs/", "/vacancy/", "/opportunity/")) and path.rstrip("/") not in ("/jobs", "/job", "/jobseekers")
    if source_name == "ZimJobSite":
        return any(x in path for x in ("/job/", "/jobs/", "/job-listing/", "/job-details/")) and path.rstrip("/") not in ("/jobs", "/job")
    if source_name == "ZimJobsHub":
        return any(x in path for x in ("/job/", "/jobs/", "/vacancy/", "/vacancies/")) and path.rstrip("/") not in ("/jobs", "/job")
    if source_name == "Public Service Commission":
        return any(x in path for x in ("/job/", "/jobs/", "/vacancy/", "/vacancies/", "/position/", "/requisition/")) and path.rstrip("/") not in ("/jobs", "/vacancies", "/")
    return False

def fetch_direct_sources():
    """Read current listing pages directly, extracting relevant vacancy detail links."""
    candidates, errors = [], []
    for source_name, listing_url, _ in DIRECT_SOURCES:
        try:
            response = requests.get(listing_url, headers=HEADERS, timeout=18, allow_redirects=True)
            response.raise_for_status()
            soup = BeautifulSoup(response.text[:3_000_000], "html.parser")
            # Prefer anchors inside listing cards, but fall back to all matching detail URLs.
            anchors = soup.find_all("a", href=True)
            page_candidates = []
            seen = set()
            for anchor in anchors:
                title = clean(anchor.get_text(" ", strip=True))
                href = anchor.get("href", "").strip()
                if not title or len(title) < 7 or len(title) > 180 or not href:
                    continue
                full_url = requests.compat.urljoin(response.url, href)
                if urlparse(full_url).netloc.lower().removeprefix("www.") not in {
                    "vacancymail.co.zw", "zimbojobs.com", "www.zimbojobs.com", "ipcjobs.org", "www.ipcjobs.org", "ipcconsultants.com", "www.ipcconsultants.com", "jobszimbabwe.co.zw", "www.jobszimbabwe.co.zw", "recruitment263.co.zw", "www.recruitment263.co.zw", "zimjobsite.com", "www.zimjobsite.com", "zimjobs.online", "www.zimjobs.online", "erecruitment.psc.gov.zw"
                }:
                    continue
                if not looks_like_vacancy_url(full_url, source_name):
                    continue
                key = normalize_url(full_url)
                if key in seen:
                    continue
                seen.add(key)
                parent = anchor
                card = None
                for ancestor in anchor.parents:
                    if getattr(ancestor, "name", None) in ("body", "html"):
                        break
                    labels = " ".join([str(ancestor.get("class", "")), str(ancestor.get("id", ""))]).lower()
                    if any(token in labels for token in ("job-card", "job_item", "job-item", "job-listing", "joblisting", "vacancy-card", "vacancy-item", "listing-item", "job-post", "job_post", "job-result", "job-card")):
                        card = ancestor
                        break
                if card is None:
                    card = anchor.parent.parent if anchor.parent and anchor.parent.parent else anchor.parent or anchor
                parent = card
                summary = clean(parent.get_text(" ", strip=True))[:1600]
                # Some boards use a generic "View & Apply" anchor. Recover the role title from nearby card links.
                if not category_for_direct(title, title, source_name):
                    nearby_titles = []
                    for nearby in parent.find_all("a", href=True):
                        nearby_text = clean(nearby.get_text(" ", strip=True))
                        if 7 <= len(nearby_text) <= 180 and category_for_direct(nearby_text, nearby_text, source_name):
                            nearby_titles.append(nearby_text)
                    if nearby_titles:
                        title = max(nearby_titles, key=len)
                category = category_for_direct(title, summary, source_name)
                if not category:
                    continue
                page_candidates.append({
                    "category": category,
                    "title": title,
                    "link": full_url,
                    "summary": summary,
                    "published": "Not stated (direct source listing)",
                    "discovery_source": source_name,
                })
            candidates.extend(page_candidates[:40])
            print(f"Direct source check: {source_name} — HTTP {response.status_code}, {len(page_candidates)} relevant links found")
        except Exception as exc:
            errors.append(f"Direct source {source_name} ({listing_url}): {type(exc).__name__}")
    return candidates, errors

def fetch_search_results():
    candidates = []
    errors = []
    now = datetime.now(timezone.utc)
    for category, query in SEARCHES:
        feed_url = "https://news.google.com/rss/search?q=" + quote_plus(query) + "&hl=en-ZW&gl=ZW&ceid=ZW:en"
        try:
            response = requests.get(feed_url, headers=HEADERS, timeout=18)
            response.raise_for_status()
            feed = feedparser.parse(response.content)
        except Exception as exc:
            errors.append(f"{category}: {type(exc).__name__}")
            continue
        count = 0
        for entry in feed.entries:
            title = clean(getattr(entry, "title", ""))
            link = getattr(entry, "link", "")
            summary = clean(getattr(entry, "summary", ""))
            if not title or not link:
                continue
            published = getattr(entry, "published", "")
            published_dt = pubdate(published) if published else None
            if published_dt and (now - published_dt).days > LOOKBACK_DAYS:
                continue
            candidates.append({"category": category, "title": title, "link": link, "summary": summary, "published": published or "Not stated"})
            count += 1
            if count >= MAX_PER_CATEGORY:
                break
        time.sleep(.1)
    direct_candidates, direct_errors = fetch_direct_sources()
    candidates.extend(direct_candidates)
    errors.extend(direct_errors)
    # De-duplicate discoveries before fetching individual advert pages.
    deduped = {}
    for candidate in candidates:
        key = normalize_url(candidate.get("link", ""))
        if not key:
            continue
        previous = deduped.get(key)
        if previous is None or (candidate.get("discovery_source") and not previous.get("discovery_source")):
            deduped[key] = candidate
    print(f"Discovery totals: {len(candidates)} candidates before URL deduplication; {len(deduped)} unique links after direct source checks")
    return list(deduped.values()), errors

def verify_candidate(candidate):
    final_url, page_text, verified, fetch_status = resolve_and_read(candidate["link"])
    combined = f"{candidate['title']} {candidate['summary']} {page_text}"
    closed = any(phrase in combined.lower() for phrase in CLOSED)
    due, due_raw = parse_deadline(page_text) if page_text else (None, None)
    if not due:
        due, due_raw = parse_deadline(f"{candidate['title']} {candidate['summary']}")
    today = local_today()
    if due and due < today:
        return {"excluded": "expired", "title": candidate["title"]}
    if closed:
        return {"excluded": "closed", "title": candidate["title"]}
    if REQUIRE_FUTURE_DEADLINE and not due:
        return {"excluded": "unknown_deadline", "title": candidate["title"]}
    region_name = region(candidate["category"])
    sponsor_label, sponsor_blocked = sponsorship(combined, region_name, verified)
    if sponsor_blocked:
        return {"excluded": "sponsorship_or_work_rights", "title": candidate["title"]}
    if region_name == "Remote":
        low = combined.lower()
        restricted = any(x in low for x in ["must be based in the united states", "us residents only", "only open to uk residents", "must reside in australia", "must be located in canada", "must live in the united kingdom", "only applicants located in the us", "must be based in new zealand"])
        if restricted:
            return {"excluded": "remote_location_restriction", "title": candidate["title"]}
        if not any(x in low for x in ["zimbabwe", "africa", "worldwide", "anywhere", "global", "work from anywhere"]):
            return {"excluded": "remote_eligibility_unconfirmed", "title": candidate["title"]}
    link = final_url if final_url.startswith("http") else candidate["link"]
    score, reasons = match_score(candidate["title"], f"{candidate['summary']} {page_text[:7000]}", candidate["category"])
    if due:
        deadline_label = f"{due.strftime('%d %b %Y')} — future deadline detected"
        status_label = "Source page checked; verify vacancy remains open"
    else:
        deadline_label = "Not stated — verify active status"
        status_label = "Original page checked" if verified else "Active status unverified; source page could not be checked"
    key_url = normalize_url(link)
    title_key = re.sub(r"[^a-z0-9]+", " ", candidate["title"].lower()).strip()
    return {"excluded": None, "id": key_url or title_key, "title_key": title_key, "category": candidate["category"], "title": candidate["title"], "employer": candidate["title"].rsplit(" - ", 1)[-1] if " - " in candidate["title"] else "See original advert", "link": link, "source": urlparse(link).netloc.lower().removeprefix("www."), "summary": candidate["summary"], "published": candidate["published"], "deadline": deadline_label, "deadline_date": due.isoformat() if due else None, "due": due, "status": status_label, "source_verified": verified, "source_check": fetch_status, "sponsorship": sponsor_label, "score": score, "match_reasons": reasons, "first_seen": local_today().isoformat(), "last_seen": local_today().isoformat()}

def collect():
    candidates, errors = fetch_search_results()
    verified = []
    excluded = {"expired": 0, "closed": 0, "unknown_deadline": 0, "sponsorship_or_work_rights": 0, "remote_location_restriction": 0, "remote_eligibility_unconfirmed": 0}
    # Source checks run concurrently to avoid long serial waits on blocked job boards.
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(verify_candidate, c) for c in candidates]
        for future in as_completed(futures):
            try:
                item = future.result()
                if item.get("excluded"):
                    excluded[item["excluded"]] = excluded.get(item["excluded"], 0) + 1
                else:
                    verified.append(item)
            except Exception as exc:
                errors.append(f"Source verification: {type(exc).__name__}")
    # Deduplicate within this run by canonical URL, then normalized title.
    unique = {}
    seen_titles = {}
    for item in verified:
        key = item["id"] or item["title_key"]
        title_key = item["title_key"]
        # Prefer one result per normalized title/employer, retaining the best verified destination.
        if title_key in seen_titles:
            old_key = seen_titles[title_key]
            old = unique[old_key]
            if item["source_verified"] and not old["source_verified"]:
                del unique[old_key]
                unique[key] = item
                seen_titles[title_key] = key
            continue
        if key not in unique or (item["source_verified"] and not unique[key]["source_verified"]):
            unique[key] = item
            seen_titles[title_key] = key
    return list(unique.values()), excluded, errors

def load_state():
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return {"jobs": {}, "last_weekly_summary": None}

def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

def classify_new(results, state):
    jobs = state.setdefault("jobs", {})
    new_items, updates, all_current = [], [], []
    now_day = local_today()
    for item in results:
        key = item["id"]
        previous = jobs.get(key)
        # Cross-run deduplication also catches the same vacancy syndicated under a different URL.
        if not previous:
            for existing_key, existing in jobs.items():
                if existing.get("title_key") == item.get("title_key"):
                    key = existing_key
                    previous = existing
                    item["id"] = existing_key
                    if item.get("source_verified") and not existing.get("source_verified"):
                        item["link"] = item.get("link") or existing.get("link")
                    break
        if previous:
            changed = previous.get("deadline_date") != item.get("deadline_date") or previous.get("sponsorship") != item.get("sponsorship") or previous.get("link") != item.get("link")
            item["first_seen"] = previous.get("first_seen", item["first_seen"])
            item["last_seen"] = now_day.isoformat()
            if changed:
                updates.append(item)
            # Preserve urgent-alert history to prevent repeat alerting.
            item["urgent_sent"] = previous.get("urgent_sent", False)
            item["weekly_eligible"] = previous.get("weekly_eligible", False)
        else:
            item["first_seen"] = now_day.isoformat()
            item["last_seen"] = now_day.isoformat()
            item["urgent_sent"] = False
            item["weekly_eligible"] = True
            new_items.append(item)
        jobs[key] = {k: v for k, v in item.items() if k not in ("due",)}
        all_current.append(item)
    # Keep 60 days of state so caches remain compact while preventing repeated daily listings.
    cutoff = (now_day - timedelta(days=60)).isoformat()
    state["jobs"] = {k: v for k, v in jobs.items() if (v.get("last_seen") or v.get("first_seen") or "0000-00-00") >= cutoff}
    return new_items, updates, all_current

def is_pr_role(item):
    """Route public relations, communications, public affairs and corporate affairs roles separately."""
    category = (item.get("category") or "").lower()
    title = (item.get("title") or "").lower()
    if any(token in category for token in ("pr & communications", "· communications sponsorship", "· communications", "pr/communications", "telma pr")):
        return True
    pr_terms = ("public relations", "pr manager", "pr officer", "communications manager", "communications officer",
                "corporate affairs", "media relations", "public affairs", "external relations")
    return any(term in title for term in pr_terms)

def escape(value):
    return html.escape(str(value or ""), quote=True)

def render_table(results, title, counts=None, errors=None):
    label = datetime.now(LOCAL_TZ).strftime("%A, %d %B %Y %H:%M Harare")
    out = [f"<h1>{escape(title)}</h1>", f"<p>Generated {escape(label)}. Ranked against Emmanuel's IT service management/support, Python/software systems and data/BI CV for general vacancies; PR/communications vacancies are matched separately against Telma Mtoko's attached Communications Specialist CV (media relations, social media, strategic planning, content creation, stakeholder engagement, marketing, commercial production and multimedia design). All career levels are considered.</p>"]
    if counts:
        out.append("<p><b>Screening:</b> " + escape("; ".join(f"{k.replace('_',' ')}: {v}" for k, v in counts.items())) + ".</p>")
    if errors:
        out.append(f"<p><b>Search/source warnings:</b> {len(errors)} checks failed. Some sources may be missing from this digest.</p>")
    if not results:
        out.append("<p>No new eligible vacancies met the current screening rules in this run.</p>")
    grouped = {}
    for item in sorted(results, key=lambda x: (-x.get("score", 0), x.get("deadline_date") or "9999-12-31")):
        grouped.setdefault(item["category"], []).append(item)
    for category, items in grouped.items():
        out.append(f"<h2>{escape(category)}</h2><table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse;width:100%;font:12px Arial,sans-serif'><thead><tr><th>Role / employer</th><th>Posted</th><th>Deadline / status</th><th>CV match</th><th>Visa sponsorship</th><th>Original advert</th></tr></thead><tbody>")
        for item in items:
            match = "; ".join(item.get("match_reasons", [])) or "No strong keyword overlap detected"
            source_status = "Original page accessible" if item.get("source_verified") else "Original page not verified"
            out.append("<tr>"
                f"<td><b>{escape(item['title'])}</b><br>{escape(item['employer'])}</td>"
                f"<td>{escape(item['published'])}</td>"
                f"<td>{escape(item['deadline'])}<br>{escape(item['status'])}</td>"
                f"<td><b>Score: {item['score']}</b><br>{escape(match[:450])}</td>"
                f"<td>{escape(item['sponsorship'])}</td>"
                f"<td><a href='{escape(item['link'])}'>Open original advert</a><br><small>{escape(item['source'])} · {escape(source_status)}</small></td></tr>")
        out.append("</tbody></table><br>")
    out.append("<hr><small>Discovery combines Google News RSS with direct listing-page checks for VacancyMail, ZimboJobs, IPC Jobs and IPC Consultants, then checks accessible original advert pages. Direct checks are best-effort and may be blocked or limited by site layout; this is not a guarantee of complete coverage. Expired deadlines and closed adverts are excluded. A reachable page does not guarantee a vacancy remains open. Sponsorship is classified from advert wording, not guaranteed. 'Potential' is not an offer. Check eligibility and visa rules with the employer and relevant immigration authority before applying.</small>")
    return "\n".join(out)

def send(subject, body, audience="main"):
    msg = EmailMessage()
    msg["From"] = GMAIL_ADDRESS
    if audience == "pr":
        to_address = PR_EMAIL_TO
        cc_address = PR_EMAIL_CC
        msg["To"] = to_address
        if cc_address:
            msg["Cc"] = cc_address
        recipients = [x for x in (to_address, cc_address) if x]
    else:
        msg["To"] = EMAIL_TO
        recipients = [EMAIL_TO]
    msg["Subject"] = subject
    msg.set_content("Open this email in an HTML-capable email client to view the job alert tables.")
    msg.add_alternative(body, subtype="html")
    with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as smtp:
        smtp.ehlo(); smtp.starttls(); smtp.ehlo()
        smtp.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        smtp.send_message(msg, to_addrs=recipients)
    print(f"SMTP accepted email for {audience} audience ({', '.join(recipients)}): {subject}")

def urgent_eligible(item):
    due = date.fromisoformat(item["deadline_date"]) if item.get("deadline_date") else None
    days_left = (due - local_today()).days if due else 999
    confirmed = item.get("sponsorship", "").startswith("Confirmed —")
    return confirmed and item.get("score", 0) >= 5 and 0 <= days_left <= 3 and not item.get("urgent_sent", False)

def main():
    state = load_state()
    results, excluded, errors = collect()
    new_items, updates, current = classify_new(results, state)
    # Route PR/communications roles only to their dedicated recipient; the general digest excludes them.
    digest_items = new_items + updates
    pr_digest_items = [item for item in digest_items if is_pr_role(item)]
    general_digest_items = [item for item in digest_items if not is_pr_role(item)]

    daily_html = render_table(general_digest_items, "Daily Job Alerts — Zimbabwe, UK, Africa & International", excluded, errors)
    send(f"Daily Job Alerts — {local_today().strftime('%d %b %Y')} — {len(general_digest_items)} new/updated", daily_html, audience="main")

    # Send a separate PR/communications digest to telmamtoko@gmail.com, CC takaengwa@gmail.com.
    if pr_digest_items:
        pr_html = render_table(pr_digest_items, "Public Relations & Communications Job Alerts", excluded, errors)
        send(f"PR & Communications Vacancies — {local_today().strftime('%d %b %Y')} — {len(pr_digest_items)} new/updated", pr_html, audience="pr")

    jobs = state.setdefault("jobs", {})
    urgent_items = []
    for item in current:
        if urgent_eligible(item):
            urgent_items.append(item)
            if item["id"] in jobs:
                jobs[item["id"]]["urgent_sent"] = True
    urgent_pr = [item for item in urgent_items if is_pr_role(item)]
    urgent_general = [item for item in urgent_items if not is_pr_role(item)]
    if urgent_general:
        urgent_html = render_table(urgent_general, "URGENT — Confirmed-sponsored jobs closing within 3 days", errors=errors)
        send(f"URGENT: Confirmed visa-sponsored vacancies closing soon — {local_today().strftime('%d %b %Y')}", urgent_html, audience="main")
    if urgent_pr:
        urgent_pr_html = render_table(urgent_pr, "URGENT — PR & Communications roles closing within 3 days", errors=errors)
        send(f"URGENT: PR/Communications vacancies closing soon — {local_today().strftime('%d %b %Y')}", urgent_pr_html, audience="pr")

    today = local_today()
    if today.weekday() == 6 and state.get("last_weekly_summary") != today.isoformat():
        week_cutoff = (today - timedelta(days=7)).isoformat()
        weekly_items = [v for v in jobs.values() if (v.get("first_seen") or "0000-00-00") >= week_cutoff and v.get("weekly_eligible", False)]
        deduped = {v.get("id") or v.get("link"): v for v in weekly_items}
        weekly_all = list(deduped.values())
        weekly_pr = [item for item in weekly_all if is_pr_role(item)]
        weekly_general = [item for item in weekly_all if not is_pr_role(item)]
        weekly_html = render_table(weekly_general, "Weekly Job Search Summary — Last 7 Days", excluded, errors)
        send(f"Weekly Job Search Summary — {today.strftime('%d %b %Y')} — {len(weekly_general)} opportunities", weekly_html, audience="main")
        weekly_pr_html = render_table(weekly_pr, "Weekly PR & Communications Job Summary — Last 7 Days", excluded, errors)
        send(f"Weekly PR & Communications Summary — {today.strftime('%d %b %Y')} — {len(weekly_pr)} opportunities", weekly_pr_html, audience="pr")
        state["last_weekly_summary"] = today.isoformat()
        for item in weekly_items:
            key = item.get("id")
            if key in jobs:
                jobs[key]["weekly_eligible"] = False

    save_state(state)
    print(f"Candidates verified: {len(results)}; new: {len(new_items)}; updated: {len(updates)}; PR/communications digest: {len(pr_digest_items)}; excluded: {excluded}; warnings: {len(errors)}")

if __name__ == "__main__":
    main()
