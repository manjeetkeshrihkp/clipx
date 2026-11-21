# 🌐 Hosting EliteX Clipper Online with GitHub

This guide covers everything you need to host and run EliteX Clipper online using GitHub.

---

## ⚡ How Hosting Works: The 2 Core Parts

EliteX Clipper requires **Python**, **FFmpeg** (for video rendering), and **AI/speech models** (~480 MB). 

Because **GitHub Pages** only serves static HTML/CSS (no Python or FFmpeg backend), GitHub handles EliteX Clipper via **GitHub Actions** and **GitHub-connected cloud platforms**:

| Capability | How it's hosted | Cost |
|---|---|---|
| **Autonomous Hourly Instagram Bot** (Auto-Pilot) | **GitHub Actions** (`.github/workflows/autotrend.yml`) | **100% Free** |
| **Interactive Web UI Dashboard** | **Hugging Face Spaces** or **Render** (connected to GitHub) | **100% Free** |
| **Instant Remote Access to your PC** | **Cloudflare Tunnel** (`cloudflared`) | **100% Free** |

---

## 🚀 Step 1: Push Your Code to GitHub

1. Go to [github.com/new](https://github.com/new) and create a new repository:
   - Repository name: `clipx`
   - Privacy: **Private** (recommended, to keep your settings and assets private) or **Public**
   - Do **NOT** initialize with a README, .gitignore, or license (we already have them).

2. In your local terminal (`C:\Users\Manjeet keshri\Downloads\clipx`), link and push:
   ```bash
   git branch -M main
   git remote add origin https://github.com/<YOUR-GITHUB-USERNAME>/clipx.git
   git push -u origin main
   ```

*(Replace `<YOUR-GITHUB-USERNAME>` with your actual GitHub username).*

---

## 🤖 Step 2: Enable the 24/7 Hourly Bot on GitHub Actions

Once pushed, GitHub Actions can run the Auto-Pilot bot **every hour** on GitHub's cloud servers without keeping your computer running.

### 1. Add Your Secrets in GitHub
1. Open your repository on GitHub.
2. Go to **Settings** → **Secrets and variables** → **Actions** → Click **New repository secret**.
3. Add the following secrets:

| Secret Name | Value | Description |
|---|---|---|
| `GEMINI_API_KEY` or `GROQ_API_KEY` | `your-api-key` | Free AI key to scout viral moments and generate hooks |
| `INSTAGRAM_ACCESS_TOKEN` | `your-ig-token` | *(Optional)* Long-lived token from Meta for Developers to post Reels directly |
| `AUTOTREND_NICHE` | `podcast` | *(Optional)* podcast, tech, gaming, motivation, finance, or custom |
| `AUTOTREND_QUERY` | *(optional query)* | Used if `AUTOTREND_NICHE` is custom |

### 2. Verify or Trigger Workflow
1. In your GitHub repository, click on the **Actions** tab.
2. You will see **ClipX Auto-Pilot (Hourly Trend & Instagram Bot)**.
3. It will run automatically **every hour** (`0 * * * *`).
4. You can also run it immediately on demand:
   - Click **ClipX Auto-Pilot** in the left sidebar.
   - Click **Run workflow** → Choose niche → Click the green **Run workflow** button!

### 3. Download Generated Clips
After each run finishes:
- Click the completed workflow run.
- Scroll to the bottom to **Artifacts**.
- Click `clipx-generated-clips-<id>` to download the rendered 9:16 vertical `.mp4` video clips directly from GitHub!

---

## 🖥️ Step 3: Host the Web Dashboard Online (Optional)

If you want to open the web dashboard from your phone or browser anywhere in the world to edit clips manually:

### Option A: Hugging Face Spaces (100% Free Docker Hosting)
Hugging Face Spaces offers **16 GB RAM, 2 vCPUs, 50 GB persistent storage** for free forever.
1. Go to [huggingface.co/new-space](https://huggingface.co/new-space).
2. Set Space Name: `clipx`.
3. Select **Docker** (Blank).
4. In Space Settings, link your GitHub repository (or push your repository to the Space remote).
5. Add your AI API key under Space Secrets (`GROQ_API_KEY` or `GEMINI_API_KEY`).
6. Hugging Face builds the Docker container and gives you a free HTTPS link (e.g. `https://huggingface.co/spaces/<user>/clipx`).

### Option B: Render.com (1-Click Blueprint)
1. Go to [render.com](https://render.com) and sign in with GitHub.
2. Click **New +** → **Blueprint**.
3. Select your `clipx` GitHub repository. Render reads the included `render.yaml` file automatically!
4. Click **Apply**. Render deploys ClipX with HTTPS.

### Option C: Cloudflare Tunnel (Instant, 0 Setup)
If you have ClipX running on your computer and want to access it from your phone:
1. Download [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/).
2. Run:
   ```bash
   cloudflared tunnel --url http://127.0.0.1:8765
   ```
3. Cloudflare gives you a free, secure `https://<random>.trycloudflare.com` link instantly. Open it on any phone or computer!

---

## 🔒 Security Best Practices
- Never commit your `.env` or files containing secret API keys.
- Store all sensitive keys in **GitHub Repository Secrets** or in the online Settings dashboard.
