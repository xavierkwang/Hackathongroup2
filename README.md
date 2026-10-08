# 🛰️ WOW Beacon — Who Owns What · People Finder

Ask a question like **"FE dev for ACE"** or **"who developed the MCC platform?"** and Beacon answers with:

1. **Who** owns or works on it: name, role, team, projects (owners flagged), Slack and email.
2. **Where** they sit: floor, desk and zone, with the desk pinned on a live floor plan.
3. **Whether they're in**: 🟢 Available · 🟡 In a meeting until 3:30 pm · 🔴 On leave, back Mon 12 Oct. This combines leave records with Outlook free/busy.

People keep their own leave current by typing it in plain language ("MC today", "off 21 to 25 Oct"). They see a preview before saving. Leads and HR can mark a teammate or a whole team at once.

> Built for the hackathon brief in [`docs/problem-statement.md`](docs/problem-statement.md).

---

## Run it in your browser (GitHub Codespaces, nothing to install)

1. On the repo page, click **Code → Codespaces → Create codespace on main**.
2. Wait 2–3 minutes for setup. The app starts by itself and opens in a new tab.
   If it doesn't, open the **Ports** tab and click the 🌐 globe next to port **5173**.

## Quick start (local, no AWS needed)

```bash
pip install tzdata          # Python 3.11+
./scripts/dev.sh            # API on :8787, web on http://localhost:5173
```

Use **Demo as** (top right) to switch users. Each browser tab keeps its own user, so you can run the two-window demo on one laptop.

| Demo user | Access |
|---|---|
| Aisha Rahman | Employee (Atlas, ACE frontend) |
| Daniel Ong | **Lead** of Atlas |
| Marcus Lee | **Lead** of Platform |
| Nadia Yusof | **HR** (any team) |
| Yvonne Tay | **Admin** (CSV upload) |

`./scripts/dev.sh --reset` wipes local leave and reseeds. Local mode uses the keyword search and date parser. To try Bedrock locally, run with `BEACON_AI=on` and AWS credentials that can call Bedrock.

## The demo script (SC6)

1. Open **Window A** as *Marcus* and ask **"FE dev for ACE"**. You get Aisha 🟢 Available, and her desk is pinned on Level 5 in the Atlas Zone.
2. Open **Window B** as *Aisha*. Go to **My leave**, type **"MC today"**, click **Preview**, then **Confirm leave**.
3. In **Window A**, ask again. Aisha now shows 🔴 **On leave · back tomorrow**, and Beacon suggests who else is available.
4. Bonus: as *Daniel* (lead), go to **Team leave** and mark the whole Atlas team. Every Atlas card turns red. Try the same as *Aisha*: she can't see that tab, and the API returns 403.

---

## Architecture

```
Browser (React SPA) ──► CloudFront ──► S3 (static site, floors.json)
      │
      └─ Bearer id_token ──► API Gateway (HTTP API, Cognito JWT authorizer)
                                   │
                                   ▼
                         Lambda  beacon.app.handler  (one function, Python 3.12, arm64)
                           ├── search.py          NL → filters → ranked people
                           ├── ai.py              Bedrock Claude Haiku (2 s timeout, then fallback)
                           ├── leave_parser.py    NL leave → dates (AI first, rules fallback)
                           ├── availability.py    leave + free/busy → badge
                           ├── calendar/          mock | Microsoft Graph getSchedule
                           └── store.py           DynamoDB (people, leave)
```

| Brief requirement | Where |
|---|---|
| NL search → person card (SC1, SC2) | `backend/src/beacon/search.py`, `frontend/src/components/PersonCard.jsx` |
| Desk pin + zone highlight on every floor (SC3) | `frontend/src/components/FloorPlan.jsx`, `frontend/public/floors.json` |
| NL leave + preview + date pickers (SC4) | `backend/src/beacon/leave_parser.py`, `frontend/src/components/LeaveComposer.jsx` |
| Lead / HR team leave, non-leads blocked (SC5) | `backend/src/beacon/auth.py`, `app.py → r_leave_team` |
| Live two-window flow (SC6) | Leave is never cached, so the next search reflects it |
| < 2 s with AI, < 300 ms fallback (SC7) | Bedrock read timeout of 2 s, then keyword search; latency is returned in every search response |
| One `sam deploy`, idle < $5/month (SC8) | `template.yaml`: everything is pay-per-request; no NAT, no always-on compute |
| No leave reasons stored | Only `start`, `end`, `portion` are stored; "MC" is parsed and discarded |

### How "AI suggests, human confirms" works
- **Search:** Bedrock only turns the question into filters (`projects`, `roles`, `owner`…). The ranking is deterministic code that both paths share, so results are explainable. If Bedrock is slow, fails, or returns nothing usable, the keyword interpreter takes over.
- **Leave:** the model or the parser only fills in the preview. Nothing is written until the user clicks **Confirm**. Dates are validated server-side: end after start, at most 90 days, within a year of today, and half days only on a single date.

---

## Deploy to AWS

Prerequisites: AWS CLI, [SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html), Node 18+, Python 3.12, and access to a Claude Haiku model in the Bedrock console for your region.

```bash
# 1. Set a globally unique Cognito domain prefix in samconfig.toml, then:
SEED_USERS=1 ./scripts/deploy.sh
```

This runs `sam build && sam deploy` (one stack), builds the React app against the stack outputs, uploads it to S3, invalidates CloudFront, and loads `data/people.csv` into DynamoDB. `SEED_USERS=1` also creates a Cognito user per person, prints temporary passwords, and adds leads, HR and admins to their groups.

**Bedrock model:** the default is `anthropic.claude-3-haiku-20240307-v1:0`. If that model isn't offered in your region, set `BedrockModelId` to a cross-region inference profile your account has enabled, such as an `apac.` profile. Check the Bedrock console for the exact ID.

**Corporate SSO:** add your SAML or OIDC identity provider to the Cognito user pool and enable it on the app client. The frontend doesn't change. Map your directory groups to the `lead`, `hr` and `admin` Cognito groups.

### Running cost (idle → light pilot)
All of these are pay-per-request: Lambda, HTTP API, DynamoDB on-demand, Bedrock per token, and Cognito (free tier covers a pilot). The only fixed costs are S3 storage and CloudFront at a few cents. Fewer than 50k searches a month stays well under **$5/month**.

---

## Outlook calendar

`CALENDAR_PROVIDER` picks the free/busy source:

| Value | What it does | Needs |
|---|---|---|
| `mock` (default) | Weekly busy patterns from `backend/src/beacon/data/calendar_mock.json` | Nothing |
| `graph` | Microsoft Graph `getSchedule`: real Outlook free/busy, **no meeting titles** | Entra ID app with `Calendars.ReadBasic.All` (application) and admin consent, ideally limited by an Exchange Application Access Policy. Put the client secret in Secrets Manager and set the `GraphTenantId`, `GraphClientId` and `GraphClientSecretArn` parameters. |
| `none` | Leave records only | Nothing |

If Graph fails, search still works and availability falls back to leave data alone.

---

## Your data

- **People:** `data/people.csv` (or **Admin → Update the directory**). Columns:
  `id,name,email,role,team,projects,owns,skills,floor,desk,zone,slackHandle,slackUserId,accessRole`.
  Separate list values with `;`. `owns` lists the projects this person owns, which drives "who owns X?". `accessRole` is only used in local mode; in AWS, roles come from Cognito groups.
- **Floor plans:** `frontend/public/floors.json`. Each floor has zones (rectangles) and desks (points) on its own canvas. `scripts/gen_floors.py` generates the demo plans. Desk IDs must match the CSV, and the tests check this.
- **Meeting rooms (Level 9):** rooms in `backend/src/beacon/data/rooms.json`, bookings in
  `backend/src/beacon/data/room_bookings.csv` (`bookingId,room,day,start,end,bookedBy,title,attendees`).
  `day` is a weekday (`Mon`…`Fri`, repeats every week) or an ISO date for a one-off. People in a booked
  room show as 🟡 *In St John until 4 pm*. Ask the chatbot "who booked St John?" or "any free meeting room?",
  or open the **Meeting rooms** tab for the day's timeline.
- **Slack links:** set `VITE_SLACK_TEAM_ID` (or `SLACK_TEAM_ID` when deploying) to open DMs directly in your workspace.

## Tests

```bash
pip install -r backend/requirements-dev.txt
pytest backend/tests -q
```

| Test | Checks |
|---|---|
| `test_search.py` | **SC1**: 10 scripted demo queries return the correct top result (currently 10/10). **SC2/SC3**: every seeded person has all card fields and a desk that exists on the floor plan, in the right zone. |
| `test_leave_parser.py` | **SC4**: 21 plain-language phrases parse correctly (currently 21/21), and unparseable text falls back to date pickers. |
| `test_leave_flow.py` | **SC5**: role checks for leads, HR and non-leads, and team updates reflected on every card. **SC6**: the full search → leave → re-search flow. Also back dates that skip weekends, overlaps, and admin-only upload. |

## Project layout

```
template.yaml            one SAM stack (SC8)
samconfig.toml           deploy settings
backend/src/beacon/      Lambda code (no third-party deps beyond tzdata)
backend/local_server.py  same handler on localhost, JSON-file store
backend/tests/           pytest suite mapped to the success criteria
frontend/                React + Vite SPA
data/people.csv          seed directory (24 fictional people, 5 projects, 2 floors)
scripts/                 dev.sh, deploy.sh, seed.py, gen_floors.py
docs/                    problem statement
```

## Roadmap (post-hackathon)
- Slack bot: `/beacon FE dev for ACE` using the same `/api/search`.
- HR system leave sync, which replaces manual entry for pilot metric PC4.
- Public-holiday calendar for "back on" dates.
- "Confirm my record" nudges every 90 days to keep the directory accurate (PC5).
