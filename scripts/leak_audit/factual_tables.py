"""Extract factual appendix columns; never import the ECtHR outcome columns."""
import re
from bs4 import BeautifulSoup

EXCLUDE = re.compile(r"amount awarded|key issues|other complaints|violation(?:s)? found|"
    r"article(?:s)? violated|court.s (?:findings|assessment)|just satisfaction|"
    r"relevant case.law|^Case-law$|non.pecuniary|costs and expenses|"
    r"key argument|key issue|specific defects|procedural deficiencies|"
    r"shortcomings in medical treatment|amount requested|amount claimed|"
    r"amount to be paid|reasons for inadmissibility", re.I)
INCLUDE = re.compile(r"^(?:No\.?$|Application|Applicant|Representative|Start|End|"
    r"Total length|Length|Duration|Period|Date|Domestic|Relevant domestic|"
    r"Background|Detention|Facility|Facilities|Prison|Space|Number of inmates|"
    r"Number of detainees|Specific grievances|Grievances|Conditions|Nature|Type|"
    r"Details|Proceedings|Final domestic|Criminal proceedings|Civil proceedings|"
    r"Case name|Lodged on|Represented by|Subject matter|Summary of facts|"
    r"Main complaints|Name of the|Grounds for detention|Sq\.\s*m|"
    r"Administrative|Location|Other relevant|Penalty|Enforceable domestic|"
    r"Court which issued|Judicial decision|Final decision in the forfeiture|"
    r"Forfeited assets|Predicate offence|Reasons given by the courts|"
    r"Reasons for absence|Witness absent|Decision under|Factual information|"
    r"Information relating|Medical evidence|Turkish Constitutional|Appellate court|"
    r"Facts and relevant|Principal medical condition|House arrest|"
    r"Specific circumstances|Inmates per brigade|Impugned judgment|"
    r"Communicated Complaints|Respondent State|Particular circumstances|"
    r"Year of birth|Nationality|Place of residence)", re.I)


def grid(table):
    pending, rows = {}, []
    for tr in table.find_all("tr"):
        if tr.find_parent("table") is not table:
            continue
        row = {col: value for col, (value, count) in pending.items()}
        pending = {col: (value, count-1) for col, (value, count) in pending.items() if count > 1}
        col = 0
        for cell in tr.find_all(["td", "th"], recursive=False):
            while col in row:
                col += 1
            value = re.sub(r"\s+", " ", cell.get_text(" ", strip=True))
            span, height = int(cell.get("colspan", 1)), int(cell.get("rowspan", 1))
            for offset in range(span):
                row[col+offset] = value
                if height > 1:
                    pending[col+offset] = (value, height-1)
            col += span
        if row:
            rows.append([row.get(i, "") for i in range(max(row)+1)])
    return rows


def extract(html, application_numbers):
    wanted = set(re.findall(r"\d+/\d{2}\b", application_numbers))
    chunks, included, excluded, unknown = [], set(), set(), set()
    for table in BeautifulSoup(html, "html.parser").find_all("table"):
        rows = grid(table)
        if len(rows) < 2:
            continue
        headers = rows[0]
        if re.match(r"\d+\. Application no\.", headers[0]):
            # Some joined Ukrainian cases use one fact/assessment table per
            # applicant, and multiple sections or applicants inside one table.
            # Import only the explicitly factual columns, never 'Key issues'.
            active, app_wanted = [], False
            for row in rows:
                first = row[0]
                if re.match(r"\d+\. Application no\.", first):
                    app_wanted = bool(set(re.findall(r"\d+/\d{2}\b", first)) & wanted)
                    active = []
                    if app_wanted:
                        chunks.append(first)
                    continue
                if any(re.fullmatch(r"Key issues", value, re.I) for value in row):
                    active = [(i, value) for i,value in enumerate(row)
                        if re.match(r"Alleged ill.treatment|Applicant.s account|Domestic investigation", value, re.I)]
                    included.update(label for _,label in active)
                    excluded.add("Key issues")
                    continue
                if len(set(row)) == 1 and re.match(r"[A-D]\. ", first):
                    active = []
                    if "Other complaints" in first or "Just satisfaction" in first:
                        excluded.add(first)
                    continue
                if app_wanted and active:
                    values = list(dict.fromkeys(f"{label}: {row[i]}" for i,label in active if row[i]))
                    chunks.extend(values)
                    active = []
            continue
        app_cols = [i for i,h in enumerate(headers) if re.search(r"Application.*(?:no|number)", h, re.I)]
        identity_table = not app_cols and all(re.match(
            r"No\.?$|Applicant.s [Nn]ame|Year of birth|Nationality|Place of residence", h) for h in headers)
        if not app_cols and not identity_table:
            continue
        keep = []
        for i, header in enumerate(headers):
            # Compensation ordered by domestic courts is case history, not the
            # ECtHR's just-satisfaction award.
            domestic = bool(re.match(r"Domestic|Relevant domestic|Final domestic", header, re.I))
            if EXCLUDE.search(header) and not domestic:
                excluded.add(header)
            elif INCLUDE.search(header):
                keep.append(i)
                included.add(header)
            elif header.strip():
                unknown.add(header)
        for row in rows[1:]:
            if len(row) != len(headers):
                raise ValueError("Appendix table shape needs manual review")
            applications = set(re.findall(r"\d+/\d{2}\b", " ".join(row[i] for i in app_cols)))
            if not identity_table and not applications & wanted:
                continue
            lines = [f"{headers[i]}: {row[i]}" for i in keep if row[i].strip()]
            if lines:
                chunks.append("\n".join(lines))
    if unknown:
        raise ValueError("Unreviewed appendix headers: " + repr(sorted(unknown)))
    if not chunks:
        raise ValueError("No matching factual appendix rows")
    return "\n\n".join(chunks), sorted(included), sorted(excluded)
