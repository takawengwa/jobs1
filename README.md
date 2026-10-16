# Daily Job Alerts — direct source checks + search discovery

## Recipients and schedule
- **Daily general digest:** 11:10 Africa/Harare (09:10 UTC), to `takaengwa@gmail.com`.
- **PR / public relations / communications / corporate affairs digest:** to `telmamtoko@gmail.com`, with `takaengwa@gmail.com` CC'd. PR roles are intentionally excluded from the general digest and matched against Telma Mtoko’s attached Communications Specialist CV, not Emmanuel’s IT/data CV.
- **Sunday weekly summaries:** separate general and PR summaries, routed to the same recipients above.
- **Urgent alerts:** confirmed-sponsored vacancies with a detected deadline within 3 days and CV score >= 5. PR roles use the PR distribution.
- Sender: Gmail SMTP using `GMAIL_ADDRESS` and `GMAIL_APP_PASSWORD` GitHub Actions secrets.

## Search coverage
The workflow now combines Google News RSS discovery with direct requests to current vacancy-listing pages for:
- [VacancyMail](https://www.vacancymail.co.zw/jobs/)
- [ZimboJobs](https://www.zimbojobs.com/jobs)
- [IPC Jobs](https://www.ipcjobs.org/)
- [IPC Consultants](https://www.ipcconsultants.com/jobs)
- [Jobs Zimbabwe](https://jobszimbabwe.co.zw/jobs/?display=list)
- [Recruitment263](https://recruitment263.co.zw/jobseekers)
- [ZimJobSite](https://www.zimjobsite.com/jobs)
- [ZimJobsHub](https://zimjobs.online/)
- [Public Service Commission eRecruitment](https://erecruitment.psc.gov.zw/)

The direct checks extract relevant IT/ICT, software/systems, data/BI/analytics, and PR/communications/corporate affairs links from listing pages, then fetch the individual advert for deadline and status screening. Search engine discovery remains as a second layer for LinkedIn, employer career pages, remote roles, and listings missed by source-page extraction. International discovery now also targets Ireland (IrishJobs, Jobs.ie, Indeed and Critical Skills Employment Permit wording), Canada (official Job Bank postings for foreign candidates / temporary foreign workers and LMIA signals), Germany (Make it in Germany, Federal Employment Agency job search, EU Blue Card/skilled-worker visa wording), job searches for Norway, Denmark, Switzerland, Luxembourg and Liechtenstein; UK searches targeting IT/software, data/BI and Telma PR/communications roles with Skilled Worker / sponsorship signals; and African regional searches excluding South Africa, covering IT/software, data/BI, PR/communications, regional NGOs and international-development employers, plus remote roles advertised as open to African applicants. African searches include country and regional terms for East, West, North, Central and non-South-African Southern Africa. Added targeted discovery for UNICEF, WHO, UNDP, the African Union, UN agencies, World Bank Group, African Development Bank, USAID/US Government opportunities and contractors/implementing partners, plus international NGOs and humanitarian/development organisations. Search categories separate IT/ICT, data/MEAL/information management, and PR/communications so the latter continues to route to Telma. These international sources are discovered through targeted search queries; they are not all scraped directly, and each individual advert still requires verification.

**Coverage limitation:** direct HTTP checks are best-effort. A site can block automated requests, use JavaScript that does not expose listings to this scraper, change its page structure, require login, or paginate beyond the pages checked. Logs report direct-source counts and errors; the email warns when checks fail. This is broader than Google News alone but is not a guarantee of exhaustive coverage. Official employer adverts remain the preferred source of truth.

## Additional discovery starting points
- United Kingdom: [GOV.UK Skilled Worker visa](https://www.gov.uk/skilled-worker-visa) and [official work visas / sponsor guidance](https://www.gov.uk/browse/visas-immigration/work-visas). A sponsor licence alone does not prove a specific vacancy will sponsor a candidate; the advert and employer must be checked.
- Pan-African and country-level discovery: [ReliefWeb Jobs](https://reliefweb.int/jobs), [Impactpool](https://www.impactpool.org/jobs), [Devex Jobs](https://www.devex.com/jobs), [BrighterMonday](https://www.brightermonday.co.ke/), [Jobberman](https://www.jobberman.com/), and [AfriqueJob country-by-country guide](https://www.afriquejob.com/en/). These are search starting points, not a guarantee of complete country coverage.

## Non-profit, multilateral and development-sector discovery starting points
- [UNICEF Careers](https://jobs.unicef.org/)
- [WHO Careers](https://www.who.int/careers)
- [UNDP Jobs](https://www.undp.org/careers)
- [UN Careers](https://careers.un.org/)
- [UNjobs](https://unjobs.org/)
- [African Union Careers](https://au.int/en/careers)
- [World Bank Group Careers](https://www.worldbank.org/en/about/careers)
- [African Development Bank Careers](https://www.afdb.org/en/about-us/careers)
- [USAID Careers](https://www.usaid.gov/careers) and [USAJOBS](https://www.usajobs.gov/) for US federal roles. Some US federal vacancies require US citizenship or existing work rights; the workflow must not assume eligibility.
- [ReliefWeb Jobs](https://reliefweb.int/jobs), [Impactpool](https://www.impactpool.org/jobs), and [Devex Jobs](https://www.devex.com/jobs) for NGO, humanitarian and development-sector vacancies.

These links are starting points for manual verification. The workflow searches indexed job announcements and does not scrape or guarantee full coverage of each organisation's official career portal. For USAID/USG-funded implementers, the employer is often a contractor or partner rather than the US government itself; verify the actual employer and eligibility in the original notice.

## International discovery starting points
- Ireland: [IrishJobs](https://www.irishjobs.ie/), [Jobs.ie](https://www.jobs.ie/), [official Critical Skills Occupations List](https://enterprise.gov.ie/en/what-we-do/workplace-and-skills/employment-permits/employment-permit-eligibility/highly-skilled-eligible-occupations-list/critical%20skills%20occupations%20list.html).
- Canada: [Job Bank — temporary foreign workers](https://www.jobbank.gc.ca/temporary-foreign-workers), [Job Bank — foreign candidates outside Canada](https://www.jobbank.gc.ca/trouverunemploi/candidats-etrangers), [official employer-specific work permits](https://www.canada.ca/en/immigration-refugees-citizenship/services/work-canada/employer-specific.html).
- Germany: [Make it in Germany](https://www.make-it-in-germany.com/en/), [Federal Employment Agency job search](https://www.arbeitsagentur.de/jobsuche/).
- Norway: [Work in Norway](https://www.workinnorway.no/).
- Denmark: [Workindenmark](https://www.workindenmark.dk/).
- Switzerland: [jobs.ch](https://www.jobs.ch/).
- Luxembourg: [Jobs.lu](https://www.jobs.lu/).
- Liechtenstein: [Liechtenstein Public Employment Service (AVAM/ALV)](https://www.amsfl.li/).

These links are included as discovery resources. The script's Google News RSS queries do not guarantee full indexing of every portal.

## Search scope
- Zimbabwe: IT/ICT/support, software/systems, data/BI/analytics, PR/public relations/communications/corporate affairs/media relations/public affairs.
- Remote: roles where advert text indicates applicants working from Zimbabwe or a wider eligible region may apply. Location restrictions are screened out when detected.
- United Kingdom: IT/software, data/BI, and PR/communications/corporate affairs roles with Skilled Worker / sponsorship indicators. The official UK rules require an eligible job and approved employer, with a Certificate of Sponsorship; search wording is not proof of eligibility.
- Africa excluding South Africa: IT/software, data/BI, PR/communications/corporate affairs, regional NGO/development roles, and remote vacancies that may be open to African applicants. Dedicated queries also cover UNICEF, WHO, UNDP, African Union, UN agencies, World Bank Group, African Development Bank, USAID/USG-related opportunities, implementing partners, and international NGOs/humanitarian organisations. This is discovery coverage rather than direct integration with every employer portal. Cross-border work authorization must be checked for each country.
- Australia and New Zealand: IT/software, data/BI, and PR/communications/corporate affairs roles with sponsorship classification.
- International recruitment / work-permit discovery: Ireland, Canada, Germany, Norway, Denmark, Switzerland, Luxembourg and Liechtenstein. Queries target permit pathways and employer wording such as Ireland's Critical Skills Employment Permit, Canada's Job Bank foreign-candidate/LMIA indicators, Germany's skilled-worker/EU Blue Card language, and relevant country-specific work-permit terms. This is a discovery signal, not a guarantee that an employer is authorised or willing to sponsor a specific applicant.
- All career levels, including graduate, junior, officer, specialist, senior and management roles.

## Sponsorship / work-permit policy
- **Confirmed:** explicit sponsorship wording on an accessible original advert; not a guarantee of visa approval. Country-specific signals such as a Critical Skills Employment Permit, LMIA, EU Blue Card, Positive List or Pay Limit Scheme are surfaced for manual verification and are not automatically treated as confirmed employer sponsorship.
- **Potential:** advert is silent or mentions visa/relocation/accredited-employer support without an explicit sponsorship offer. Ask the employer.
- **Unavailable:** explicit no-sponsorship or incompatible existing-work-rights restrictions are detected; listing is excluded.
- **Unverified:** original advert could not be checked or sponsorship wording appears only in search results.
- Search snippets alone never count as confirmed sponsorship and never trigger urgent sponsorship alerts.

## Deadline checks and deduplication
- Follows redirects, fetches destination pages, extracts visible text, detects closed wording and common deadline formats.
- Expired deadlines and explicitly closed listings are excluded. Missing dates are labelled `Not stated — verify active status` unless `REQUIRE_FUTURE_DEADLINE=true` is set.
- Direct source listings may not expose publication dates; these are marked `Not stated (direct source listing)` rather than inventing a date.
- Deduplicates by canonical URL and normalized title; state is retained for up to 60 days through GitHub Actions cache. Cache persistence is best-effort, so listings may recur if GitHub evicts the cache.

## CV matching
General IT/data/remote roles are matched against Emmanuel's IT/data CV. Public relations, communications, media relations, marketing, commercial production and corporate affairs roles are routed only to Telma's PR digest and matched against Telma Mtoko's attached Communications Specialist CV. Her profile includes 7 years of communications/PR/graphic design/commercial production experience; ZTN Commercial Producer (Jul 2022–present), ZBC Producer (Apr 2017–May 2018), Junior Manager & Public Relations Officer (Dec 2018–Mar 2019), an MA in Multimedia Production Designs and Systems, and a BSc Honours in Creative Art & Design. Scores are screening aids, not determinations of eligibility or qualification.

## Setup
1. Extract this ZIP and upload its contents to the root of your private GitHub repository, preserving `.github/workflows/daily-job-alerts.yml`.
2. Under **Settings → Secrets and variables → Actions**, create `GMAIL_ADDRESS` and `GMAIL_APP_PASSWORD` for the Gmail account that sends the messages.
3. Recipient routing is set in the workflow: `EMAIL_TO=takaengwa@gmail.com`, `PR_EMAIL_TO=telmamtoko@gmail.com`, `PR_EMAIL_CC=takaengwa@gmail.com`.
4. Enable Gmail 2-Step Verification and create an App Password at https://myaccount.google.com/apppasswords. Do not use your normal Gmail password.
5. Open **Actions → Daily Job Alerts → Run workflow**. Inspect the logs for direct-source counts and errors; confirm emails arrive in the correct inboxes.
6. Keep the workflow enabled. Scheduled GitHub Actions runs can be delayed.

## Important
The package is not deployed until you upload it and configure secrets. It does not claim live email delivery. Always verify the original employer advert and immigration requirements before applying. Never commit credentials.
