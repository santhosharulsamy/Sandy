"""Build a single, print-styled HTML edition of the book and render it to PDF.

Assembles the chapter markdown files in order into one HTML document with a
title page, table of contents, per-chapter page breaks, and print CSS, then
renders it to PDF with the bundled Chromium (headless --print-to-pdf).

    pip install markdown        # one-time: the only dependency
    python docs/book/build_pdf.py

The PDF step uses the bundled Chromium; if it isn't found, only the HTML is
written (and any browser can print that to PDF).

Outputs, next to this script:
    the-sandy-programming-language.html   (the single-file edition)
    the-sandy-programming-language.pdf    (if Chromium is available)
"""

import glob
import os
import shutil
import subprocess
import sys

import markdown

HERE = os.path.dirname(os.path.abspath(__file__))
HTML_OUT = os.path.join(HERE, "the-sandy-programming-language.html")
PDF_OUT = os.path.join(HERE, "the-sandy-programming-language.pdf")

CSS = """
@page { size: A4; margin: 22mm 20mm; }
@page { @bottom-center { content: counter(page); } }
:root { --ink:#1b1712; --soft:#4c453b; --muted:#8a8073; --amber:#a45e12;
        --line:#e5ded2; --code-bg:#f6f2ea; }
* { box-sizing: border-box; }
body { font-family: "Public Sans", Georgia, "Times New Roman", serif;
       color: var(--ink); line-height: 1.62; font-size: 11.2pt; margin: 0; }
h1, h2, h3, h4 { font-family: "Bricolage Grotesque", Georgia, serif;
       line-height: 1.15; color: var(--ink); }
h1 { font-size: 26pt; letter-spacing: -.02em; }
h2 { font-size: 18pt; margin: 0 0 .4em; letter-spacing: -.01em; }
h3 { font-size: 13.5pt; margin: 1.4em 0 .3em; }
p, li { color: var(--soft); }
a { color: var(--amber); text-decoration: none; }
code, pre { font-family: "JetBrains Mono", ui-monospace, Menlo, monospace; }
code { background: var(--code-bg); padding: .08em .32em; border-radius: 3px;
       font-size: .88em; color: #603b0e; }
pre { background: var(--code-bg); border: 1px solid var(--line);
      border-radius: 7px; padding: 12px 14px; overflow-x: auto; font-size: 9.4pt;
      line-height: 1.5; }
pre code { background: none; padding: 0; color: var(--ink); font-size: inherit; }
table { border-collapse: collapse; width: 100%; margin: 1em 0; font-size: 10pt; }
th, td { border: 1px solid var(--line); padding: 6px 10px; text-align: left;
         vertical-align: top; }
th { background: var(--code-bg); font-family: "Bricolage Grotesque", serif; }
blockquote { border-left: 3px solid var(--amber); margin: 1em 0; padding: .2em 1em;
             color: var(--soft); background: #faf7f1; }
hr { border: none; border-top: 1px solid var(--line); margin: 2em 0; }

.chapter { page-break-before: always; }
.titlepage { page-break-after: always; text-align: center; padding-top: 32%; }
.titlepage .name { font-family: "Bricolage Grotesque", serif; font-weight: 800;
       font-size: 40pt; letter-spacing: -.03em; margin: 0; }
.titlepage .name .dot { color: var(--amber); }
.titlepage .tag { font-size: 13pt; color: var(--soft); margin-top: 1.2em; }
.titlepage .foot { margin-top: 3.5em; font-family: "JetBrains Mono", monospace;
       font-size: 9.5pt; color: var(--muted); }
.toc { page-break-after: always; }
.toc h2 { border-bottom: 2px solid var(--amber); padding-bottom: .2em; }
.toc ol { line-height: 2; }
"""

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
         'family=Bricolage+Grotesque:opsz,wght@12..96,600;12..96,800&'
         'family=Public+Sans:ital,wght@0,400;0,600;1,400&'
         'family=JetBrains+Mono:wght@400;600&display=swap">')


def chapters():
    files = sorted(glob.glob(os.path.join(HERE, "[0-9][0-9]-*.md")))
    return files


def toc_html():
    items = []
    for path in chapters():
        with open(path, encoding="utf-8") as f:
            first = f.readline().strip().lstrip("# ").strip()
        items.append(f"<li>{first}</li>")
    return ("<div class='toc'><h2>Contents</h2><ol>" + "".join(items)
            + "</ol></div>")


def build_html():
    md = markdown.Markdown(extensions=["fenced_code", "tables"])
    parts = [
        "<!doctype html><html><head><meta charset='utf-8'>",
        "<title>The Sandy Programming Language</title>", FONTS,
        f"<style>{CSS}</style></head><body>",
        "<div class='titlepage'>",
        "<p class='name'>sandy<span class='dot'>.</span></p>",
        "<p class='tag'>The Sandy Programming Language</p>",
        "<p class='tag' style='font-size:11pt'>As easy as Python. Compiles to a "
        "native binary. Checked before you ship.</p>",
        "<p class='tag' style='font-size:12pt; margin-top:2.4em'>"
        "Santhosh Arulsamy</p>",
        "<p class='foot'>A complete guide to the language,<br>its standard "
        "library, and its tools.</p>",
        "</div>",
        toc_html(),
    ]
    for path in chapters():
        md.reset()
        with open(path, encoding="utf-8") as f:
            body = md.convert(f.read())
        parts.append(f"<div class='chapter'>{body}</div>")
    parts.append("</body></html>")
    with open(HTML_OUT, "w", encoding="utf-8") as f:
        f.write("".join(parts))
    return HTML_OUT


def render_pdf(html_path):
    chrome = None
    for name in ("chromium", "chromium-browser", "google-chrome",
                 "/opt/pw-browsers/chromium/chrome-linux/chrome"):
        found = shutil.which(name) if "/" not in name else (
            name if os.path.exists(name) else None)
        if found:
            chrome = found
            break
    if chrome is None:
        for base in glob.glob("/opt/pw-browsers/chromium*/chrome-linux/chrome"):
            chrome = base
            break
    if chrome is None:
        print("Chromium not found; wrote HTML only.", file=sys.stderr)
        return None
    subprocess.run([
        chrome, "--headless", "--no-sandbox", "--disable-gpu",
        "--no-pdf-header-footer",
        f"--print-to-pdf={PDF_OUT}", "file://" + html_path,
    ], capture_output=True, timeout=120)
    return PDF_OUT if os.path.exists(PDF_OUT) else None


if __name__ == "__main__":
    html = build_html()
    print(f"wrote {html} ({os.path.getsize(html) // 1024} KB)")
    pdf = render_pdf(html)
    if pdf:
        print(f"wrote {pdf} ({os.path.getsize(pdf) // 1024} KB)")
