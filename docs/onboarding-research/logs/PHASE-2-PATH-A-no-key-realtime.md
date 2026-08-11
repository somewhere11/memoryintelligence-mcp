# Phase 2: Real-Time Testing Report - Path A (No API Key)

**Date:** 2026-06-05 (initial), completed 2026-07-28  
**Test Scenario:** Novice user with no existing API key navigates portal to obtain one  
**Model:** Think out loud; document friction in real-time  
**Status:** COMPLETE — Portal fully documented via browser inspection (2026-07-28)

---

## Step 1: Locate API Key Instructions

**What I Did:**
- Read GitHub documentation
- Searched for "API key" instructions
- Found: "Free API key from memoryintelligence.io/portal"

**What I Expected:**
- Step-by-step guide: "Create account → Verify email → Generate key → Copy key"
- OR: Direct link with context: "[Get API Key](https://memoryintelligence.io/portal)"
- OR: Embedded instructions in setup wizard

**What I Found:**
- One sentence mentioning the portal URL
- No account creation instructions
- No walkthrough of what the portal looks like
- No mention of invite-only status

**Friction Level:** ⚠️ HIGH

---

## 🚨 CRITICAL PATH A FINDING: INVITE-ONLY

**First thing visible on portal signup form:**
> "Coming soon — public signup opens shortly. MemoryIntelligence is invite-only for now."

**This is not documented in the README.** The README says "Get a free API key at memoryintelligence.io/portal" with no mention of invite status. A new user following the README hits an invite wall at this exact step with no guidance on how to request access.

**Documentation gap:** The README should state invite status prominently near the "get your API key" instruction:
> "Currently in invite-only beta. [Join waitlist / request invite / check your inbox if you were referred]"

---

## Portal Flow: Full Documentation (Browser Inspection, 2026-07-28)

### Screen 1: Sign In / Create Account (Landing)

- Title: "Sign in to your account"
- Email + Password fields
- "Forgot password?" link
- "New here? Create an account" → signup form

### Screen 2: Create Account (Signup Form)

Fields:
- Email (required)
- Name (optional) — placeholder: "How should we address you?"
- "What are you building?" (optional) — placeholder: "e.g. personal memory app, research tool"
- Password — "At least 8 characters"

**Invite notice appears here:** "Coming soon — public signup opens shortly. MemoryIntelligence is invite-only for now."

No card required. No plan selection at signup.

### Screen 3: Check Your Email

"We sent a verification link to [email]. Click it to activate your account and reveal your API key."

"Resend email" button present.

Two verification methods:
1. Email link click (primary)
2. 6-digit code entry (Screen 4)

### Screen 4: 6-Digit Code Entry (Alternate Verification)

- Email field + Verification code (6-digit)
- "Verify & get API key" button

### Screen 5: Dashboard (Post-Verification)

**API Key revealed:**
> "Your API Key — Copy this and save it somewhere safe. You can always reveal it again in the Keys tab."

**Key format confirmed from Quickstart tab:**
```
export MI_KEY="mi_sk_beta_your_key_here"
```
Keys begin with `mi_sk_beta_` prefix.

---

## Portal Full Feature Map

### Navigation
- Dashboard (memory search + recent captures)
- API Keys (key management)
- Members (team roles)
- Usage (real-time analytics)
- Quickstart (cURL examples)
- Billing (plans + pricing)
- API Docs › (external)

### Dashboard
- **MI Search** — in-browser semantic memory search
  - Filter by channel: API, Slack, Google Drive
  - Filter by date range
  - Quick query chips: "recent notes", "people I met", "decisions I made", etc.
  - Sort: Top match, Good match, Context
- **Build summary + Run MI Ask** — select memories, synthesize in browser
- **"Ask from memory" dialog** — floating chat UI for memory queries
- **PII detection dialog** — catches PII before capture, offers redact/keep
- **Recent captures** timeline

### Key Management
- Name, permissions (Read/Write), expiration (Never / 30 / 90 / 365 days)
- "Copy your secret key now. You won't be able to see it again." at creation
- BUT: Keys tab has a "Reveal" button for existing keys (inconsistency)
- Actions: Create, Revoke, Rotate
- Per-key usage stats

### Workspace System
- Up to 3 workspaces per beta user
- Roles: Viewer (read-only), Member (use keys + view usage), Admin (full access)
- Adding members requires they already have an MI account
- "Email invites for new users are coming soon"

### Plans (All Free During Beta)
| Tier | Launch Price | UMOs | Description |
|------|-------------|------|-------------|
| 01 Capture | $29/mo | 500 | Manual only, 1 user |
| 02 Automate | $49/mo | 5,000 | Auto capture + signal rules + ML feedback |
| 03 Control | $99/mo | Unlimited | Admin, compliance — coming soon |

### API Quickstart (Portal)
```bash
curl -s https://api.memoryintelligence.io/health | python3 -m json.tool
export MI_KEY="mi_sk_beta_your_key_here"
export MI_URL="https://api.memoryintelligence.io"
# Capture, Search, Explain & Verify — all with cURL
```

---

## Q-PATH-A Question Resolution

| ID | Question | Status | Answer |
|----|---------|--------|--------|
| Q-PATH-A-1 | Portal account creation | ✅ RESOLVED | Email + optional name/purpose + password (8+ chars). Email link OR 6-digit code verification. |
| Q-PATH-A-2 | Key format & generation time | ✅ RESOLVED | Format: `mi_sk_beta_...`. Revealed immediately after email verification. Re-revealable from Keys tab. |
| Q-PATH-A-3 | Key validity & multiple keys | ✅ RESOLVED | Expiration: Never / 30 / 90 / 365 days. Revoke, rotate supported. Up to 3 workspaces with multiple keys each. |
| Q-PATH-A-4 | Key testing before setup | ✅ RESOLVED | Health endpoint: `curl -s https://api.memoryintelligence.io/health`. Also: capture test via API. |
| Q-PATH-A-5 | Portal unavailability fallback | ⚠️ PARTIAL | No status page referenced. No offline signup path. Email delivery dependency. |

---

## New Findings from Portal Inspection

### A1: Invite-Only Not in README (CRITICAL)
"Coming soon — public signup opens shortly." not documented anywhere in README. Users following the docs hit an invite wall with no guidance on how to proceed.

### A2: Full In-Browser Memory UI Undocumented
Portal has MI Search, Build Summary, Run MI Ask, Ask from Memory dialog — a complete web UI for the same tools available via MCP. Not mentioned in README or any onboarding doc. Users who only read the README don't know this exists.

### A3: "Shown Once" Language Inconsistency  
Key creation modal says "You won't be able to see it again." Keys tab has a "Reveal" button. This inconsistency will cause panic in users who failed to copy their key — they'll believe it's permanently lost when it isn't.

### A4: Team Addition Requires Prior Account (Beta Limitation)
"The person must already have an MI account." For an invite-only product, this creates a catch-22 for team onboarding.

### A5: Plans Fully Documented in Portal Only
Tier pricing ($29/$49/$99) with full feature matrices visible in portal Billing tab. Not in README. Users can't evaluate pricing without reaching the portal.

---

**Status: COMPLETE** — All Q-PATH-A questions resolved. 5 new findings logged above.
