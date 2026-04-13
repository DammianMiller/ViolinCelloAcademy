# ViolinCelloAcademy

A local, self-contained mirror of **violincelloacademy.com.au** where every
asset (HTML, CSS, JavaScript, images, fonts, …) is hosted locally and all
URLs are relative – no external dependencies at runtime.

---

## Repository layout

```
ViolinCelloAcademy/
├── www/                  ← mirrored website files (index.html lives here)
│   ├── index.html
│   ├── assets/
│   │   └── external/     ← CDN assets downloaded locally by localize.py
│   └── …
├── download.sh           ← one-shot script: mirror + localise
├── localize.py           ← post-processor: convert absolute URLs → relative
├── .gitignore
└── README.md
```

---

## Quick start

### Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| `wget` | ≥ 1.20 | Available by default on most Linux distros; `brew install wget` on macOS |
| Python 3 | ≥ 3.9 | Required by `localize.py` |

### 1 – Clone and run the download script

```bash
git clone https://github.com/DammianMiller/ViolinCelloAcademy.git
cd ViolinCelloAcademy
bash download.sh
```

`download.sh` will:

1. Run `wget` in mirror mode to recursively download the entire
   `violincelloacademy.com.au` website (HTML pages **and** all page
   requisites: images, stylesheets, scripts, fonts, …).
2. Move the downloaded files from the `_tmp_mirror/` staging directory
   into `www/`.
3. Call `localize.py` to perform a second pass that handles anything
   `wget --convert-links` misses (see below).

The whole process typically takes 1–5 minutes depending on your connection.

### 2 – Preview locally

```bash
python3 -m http.server 8080 --directory www
# then open http://localhost:8080 in your browser
```

Or simply open `www/index.html` directly in your browser (most assets will
work; a local server is only needed for pages that use `fetch()` / AJAX).

### 3 – Commit the mirrored files

After verifying the site looks correct:

```bash
git add www/
git commit -m "Add mirrored violincelloacademy.com.au"
git push
```

---

## What `localize.py` does

`wget --convert-links` rewrites `href`/`src` attributes in HTML files, but
it cannot handle every case.  `localize.py` performs a thorough second pass:

| Source | What is rewritten |
|--------|------------------|
| HTML attributes | `href`, `src`, `action`, `data`, `poster`, `srcset`, `data-src`, `data-background`, `data-href`, `data-url`, `content` |
| CSS files | `url()` references |
| Inline `<style>` blocks | `url()` references |
| JS files | Hard-coded origin strings |
| `<base href>` | Removed / relativised |
| `<link rel="canonical">` | Removed (prevents browser redirecting to live site) |
| `<meta http-equiv="refresh">` | Removed |
| External CDN assets | Downloaded to `www/assets/external/` and referenced locally |

Supported external hosts that are automatically downloaded:

- `fonts.googleapis.com` / `fonts.gstatic.com`
- `cdnjs.cloudflare.com`
- `cdn.jsdelivr.net`
- `ajax.googleapis.com`
- `code.jquery.com`
- `stackpath.bootstrapcdn.com` / `maxcdn.bootstrapcdn.com`
- `use.fontawesome.com`

You can run `localize.py` on its own at any time:

```bash
python3 localize.py --root www
# or, to skip downloading external assets:
python3 localize.py --root www --no-download
```

---

## Updating the mirror

To refresh the mirror with a newer version of the live site:

```bash
# Remove old mirror and re-download
rm -rf www/
bash download.sh
git add www/
git commit -m "Refresh mirror $(date +%Y-%m-%d)"
```
