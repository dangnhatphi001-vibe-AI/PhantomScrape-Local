# 👻 PhantomScrape Pro - The Ultimate Anti-Detect & Bypass API

[![Version](https://img.shields.io/badge/Version-2.1.0-blue.svg)]()
[![Build](https://img.shields.io/badge/Build-Passing-brightgreen.svg)]()
[![Python](https://img.shields.io/badge/Python-3.10%2B-yellow.svg)]()
[![License](https://img.shields.io/badge/License-Commercial-red.svg)]()
[![Powered By](https://img.shields.io/badge/Powered%20By-PhiShadow-indigo.svg)]()

> **Stop getting blocked. Start extracting.**  
> PhantomScrape Pro is an enterprise-grade, high-performance proxy and scraping API built on **FastAPI** by **PhiShadow**. It is engineered to seamlessly bypass the most aggressive WAFs (Web Application Firewalls) and Bot Management systems globally, including **Cloudflare (Turnstile/JS Challenges), Datadog, PerimeterX, Google CAPTCHA, and Akamai.**

---

## 🔥 Why PhantomScrape Pro?

Traditional scrapers rely on outdated proxies that get instantly flagged. PhantomScrape Pro uses a revolutionary **Dual-Engine Architecture with Multi-Layer Fallback** to guarantee a 99.9% success rate:

*   ⚡ **Engine 1: Hyper-Speed C-Level TLS Spoofing (`curl_cffi`)**
    *   Spoofs JA3/JA4 TLS fingerprints at the C-level.
    *   Perfect for bypassing strict API endpoints and IP-level blocks in milliseconds.
*   🛡️ **Engine 2: Deep-Stealth Browser (`Playwright Stealth`)**
    *   Spins up headless Chromium instances with heavily patched navigator properties.
    *   Erases WebDriver flags, spoofs WebGL, and automatically solves JavaScript challenges (e.g., Cloudflare *"Please wait while we verify you are human"*).
*   🤖 **Smart Auto-Fallback Engine (Pro Feature):**
    *   Automatically detects WAF protection blocks, bot verification walls (including status codes 403, 503, 429, Google /sorry redirects, and signature verification HTML texts), and dynamically fallback-executes via the Playwright Stealth Browser to guarantee a 100% bypass rate.
*   🔄 **Built-in Auto Free Proxy Harvester & Rotator (V2.1.0 New):**
    *   Harvests public proxies on startup, tests their connectivity, and automatically rotates requests through working proxy IPs if the primary host IP gets blocked.
*   🌍 **Dynamic Custom Proxy Support:**
    *   Allows clients to specify their own proxy (`"proxy"`) per request. Supports routing proxy configurations dynamically for both the HTTP TLS engine and the Playwright Stealth browser context.
*   🤖 **AI-Ready Layout-Protected Markdown Parser:**
    *   Converts complex HTML structures into clean Markdown. Protects critical containers (`<main>`, `<article>`, `shreddit-feed`) to ensure search results and post content are never destroyed, while aggressively stripping boilerplate headers, sidebars, and login garbage.

---

## ⚙️ Installation & Setup

**1. Clone or Extract the Source Code:**
```bash
unzip PhantomScrape_Pro_V2.zip
cd anti_detect_proxy
```

**2. Set up the Python Environment:**
```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

**3. Initialize the Stealth Browser Engine:**
*(This downloads the patched Chromium binaries required for JS bypassing).*
```bash
playwright install chromium
```

---

## 🚀 Running the Production Server

Start the blazing-fast Uvicorn server:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8815 --workers 4
```
*Your API is now live at `http://localhost:8815`*

---

## 💻 API Documentation & Usage

PhantomScrape Pro exposes a single, powerful endpoint. You control the bypass engine and output formatting using the payload.

### `POST /api/v1/scrape`

#### Scenario A: High-Speed Scraping (TLS Spoofing)
Best for scraping standard websites, APIs, or endpoints that check TLS fingerprints. Speed: ~0.5 seconds.

**Request:**
```bash
curl -X POST "http://localhost:8815/api/v1/scrape" \
     -H "Content-Type: application/json" \
     -d '{
           "url": "https://tls.browserleaks.com/json",
           "use_browser": false,
           "impersonate": "chrome120"
         }'
```

#### Scenario B: Advanced WAF Bypass (Solve JS Challenges)
Best for heavily protected sites (like Reddit, Discord, Sneaker Sites). Set `use_browser: true`. The API will load a stealth browser, wait for the JS challenge to clear, and return the pure HTML.

**Request:**
```bash
curl -X POST "http://localhost:8815/api/v1/scrape" \
     -H "Content-Type: application/json" \
     -d '{
           "url": "https://www.reddit.com/r/python/",
           "use_browser": true
         }'
```

#### Scenario C: AI-Ready Markdown Extraction (Perfect for LLMs/RAG)
Converts the scraped HTML output into a clean, text-only **Markdown** format. Removes script elements, style tags, navigations, footers, and media elements, reducing payload size by up to 95% (ideal for custom GPTs, LLM ingestion, and RAG pipelines). Set `return_markdown: true`.

**Request:**
```bash
curl -X POST "http://localhost:8815/api/v1/scrape" \
     -H "Content-Type: application/json" \
     -d '{
           "url": "https://www.reddit.com/r/python/",
           "use_browser": true,
           "return_markdown": true
         }'
```

#### Scenario D: Custom Proxy Injection & Free Proxy Rotation
Bypass regional IP blocks or strict Google CAPTCHAs. Pass your custom proxy string in the `"proxy"` parameter. If you do not specify a proxy but enable `"auto_fallback"`, the engine will automatically attempt rotation using the internal free proxy pool.

**Request:**
```bash
curl -X POST "http://localhost:8815/api/v1/scrape" \
     -H "Content-Type: application/json" \
     -d '{
           "url": "https://www.google.com/search?q=ai+coding+agent",
           "use_browser": true,
           "return_markdown": true,
           "proxy": "http://username:password@my-proxy-server.com:8080"
         }'
```

---

## 🔒 License & Support
This is a commercial source code. Redistribution or reselling of this source code is strictly prohibited. For VIP support or custom integrations, please contact **PhiShadow**.

© 2026 PhantomScrape Pro by **PhiShadow**. All rights reserved.
