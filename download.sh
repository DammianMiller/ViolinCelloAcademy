#!/usr/bin/env bash
# download.sh - Mirror violincelloacademy.com.au for local hosting
#
# Usage: bash download.sh
#
# Requirements: wget (pre-installed on most Linux/macOS systems)
#
# This script uses wget to recursively download the entire website,
# converting all links to relative paths.  After it finishes, run
# localize.py for any additional clean-up of hard-coded absolute URLs
# that wget's --convert-links cannot handle (e.g. inside CSS url()
# expressions, inline JS strings, meta-refresh tags, etc.).

set -euo pipefail

SITE="https://violincelloacademy.com.au"
# Temporary staging area; wget nests files under the domain name
TMP_DIR="_tmp_mirror"
# Final destination committed to the repository
DEST="www"

echo "==> Downloading ${SITE} into ./${TMP_DIR}/"

wget \
  --recursive \
  --no-clobber \
  --page-requisites \
  --html-extension \
  --convert-links \
  --restrict-file-names=windows \
  --domains violincelloacademy.com.au \
  --no-parent \
  --directory-prefix="${TMP_DIR}" \
  --user-agent="Mozilla/5.0 (compatible; site-archiver/1.0)" \
  --wait=0.5 \
  --random-wait \
  --timeout=30 \
  --tries=3 \
  "${SITE}/"

# Move files from the domain-namespaced sub-directory to the final destination
echo ""
echo "==> Moving mirrored files to ./${DEST}/"
rm -rf "${DEST}"
mv "${TMP_DIR}/violincelloacademy.com.au" "${DEST}"
rm -rf "${TMP_DIR}"

echo ""
echo "==> Running localize.py to fix remaining absolute references"
echo "    (CSS url(), inline JS, canonical tags, og:url, etc.) ..."

python3 localize.py --root "${DEST}"

echo ""
echo "==> Done.  Open ./${DEST}/index.html in a browser to preview the"
echo "    locally hosted site, or run:"
echo "      python3 -m http.server 8080 --directory ${DEST}"
echo "    and navigate to http://localhost:8080"
