# Parsonic Roadmap

Organized by value — highest impact features first.

---

## ✅ Completed (v1.0)

- [x] Visual selector builder with live browser preview
- [x] AI-powered field detection (AI Analyze button)
- [x] Multi-page selector accumulation (run AI Analyze on different pages)
- [x] Smart crawling with multiple link selectors (pagination + detail links)
- [x] Result persistence across sessions
- [x] Auto-validation (filters entries without company/phone/email/address)
- [x] Data sanitization (strips mailto:, tel:, normalizes whitespace)
- [x] Thermal safety monitoring (pauses AI when GPU/CPU hot)
- [x] CSV/JSON export
- [x] Stealth mode (anti-detection for Playwright)
- [x] Rate limiting with adaptive delays

---

## 🔥 Tier 1: Highest Value
*Game-changing features that differentiate Parsonic*

### 1. "Just Scrape It" — Autonomous Mode
> Paste a URL. Get data. Zero configuration.

- [ ] Auto-detect page type (listing vs detail page)
- [ ] Auto-discover pagination (find "Next" buttons)
- [ ] Auto-find all business fields without manual setup
- [ ] Sample multiple pages to learn site structure
- [ ] One-click scraping for common directories (Yelp, Yellow Pages, etc.)

**Value:** Eliminates the learning curve. Anyone can scrape anything.

---

### 2. CLI & REST API
> Programmatic access for automation and integration

- [ ] **CLI tool**: `parsonic scrape https://example.com -o results.csv`
- [ ] **REST API**: `POST /scrape {url, fields}` → returns JSON
- [ ] **Python SDK**: `parsonic.scrape(url, fields=['company_name', 'phone'])`
- [ ] **Docker image**: Headless mode for servers

**Value:** Enables automation, cron jobs, integration with any system.

---

### 3. Google Sheets Live Sync
> Results appear in a spreadsheet instantly

- [ ] Connect Google account (OAuth)
- [ ] Select or create target spreadsheet
- [ ] Auto-append new results as rows
- [ ] Real-time sync (no manual export)

**Value:** Most users live in spreadsheets. This is where they want data.

---

### 4. Incremental Scraping
> Only scrape new/changed listings

- [ ] Track previously scraped URLs
- [ ] Detect new listings since last run
- [ ] Detect changed data (updated phone, address, etc.)
- [ ] "Changes only" export mode
- [ ] Freshness timestamps per record

**Value:** 10x faster for monitoring jobs. Saves hours on repeat scrapes.

---

### 5. Learning from Corrections
> AI gets smarter when you fix mistakes

- [ ] Track when user edits AI-detected fields
- [ ] Learn patterns from corrections
- [ ] Apply learnings to similar pages
- [ ] Per-domain memory (remember site-specific fixes)
- [ ] Export/import learned patterns

**Value:** AI improves over time. Less manual work each session.

---

## 🎯 Tier 2: High Value
*Significant improvements to capability and data quality*

### 6. Visual AI (Screenshot Analysis)
> Use vision models to understand pages visually

- [ ] Capture page screenshot
- [ ] Send to vision model (GPT-4V, LLaVA, Claude)
- [ ] "Find the phone number in this image"
- [ ] Works even with obfuscated HTML
- [ ] Fallback when CSS selectors fail

**Value:** Works on sites where traditional scraping fails.

---

### 7. Data Enrichment Pipeline
> Enhance scraped data automatically

- [ ] **Phone validation** — Verify numbers are active (Twilio/Numverify)
- [ ] **Email verification** — Check deliverability (ZeroBounce/Hunter)
- [ ] **Address geocoding** — Convert to lat/long (Google/Mapbox)
- [ ] **Company enrichment** — Fetch LinkedIn, website, employee count
- [ ] **Social profiles** — Find Twitter, Facebook, Instagram

**Value:** Clean, verified, enriched data is worth 10x raw scraped data.

---

### 8. Webhooks & Real-time Push
> Send data anywhere instantly

- [ ] Configure webhook URL per project
- [ ] POST each result as JSON in real-time
- [ ] Retry logic for failed deliveries
- [ ] Batch mode (send N results at once)
- [ ] Custom headers (auth tokens)

**Value:** Enables integration with any system without custom code.

---

### 9. Resume from Failure
> Never lose progress on big jobs

- [ ] Checkpoint every N pages
- [ ] Auto-save queue state
- [ ] "Resume" button to continue interrupted jobs
- [ ] Track partial results separately
- [ ] Retry failed URLs automatically

**Value:** Reliability for large scraping jobs (1000+ pages).

---

### 10. Fuzzy Deduplication
> "Acme Corp" = "Acme Corporation" = "ACME"

- [ ] Fuzzy company name matching
- [ ] Phone number normalization ((555) 123-4567 = 5551234567)
- [ ] Address standardization
- [ ] Merge duplicates from different sources
- [ ] Confidence score for matches

**Value:** Clean data without manual dedup work.

---

## 💪 Tier 3: Strong Value
*Important features for power users*

### 11. CRM Integrations
- [ ] **Salesforce** — Create leads/contacts
- [ ] **HubSpot** — Push to CRM
- [ ] **Pipedrive** — Create deals
- [ ] **Airtable** — Sync to bases
- [ ] **Notion** — Add to databases

### 12. Database Direct Write
- [ ] PostgreSQL export
- [ ] MySQL/MariaDB export
- [ ] MongoDB export
- [ ] SQLite (already supported, enhance)
- [ ] Connection string configuration

### 13. Scheduling & Monitoring
- [ ] Cron-style scheduling (daily, weekly, custom)
- [ ] Email alerts on completion/failure
- [ ] Slack notifications
- [ ] Success/failure dashboard
- [ ] Historical run statistics

### 14. Natural Language Interface
- [ ] "Scrape all restaurants in Houston"
- [ ] "Find companies with phone numbers on this page"
- [ ] "Why isn't the address being extracted?"
- [ ] Chat-based project configuration

### 15. Multi-Browser Worker Pool
- [ ] Spawn N browser instances
- [ ] Distribute URLs across workers
- [ ] Aggregate results
- [ ] Configurable concurrency
- [ ] Resource usage monitoring

---

## 🔧 Tier 4: Nice to Have
*Quality of life improvements*

### 16. UX Improvements
- [ ] Dark/Light theme toggle
- [ ] Drag-and-drop field reordering
- [ ] Visual selector preview (highlight matches)
- [ ] Side-by-side: page vs extracted data
- [ ] Keyboard shortcuts customization

### 17. Project Templates Marketplace
- [ ] Share project configs publicly
- [ ] Browse community templates
- [ ] "Yellow Pages scraper" one-click install
- [ ] Rating and reviews
- [ ] Fork and customize

### 18. Authentication Improvements
- [ ] Visual login flow recorder
- [ ] Cookie import from browser
- [ ] Session persistence across runs
- [ ] 2FA handling (TOTP)
- [ ] Proxy authentication

### 19. Advanced Transforms
- [ ] Python expression per field
- [ ] Regex extraction with groups
- [ ] Calculated/computed fields
- [ ] Conditional logic (if/else)
- [ ] External lookup (API calls)

### 20. Compliance & Audit
- [ ] robots.txt enforcement levels
- [ ] Request logging
- [ ] Rate limit presets (respectful/normal/aggressive)
- [ ] Export audit trail
- [ ] Legal disclaimer generator

---

## 🌙 Moonshots
*Long-term vision / big bets*

### AI Agent Mode
- [ ] Autonomous site navigation
- [ ] AI clicks through multi-step flows
- [ ] CAPTCHA solving integration
- [ ] Login automation (AI figures out forms)
- [ ] Infinite scroll handling

### Browser Extension
- [ ] Chrome/Firefox extension
- [ ] Right-click → "Scrape this"
- [ ] Visual selector from any tab
- [ ] Sync with desktop app

### Data Marketplace
- [ ] Pre-scraped industry datasets
- [ ] Real-time data feeds (subscription)
- [ ] Buy/sell custom scrapes
- [ ] Data quality scoring

### Cloud Platform
- [ ] Hosted Parsonic (SaaS)
- [ ] Team workspaces
- [ ] Usage-based pricing
- [ ] Managed proxy pools
- [ ] Enterprise SSO

---

## Priority Framework

When deciding what to build next, we prioritize:

| Factor | Weight | Description |
|--------|--------|-------------|
| **User Impact** | 40% | How much time/effort does it save? |
| **Differentiation** | 25% | Does it set Parsonic apart from alternatives? |
| **Feasibility** | 20% | Can we build it well in reasonable time? |
| **Revenue Potential** | 15% | Does it enable monetization? |

---

## Contributing

Want to help build these features?

1. **Pick a feature** from Tier 1-3
2. **Open an issue** to discuss approach
3. **Submit a PR** with implementation
4. **Get credited** in release notes

Features with `[Bounty]` tags may have cash rewards for contributors.

---

*Last updated: January 2025*
*This roadmap evolves based on user feedback. Star the repo to stay updated!*
