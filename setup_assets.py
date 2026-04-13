import os
import re


def make_relative():
    for html_file in os.listdir("."):
        if not html_file.endswith(".html"):
            continue

        with open(html_file, "r", encoding="utf-8") as f:
            content = f.read()

        new_content = content

        # Replace images from squarespace-cdn with relative paths
        new_content = re.sub(
            r'https://images\.squarespace-cdn\.com/[^"\' >]+',
            lambda m: "assets/img/" + m.group(0).split("/")[-1].split("?")[0],
            new_content,
        )

        # Replace CSS from static1.squarespace.com
        new_content = re.sub(
            r'https://static1\.squarespace\.com/static/[^"\' >]+',
            lambda m: "assets/css/" + m.group(0).split("/")[-1].split("?")[0],
            new_content,
        )

        # JS from assets.squarespace.com
        new_content = re.sub(
            r'https://assets\.squarespace\.com/[^"\' >]+',
            lambda m: "assets/js/" + m.group(0).split("/")[-1].split("?")[0],
            new_content,
        )

        # Remove preconnect links to external domains
        new_content = re.sub(
            r'<link rel="preconnect" href="https://images\.squarespace-cdn\.com">',
            "",
            new_content,
        )
        new_content = re.sub(
            r'<link rel="preconnect" href="https://fonts\.gstatic\.com"[^>]*>',
            "",
            new_content,
        )

        with open(html_file, "w", encoding="utf-8") as f:
            f.write(new_content)


if __name__ == "__main__":
    make_relative()
