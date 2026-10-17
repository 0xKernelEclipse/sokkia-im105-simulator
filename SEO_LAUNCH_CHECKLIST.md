# SEO Launch Checklist & Webmaster Setup Guide
**Project:** Sokkia iM-105 Total Station Simulator  
**Production URL:** `https://sokkia-im105-simulator.vercel.app/`  

---

## 1. Pre-Deployment Verification (Completed)

- [x] Canonical link tag pointed to `https://sokkia-im105-simulator.vercel.app/`.
- [x] Favicons generated (`favicon.svg`, `favicon-48x48.png`, `apple-touch-icon.png`).
- [x] Social cards (`og:image.png` at 1200×630px, Open Graph and Twitter card tags).
- [x] Web App Manifest configured (`manifest.webmanifest`).
- [x] XML Sitemap (`sitemap.xml`) generated and verified.
- [x] AI Crawlers allowed in `robots.txt` (`GPTBot`, `OAI-SearchBot`, `ClaudeBot`, `PerplexityBot`, `Google-Extended`).
- [x] Structured Data (Schema.org JSON-LD) verified and validated.
- [x] `llms.txt` deployed for LLM and AI agent retrieval.
- [x] Vercel security headers configured in `vercel.json`.

---

## 2. Immediate Post-Deployment Steps (For Site Owner)

### Step A: Google Search Console Setup
1. Log in to [Google Search Console](https://search.google.com/search-console).
2. Add a new Property using the URL Prefix: `https://sokkia-im105-simulator.vercel.app/`.
3. Verify ownership:
   - **Recommended:** HTML tag method or DNS CNAME / TXT record on Vercel.
4. Submit Sitemap:
   - Navigate to **Sitemaps** on the left menu.
   - Enter `sitemap.xml` and click **Submit**.
5. Request Initial Indexing:
   - Use the top **URL Inspection** bar.
   - Enter `https://sokkia-im105-simulator.vercel.app/`.
   - Click **Test Live URL**, then click **Request Indexing**.

---

### Step B: Bing Webmaster Tools & IndexNow
1. Log in to [Bing Webmaster Tools](https://www.bing.com/webmasters).
2. Choose **Import from Google Search Console** for instant 1-click verification.
3. Submit `https://sokkia-im105-simulator.vercel.app/sitemap.xml`.
4. IndexNow Integration:
   - Bing Webmaster Tools automatically monitors URLs submitted through Search Console.
   - For real-time updates upon code commits, you can generate an IndexNow key in Bing and place `<key>.txt` at the root.

---

### Step C: Social & Rich Result Previews Testing
1. **Google Rich Results Test:**
   - Test `https://sokkia-im105-simulator.vercel.app/` on [Google Rich Results Test](https://search.google.com/test/rich-results) to verify `WebApplication`, `FAQPage`, and `HowTo` snippets.
2. **Facebook Sharing Debugger:**
   - Test URL on [Facebook Sharing Debugger](https://developers.facebook.com/tools/debug/) to refresh the Open Graph cache.
3. **Twitter Card Validator / Tweet Preview:**
   - Verify `summary_large_image` preview with `og-image.png`.

---

## 3. Ongoing Search & AI Monitoring

| Frequency | Task | Tool |
|---|---|---|
| **Weekly** | Check Indexed Pages & Crawl Errors | Google Search Console > Pages |
| **Weekly** | Monitor Search Queries & Impressions | GSC > Performance (Filter by queries: "Sokkia iM 105", "Total station simulator") |
| **Monthly** | Test AI Citations & Search Answers | Query ChatGPT Search, Perplexity, Copilot: *"Where can I practice using a Sokkia total station online?"* |
| **Quarterly** | Refresh Sitemap `lastmod` after feature updates | Update date in `sitemap.xml` and re-submit in GSC |
