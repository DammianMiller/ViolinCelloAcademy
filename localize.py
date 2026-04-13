#!/usr/bin/env python3
"""
localize.py – Post-process a wget-mirrored site so that every reference to
the original domain (or any other absolute URL) is converted to a relative
path that works when files are served directly from the local file-system.

Usage
-----
    python3 localize.py --root site/violincelloacademy.com.au

What it does
------------
For every HTML / CSS / JS file found under --root the script:

1. Rewrites absolute URLs that point to the original domain so they become
   relative paths (e.g. https://violincelloacademy.com.au/images/logo.png
   becomes ../../images/logo.png when processed from a sub-directory).

2. Downloads any still-external resource URLs (fonts, CDN libraries, etc.)
   to a local ``assets/`` directory and updates the references accordingly.

3. Strips or neutralises canonical / og:url / alternate tags that would
   redirect a browser back to the live domain.

4. Rewrites <base href="..."> tags so they no longer point to the live site.

The script is idempotent – running it more than once on the same tree is safe.
"""

import argparse
import os
import re
import sys
import urllib.parse
import urllib.request
import hashlib
import mimetypes
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ORIGIN_DOMAIN = "violincelloacademy.com.au"
ORIGIN_SCHEMES = ("https://", "http://")
ORIGIN_PREFIXES = tuple(s + ORIGIN_DOMAIN for s in ORIGIN_SCHEMES)

# External resource hosts whose assets we want to download locally.
# Add more patterns as needed.
EXTERNAL_HOSTS_TO_LOCALISE = [
    "fonts.googleapis.com",
    "fonts.gstatic.com",
    "cdnjs.cloudflare.com",
    "cdn.jsdelivr.net",
    "ajax.googleapis.com",
    "code.jquery.com",
    "stackpath.bootstrapcdn.com",
    "maxcdn.bootstrapcdn.com",
    "use.fontawesome.com",
]

# Attributes in HTML tags that can carry a URL.
HTML_URL_ATTRS = [
    "href",
    "src",
    "action",
    "data",
    "poster",
    "srcset",
    "data-src",
    "data-background",
    "data-href",
    "data-url",
    "content",   # <meta content="url ...">
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def is_origin_url(url: str) -> bool:
    """Return True if *url* points to the original domain."""
    url_lower = url.lower()
    return any(url_lower.startswith(p) for p in ORIGIN_PREFIXES)


def strip_origin(url: str) -> str:
    """Remove the scheme+domain prefix from a URL, returning the path."""
    for prefix in ORIGIN_PREFIXES:
        if url.lower().startswith(prefix):
            remainder = url[len(prefix):]
            # Ensure leading slash
            if not remainder.startswith("/"):
                remainder = "/" + remainder
            return remainder
    return url


def url_to_rel_path(url: str, from_file: Path, root: Path) -> str:
    """Convert an absolute origin URL to a relative path from *from_file*."""
    path_str = strip_origin(url)
    # Remove query-string / fragment for file resolution
    path_str = path_str.split("?")[0].split("#")[0]
    if not path_str or path_str == "/":
        path_str = "/index.html"
    # Ensure .html extension if no extension present and it looks like a page
    if not Path(path_str).suffix:
        path_str = path_str.rstrip("/") + "/index.html"
    target = root / path_str.lstrip("/")
    try:
        rel = os.path.relpath(target, from_file.parent)
    except ValueError:
        # On Windows, relpath can fail across drives; fall back to absolute
        return str(target)
    # Normalise Windows separators
    return rel.replace("\\", "/")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:12]


def safe_filename(url: str, content_type: str | None = None) -> str:
    """Derive a safe filename from a URL."""
    parsed = urllib.parse.urlparse(url)
    name = parsed.path.rstrip("/").split("/")[-1] or "resource"
    if "." not in name:
        ext = mimetypes.guess_extension(content_type or "") or ""
        name += ext
    # Replace characters that are unsafe in filenames
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    return name


def download_external(url: str, assets_dir: Path) -> str | None:
    """
    Download an external URL to assets_dir.
    Returns the local file path (relative to assets_dir) or None on failure.
    """
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; site-archiver/1.0)"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            content_type = resp.headers.get("Content-Type", "")
            data = resp.read()
    except Exception as exc:
        print(f"    [WARN] Could not download {url}: {exc}", file=sys.stderr)
        return None

    fname = safe_filename(url, content_type.split(";")[0].strip())
    # Prefix with a hash snippet to avoid name collisions
    fname = sha256_hex(url.encode()) + "_" + fname
    dest = assets_dir / fname
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return str(dest)


# ---------------------------------------------------------------------------
# HTML processing
# ---------------------------------------------------------------------------

# Pattern that matches an HTML tag opening, used to spot attributes.
# The value group captures:
#   - When quotes present: everything up to the SAME matching closing quote
#     (using the backreference (?P=q) so single-quoted values may contain "
#      and double-quoted values may contain ')
#   - When no quotes:      everything up to whitespace or >
_TAG_RE = re.compile(r"<([a-zA-Z][a-zA-Z0-9]*)\b([^>]*)>", re.DOTALL)
_ATTR_RE = re.compile(
    r"""(?P<attr>[a-zA-Z][a-zA-Z0-9_:-]*)\s*=\s*"""
    r"""(?:(?P<q>['"])(?P<val_q>.*?)(?P=q)|(?P<val_u>[^'">\s]*))""",
    re.IGNORECASE | re.DOTALL,
)

# <meta http-equiv="refresh"> / canonical / og:url tags we want to strip
_META_REFRESH_RE = re.compile(
    r'<meta\b[^>]*\bhttp-equiv\s*=\s*["\']refresh["\'][^>]*>',
    re.IGNORECASE | re.DOTALL,
)
_CANONICAL_RE = re.compile(
    r'<link\b[^>]*\brel\s*=\s*["\']canonical["\'][^>]*>',
    re.IGNORECASE | re.DOTALL,
)

# CSS url() references
_CSS_URL_RE = re.compile(r"""url\(\s*(['"]?)([^'"\)]+)\1\s*\)""", re.IGNORECASE)

# <base href="...">
_BASE_HREF_RE = re.compile(r'(<base\b[^>]*\bhref\s*=\s*["\'])([^"\']+)(["\'][^>]*>)', re.IGNORECASE)


def rewrite_url(
    url: str,
    from_file: Path,
    root: Path,
    assets_dir: Path,
    download_external_assets: bool = True,
) -> str:
    """
    Given a URL found inside *from_file*, return the appropriate replacement.

    - Origin-domain absolute URLs → relative path
    - Root-relative URLs (/path)  → relative path from current file
    - Selected external URLs     → downloaded to assets_dir, then relative path
    - Relative URLs              → unchanged
    - Other absolute URLs        → unchanged (or optionally downloaded)
    """
    url = url.strip()
    if not url or url.startswith("data:") or url.startswith("#"):
        return url

    if is_origin_url(url):
        return url_to_rel_path(url, from_file, root)

    # Root-relative path: /some/path → convert to relative from current file
    if url.startswith("/") and not url.startswith("//"):
        return url_to_rel_path(url, from_file, root)

    if download_external_assets and url.startswith(("http://", "https://")):
        parsed = urllib.parse.urlparse(url)
        if any(host in parsed.netloc for host in EXTERNAL_HOSTS_TO_LOCALISE):
            local = download_external(url, assets_dir)
            if local:
                rel = os.path.relpath(local, from_file.parent).replace("\\", "/")
                return rel

    return url


def process_html(text: str, from_file: Path, root: Path, assets_dir: Path) -> str:
    """Rewrite all URLs in an HTML document."""

    # 1. Remove canonical link and meta-refresh tags that point back to live site
    text = _META_REFRESH_RE.sub("<!-- meta-refresh removed by localize.py -->", text)
    text = re.sub(
        r'<link\b[^>]*\brel\s*=\s*["\']canonical["\'][^>]*>',
        "<!-- canonical removed by localize.py -->",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # 2. Rewrite <base href="...">
    def replace_base(m):
        url = m.group(2)
        new_url = rewrite_url(url, from_file, root, assets_dir)
        return m.group(1) + new_url + m.group(3)

    text = _BASE_HREF_RE.sub(replace_base, text)

    # 3. Rewrite tag attributes
    def replace_tag(m):
        tag_name = m.group(1)
        attrs_str = m.group(2)

        def replace_attr(am):
            attr = am.group("attr").lower()
            # Support both quoted (val_q) and unquoted (val_u) attribute values
            if am.group("q"):
                val = am.group("val_q")
                quote = am.group("q")
            else:
                val = am.group("val_u") or ""
                quote = '"'

            if attr in HTML_URL_ATTRS:
                if attr == "srcset":
                    # srcset is a comma-separated list of "url [descriptor]" entries.
                    # Each entry is "url [width_or_density_descriptor]".
                    # The first token is always the URL; subsequent tokens are
                    # descriptors like "2x" or "480w" which are left unchanged.
                    new_entries = []
                    for part in val.split(","):
                        part = part.strip()
                        if not part:
                            continue
                        tokens = part.split()
                        if tokens:
                            # Always attempt to rewrite the first token as a URL;
                            # rewrite_url returns it unchanged if it is not a
                            # recognised URL pattern.
                            tokens[0] = rewrite_url(tokens[0], from_file, root, assets_dir)
                        new_entries.append(" ".join(tokens))
                    new_val = ", ".join(new_entries)
                else:
                    new_val = rewrite_url(val, from_file, root, assets_dir)
                return f'{am.group("attr")}={quote}{new_val}{quote}'
            return am.group(0)

        new_attrs = _ATTR_RE.sub(replace_attr, attrs_str)
        return f"<{tag_name}{new_attrs}>"

    text = _TAG_RE.sub(replace_tag, text)

    # 4. Rewrite inline <style> blocks and style="..." attributes
    text = process_css_in_html(text, from_file, root, assets_dir)

    # 5. Rewrite remaining bare origin URLs in inline <script> blocks.
    # Use a regex that matches quoted string literals so we only replace
    # URLs inside strings, not in comments or other non-URL contexts.
    for prefix in ORIGIN_PREFIXES:
        text = re.sub(
            r'(["\'])(' + re.escape(prefix) + r'[^"\']*?)(["\'])',
            lambda m: m.group(1) + rewrite_url(m.group(2), from_file, root, assets_dir, download_external_assets=False) + m.group(3),
            text,
        )

    return text


def process_css_in_html(text: str, from_file: Path, root: Path, assets_dir: Path) -> str:
    """Rewrite url() references inside <style> tags and style="" attributes."""

    # Inline style blocks
    def replace_style_block(m):
        inner = _CSS_URL_RE.sub(
            lambda cm: rewrite_css_url(cm, from_file, root, assets_dir),
            m.group(0),
        )
        return inner

    text = re.sub(
        r"<style\b[^>]*>.*?</style>",
        replace_style_block,
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return text


def process_css(text: str, from_file: Path, root: Path, assets_dir: Path) -> str:
    """Rewrite url() references in a standalone CSS file."""

    def repl(m):
        return rewrite_css_url(m, from_file, root, assets_dir)

    return _CSS_URL_RE.sub(repl, text)


def rewrite_css_url(m, from_file: Path, root: Path, assets_dir: Path) -> str:
    quote = m.group(1)
    url = m.group(2)
    new_url = rewrite_url(url, from_file, root, assets_dir)
    return f"url({quote}{new_url}{quote})"


def process_js(text: str, from_file: Path, root: Path, assets_dir: Path) -> str:
    """Rewrite hard-coded origin URLs inside JS files.

    Replaces the origin prefix only inside quoted string literals to avoid
    inadvertently modifying comments or non-URL contexts.
    """
    for prefix in ORIGIN_PREFIXES:
        text = re.sub(
            r'(["\'])(' + re.escape(prefix) + r'[^"\']*?)(["\'])',
            lambda m: m.group(1) + rewrite_url(m.group(2), from_file, root, assets_dir, download_external_assets=False) + m.group(3),
            text,
        )
    return text


# ---------------------------------------------------------------------------
# File walker
# ---------------------------------------------------------------------------

TEXT_EXTENSIONS = {
    ".html", ".htm", ".xhtml",
    ".css",
    ".js", ".mjs",
    ".xml", ".svg",
    ".json",
    ".txt",
}


def process_file(path: Path, root: Path, assets_dir: Path):
    ext = path.suffix.lower()
    if ext not in TEXT_EXTENSIONS:
        return

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        print(f"  [WARN] Cannot read {path}: {exc}", file=sys.stderr)
        return

    original = text

    if ext in (".html", ".htm", ".xhtml"):
        text = process_html(text, path, root, assets_dir)
    elif ext == ".css":
        text = process_css(text, path, root, assets_dir)
    elif ext in (".js", ".mjs"):
        text = process_js(text, path, root, assets_dir)
    elif ext == ".svg":
        text = process_html(text, path, root, assets_dir)
    else:
        # For XML/JSON/TXT, at minimum replace bare origin URLs.
        # Replace the longer prefix+slash pattern first so the bare prefix
        # replacement doesn't produce a double-slash artifact.
        for prefix in ORIGIN_PREFIXES:
            text = text.replace(prefix + "/", "./")
            text = text.replace(prefix, "./")

    if text != original:
        path.write_text(text, encoding="utf-8")
        print(f"  [OK]   {path.relative_to(root)}")


def walk_and_process(root: Path):
    assets_dir = root / "assets" / "external"
    assets_dir.mkdir(parents=True, exist_ok=True)

    all_files = sorted(root.rglob("*"))
    total = sum(1 for f in all_files if f.is_file() and f.suffix.lower() in TEXT_EXTENSIONS)
    processed = 0

    for path in root.rglob("*"):
        if path.is_file():
            process_file(path, root, assets_dir)
            if path.suffix.lower() in TEXT_EXTENSIONS:
                processed += 1

    print(f"\n  Processed {processed}/{total} text files.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--root",
        default="www",
        help="Root directory of the mirrored site (default: www)",
    )
    parser.add_argument(
        "--no-download",
        action="store_true",
        help="Skip downloading external assets; only rewrite local references",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.exists():
        print(f"Error: root directory {root} does not exist.", file=sys.stderr)
        print("Run download.sh first to mirror the site.", file=sys.stderr)
        sys.exit(1)

    print(f"Localising references in: {root}")
    walk_and_process(root)
    print("\nDone.  All references have been made relative.")


if __name__ == "__main__":
    main()
