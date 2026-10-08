# WOW Beacon — Problem Statement

**Who Owns What · People Finder** · Hackathon submission

---

## 1. Problem Statement

Employees regularly need to find **the right person for a project**: who owns it, what their role is, which team they're on, where they sit, and whether they're available. Today that knowledge is spread across wikis, spreadsheets, org charts, Slack channels and word of mouth. No single place answers *"who do I talk to about X, and can I reach them now?"*

As a result, people:

- **Waste time asking around.** They post "does anyone know who owns X?" in #general, wait for replies, and get pointed from person to person.
- **Message the wrong or unavailable person.** They find a contact, then learn they're on MC or annual leave for a week, because leave status isn't visible anywhere they look.
- **Can't find people physically.** Even with a name, nobody knows which floor or desk the person sits at, so in-person collaboration is slow.
- **Rely on knowledge that goes stale.** Project and role ownership changes faster than wikis get updated, and new joiners suffer most.

> *"I found the right person, messaged them, then discovered they're on leave for a week. No-one told me."*

**In one line:** there is no single, trusted, self-service way to find *who owns what, where they sit, and whether they're available*. Every lookup costs time and interrupts other people.

---

## 2. Business Objectives

| # | Objective | Why it matters |
|---|-----------|----------------|
| BO1 | **Cut the time spent finding the right contact** for any project, role or team | Gives engineering, product and ops time back; fewer interruptions in shared channels |
| BO2 | **Make availability visible before people reach out** (on leave / MC / back tomorrow) | Fewer dead-end messages and blocked work; escalations go to someone who's in |
| BO3 | **Speed up in-person collaboration** with a desk and zone lookup on a real floor plan | People can walk over instead of messaging into the void; helps hybrid and office days |
| BO4 | **Shorten onboarding** for new joiners and cross-team movers | New staff can work out the org on their own from day one |
| BO5 | **Keep the directory easy to keep up to date** with a natural-language leave page and team leave for leads and HR | Keeping records current takes seconds, so data stays fresh without heavy HR process |
| BO6 | **Ship with no integration dependencies and very low running cost** (CSV / Google Sheet data, serverless AWS, under $5/month) | Can go live quickly without app approvals or system access; low risk to try out |

---

## 3. Success Criteria

### Hackathon (demo-day) criteria

| # | Criterion | Target |
|---|-----------|--------|
| SC1 | A natural-language search ("FE dev for ACE") returns the correct person card | Correct top result for **≥ 9 of 10** scripted demo queries |
| SC2 | The result card shows name, role, project, team, floor and desk, zone, Slack link and availability badge | All fields filled in for **100%** of seeded people |
| SC3 | Clicking a result pins the exact desk on the floor plan and highlights the zone | Works across **all seeded floors** |
| SC4 | The leave page understands plain-language leave ("MC today", "off 21 to 25 Sep") and shows a preview before saving | **≥ 90%** of test phrases parsed correctly; date pickers work when the AI can't parse |
| SC5 | Leads and HR can mark a teammate or a whole team on leave, and non-leads are blocked | Role check enforced; bulk update reflected on all affected cards |
| SC6 | **End-to-end live demo:** search → 🟢 Available → leave entered on the web → re-search → 🔴 On leave | Works live in two browser windows with no manual data fix |
| SC7 | Performance | Search response **< 2 s** at the 95th percentile, including the AI call (**< 300 ms** with keyword fallback) |
| SC8 | Runs on serverless AWS with one deployable stack | Deploys with one `sam deploy`; idle cost **< $5/month** |

### Post-pilot (business) criteria

These are proposed targets to confirm with stakeholders.

| # | Metric | Target after a 4–6 week pilot |
|---|--------|------------------------------|
| PC1 | Median time to find the right contact | **From minutes to under 30 s** (pilot survey plus timed tasks) |
| PC2 | "Who owns X?" posts in shared Slack channels | **↓ 50%** compared with the baseline |
| PC3 | Adoption | **≥ 60%** of pilot employees search at least once a week |
| PC4 | Leave data freshness | **≥ 80%** of leave entered in Beacon before or on the day it starts |
| PC5 | Directory accuracy | **≥ 95%** of records confirmed current in the last 90 days |
| PC6 | User satisfaction | **CSAT ≥ 4 / 5** or NPS > 30 from pilot users |

---

## 4. Classification

| Dimension | Classification |
|-----------|----------------|
| **Hackathon track / category** | Employee Productivity & Internal Tools (Employee Experience) |
| **Problem type** | Knowledge discovery / information findability (people ↔ projects ↔ roles ↔ seats ↔ availability) |
| **Solution type** | Internal web application (self-service directory) with a GenAI assist |
| **AI usage** | Generative AI / NLP: natural-language query → structured filters, and natural-language leave → structured dates (Amazon Bedrock, Claude Haiku). Keyword and date-parser fallback if the AI is unavailable. **The AI only suggests; the user confirms before anything is saved.** |
| **Primary users** | All employees (search); team leads and HR (team leave updates); admins (data upload, desk mapping) |
| **Impact area** | Productivity (time saved), collaboration, onboarding, hybrid workplace |
| **Data classification** | **Internal / Confidential.** Employee name, role, team, project, desk, Slack handle and leave *dates* only. No leave *reason*, medical or HR records stored ("MC" is shown only as an on-leave status). Access limited to employees through SSO. |
| **Architecture** | Serverless AWS: S3 + CloudFront, API Gateway, Lambda, DynamoDB, Bedrock, Cognito/SSO |
| **Integration dependency** | None for the MVP (CSV / Google Sheet data). Slack bot and calendar/HR sync are future extensions. |
| **Maturity at end of hackathon** | Working MVP / pilot-ready prototype |
| **Risk level** | Low: read-heavy, internal-only, no writes to systems of record, human-confirmed AI actions |
