"""
    Convert a Markdown file in TimelineJS format into the same JSON structure as csv_to_json.py.
    Designed for use with Obsidian: [[wiki-style links]] to other .md files are stripped
    (link text is kept when using [[target|display]], otherwise the target name is kept).

    MD format: each event/slide is a section starting with ## or ###. Use key: value lines
    (same names as CSV: Year, Month, Day, Time, or Start Year, Start Month, Start Day, Start Time;
    End Year, End Month, End Day, End Time; Display Date, Headline, Text, Media, Media Credit,
    Media Caption, Media Thumbnail, Type, Group, Background). Optional: heading can be
    "## YYYY-MM-DD" or "## YYYY-MM-DD — Headline" to set start date and/or headline.

    Example:
        ## Title Slide
        Type: title
        Headline: Women in Computing
        Text: <p>Introduction...</p>
        Background: https://...

        ## 1815-12-10 — Ada Lovelace
        End Year: 1852
        End Month: 11
        End Day: 27
        Text: She worked on [[Analytical Engine]] and ...
        Media: https://...
        Media Credit: Wikimedia Commons
"""
import json
import re
import sys
from datetime import datetime

# Same as csv_to_json; Start Year/Month/Day/Time are aliases for Year/Month/Day/Time
HEADERS = [
    "Year", "Month", "Day", "Time",
    "Start Year", "Start Month", "Start Day", "Start Time",
    "End Year", "End Month", "End Day", "End Time",
    "Display Date",
    "Headline", "Text",
    "Media", "Media Credit", "Media Caption", "Media Thumbnail",
    "Type", "Group", "Background",
]


def strip_obsidian_links(text):
    """Remove Obsidian [[link]] and [[link|display]] syntax; keep display text or link name."""
    if not text or not isinstance(text, str):
        return text
    # [[target|display]] -> display
    text = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", text)
    # [[target]] -> target
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    return text


def populate_time(time_str, target_dict):
    try:
        parsed = datetime.strptime(time_str.strip(), "%H:%M:%S")
        target_dict["hour"] = parsed.hour
        target_dict["minute"] = parsed.minute
        target_dict["second"] = parsed.second
    except ValueError:
        if time_str.strip():
            print(f"Invalid time string: {time_str!r}; must use %H:%M:%S format")


def parse_md_sections(content):
    """Split markdown into sections by ## or ###. Return list of (heading, body_text)."""
    sections = []
    current_heading = None
    current_body = []
    for line in content.splitlines():
        if line.startswith("##"):
            if current_heading is not None:
                sections.append((current_heading, "\n".join(current_body)))
            current_heading = line.lstrip("#").strip()
            current_body = []
        else:
            current_body.append(line)
    if current_heading is not None:
        sections.append((current_heading, "\n".join(current_body)))
    return sections


def parse_heading_date_and_headline(heading):
    """If heading is 'YYYY-MM-DD' or 'YYYY-MM-DD — Headline' or 'YYYY — Headline', return (y, m, d, headline)."""
    heading = heading.strip()
    # "1815-12-10 — Ada Lovelace" or "1815-12-10"
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})\s*[—\-–]\s*(.+)$", heading)
    if m:
        return m.group(1), m.group(2), m.group(3), m.group(4).strip()
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})\s*$", heading)
    if m:
        return m.group(1), m.group(2), m.group(3), None
    # "1952 — Grace Hopper invents the compiler" (year only)
    m = re.match(r"^(\d{4})\s*[—\-–]\s*(.+)$", heading)
    if m:
        return m.group(1), "", "", m.group(2).strip()
    m = re.match(r"^(\d{4})\s*$", heading)
    if m:
        return m.group(1), "", "", None
    return None, None, None, None


def parse_key_value_body(body):
    """Parse 'Key: value' lines; multiline values follow a colon line (indented)."""
    row = {h: "" for h in HEADERS}
    lines = body.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        for key in HEADERS:
            if line.startswith(key + ":"):
                value = line[len(key) + 1 :].strip()
                i += 1
                while i < len(lines) and lines[i].startswith(" ") and not any(
                    lines[i].strip().startswith(h + ":") for h in HEADERS
                ):
                    value += "\n" + lines[i].strip()
                    i += 1
                row[key] = value
                break
        else:
            i += 1
    return row


def section_to_row(heading, body):
    """Build a CSV-like dict from one MD section."""
    row = parse_key_value_body(body)
    # Prefer Start Year/Month/Day/Time from body over Year/Month/Day/Time
    if row.get("Start Year", "").strip():
        row["Year"] = row["Year"] or row["Start Year"]
        row["Month"] = row["Month"] or row.get("Start Month", "")
        row["Day"] = row["Day"] or row.get("Start Day", "")
        row["Time"] = row["Time"] or row.get("Start Time", "")
    hy, hm, hd, hheadline = parse_heading_date_and_headline(heading)
    if hy:
        if not row["Year"]:
            row["Year"] = hy
        if not row["Month"] and hm:
            row["Month"] = hm
        if not row["Day"] and hd:
            row["Day"] = hd
        if hheadline and not row["Headline"]:
            row["Headline"] = hheadline
    # Strip Obsidian links from text fields
    for key in ("Headline", "Text", "Media Caption", "Media Credit"):
        if row[key]:
            row[key] = strip_obsidian_links(row[key])
    return row


def row_to_json_event(csv_row):
    """Convert one CSV-like row to TimelineJS event dict (same as csv_to_json)."""
    json_row = {
        "media": {},
        "start_date": {},
        "end_date": {},
        "text": {},
    }
    json_row["media"]["url"] = csv_row["Media"]
    json_row["media"]["credit"] = csv_row["Media Credit"]
    json_row["media"]["caption"] = csv_row["Media Caption"]
    json_row["media"]["thumbnail"] = csv_row["Media Thumbnail"]

    json_row["text"]["headline"] = csv_row["Headline"]
    json_row["text"]["text"] = csv_row["Text"]

    json_row["start_date"]["year"] = csv_row["Year"]
    json_row["start_date"]["month"] = csv_row["Month"]
    json_row["start_date"]["day"] = csv_row["Day"]
    if csv_row["Time"]:
        populate_time(csv_row["Time"], json_row["start_date"])
    if csv_row["Display Date"]:
        json_row["start_date"]["display_date"] = csv_row["Display Date"]

    # Only include end_date if at least one end date field is set (match csv_to_json behavior)
    end_has_info = any(
        csv_row[k].strip() for k in ("End Year", "End Month", "End Day", "End Time")
    )
    if end_has_info:
        json_row["end_date"]["year"] = csv_row["End Year"]
        json_row["end_date"]["month"] = csv_row["End Month"]
        json_row["end_date"]["day"] = csv_row["End Day"]
        if csv_row["End Time"]:
            populate_time(csv_row["End Time"], json_row["end_date"])
    else:
        del json_row["end_date"]

    json_row["group"] = csv_row["Group"]
    if csv_row["Background"]:
        bg = csv_row["Background"].strip()
        if bg.startswith("http"):
            json_row["background"] = {"url": bg}
        else:
            json_row["background"] = {"color": bg}

    return json_row


def main(md_filename, json_filename=None):
    print(f"Reading data from {md_filename}")
    with open(md_filename) as f:
        content = f.read()

    out = {"events": []}
    sections = parse_md_sections(content)

    for heading, body in sections:
        if not heading and not body.strip():
            continue
        row = section_to_row(heading, body)
        json_row = row_to_json_event(row)

        if row["Type"] == "title":
            out["title"] = json_row
        elif row["Type"] == "era":
            out.setdefault("eras", []).append(json_row)
        else:
            out["events"].append(json_row)

    if json_filename:
        json.dump(out, open(json_filename, "w"), indent=2)
        print(f"Wrote {json_filename}")
    else:
        json.dump(out, sys.stdout, indent=2)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(
            f"Usage: {sys.argv[0]} input_filename.md [output_filename.json]\n"
            "If output_filename is not specified, will dump to standard out."
        )
        sys.exit(1)
    main(*sys.argv[1:])
