# Lebenslauf

Lebenslauf means CV in German. A CLI app that turns a YAML resume into a
print-ready A4 PDF.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The app uses Selenium Manager, so a separate driver install is usually not
needed. You do need a Chromium-based browser installed.

## Usage

```bash
python -m lebenslauf example_resume.yaml template.html -o resume.pdf
```

You can pass a browser executable explicitly:

```bash
python -m lebenslauf example_resume.yaml template.html -o resume.pdf --browser /usr/bin/brave-browser
```

If `--browser` is omitted, the app searches for Chromium, Brave, then Chrome. It exits with an error if none is found.

```bash
# Show help
python -m lebenslauf --help

# Save the processed HTML into rendered.html
python -m lebenslauf example/resume.yaml example/template.html --keep-html rendered.html

# Open the browser window
python -m lebenslauf example/resume.yaml example/template.html --show-browser
```

## YAML Format

```yaml
person:
  name: "John Doe"
  role: "Software Developer"
  contacts:
    phone: "+7 777 888 2233"
    mail: "john@example.com"
    telegram: "@johndoe"
    linkedin: "https://linkedin.com/in/johndoe"
    github: "https://github.com/johndoe"
    gitlab: "https://gitlab.com/johndoe"
experience:
  - company: "Great Company Inc."
    role: "QA Engineer"
    duration:
      start: "11 Aug 2024"
      end: "20 Sep 2025"
    responsibilities:
      - "Participated in manual testing of embedded software"
      - "Improved regression testing workflow"
skills:
  - "PostgreSQL"
  - "Linux"
certificates:
  - name: "Really Great Python Course"
    issuer: "Super Skill Academy"
languages:
  - name: "English"
    level: "native"
education:
  - academy: "Vulcan Technical University"
    specialization:
      type: "Specialization"
      name: "Mechanical Engineering"
    duration:
      start: "1 Sep 2020"
      end: "30 Oct 2024"
```

`person.name`, `person.role`, and `person.contacts` are required. The other top-level sections are optional.

## Template Contract

The CLI renders the user-supplied template with every YAML top-level key available as a Jinja variable. It also exposes the complete YAML dictionary as `resume`.

The user template must be an HTML fragment, not a full document. Do not include `<!doctype>`, `<html>`, `<head>`, `<body>`, or `<script>` tags. The app inserts the rendered fragment into its own system template, which owns the A4 sheet shell, print CSS, and on-screen page-boundary guides.

Templates are no longer constrained by browser-side pagination markup. Use whatever structure fits your layout; the browser will paginate naturally during printing, while the app shows dashed A4 boundary lines on screen as a visual guide only.

The included `template.html` is a user template example. The system template lives in `lebenslauf/template.html`; normal users do not need to pass it on the command line.
