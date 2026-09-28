"""Synthetic certificate generators, one per document type, with labelled entity spans.

Each template varies label wording, field order, layout (key: value, table rows, prose) and
date formats, and deliberately includes the look-alikes a regex gets wrong:
  - the OEM's own GSTIN beside the bidder's in an authorization letter (only the bidder's is labelled)
  - a "minimum local content of N%" threshold restated before the certified figure
  - validity *start* dates, incorporation and issue dates (only an expiry is VALID_UNTIL)
  - a PAN embedded inside a GSTIN (never labelled PAN)
  - past-year classifications in a Udyam certificate (only the current year's is CATEGORY)
  - UDIN, FRN, ESIC and membership numbers that look like identifiers but are none of ours
"""
import random
from datetime import date, timedelta

from ml.common.docbuilder import DocBuilder
from ml.common.entities import Company, random_company, random_date, variant_name

_FIRST = ["Rajesh", "Priya", "Amit", "Sunita", "Vikram", "Anita", "Suresh", "Kavita", "Arun", "Meena",
          "Rahul", "Deepa", "Sanjay", "Neha", "Manoj", "Pooja", "Ravi", "Lakshmi", "Harish", "Farah"]
_LAST = ["Sharma", "Patel", "Iyer", "Reddy", "Gupta", "Nair", "Singh", "Kulkarni", "Das", "Khan",
         "Mehta", "Rao", "Joshi", "Menon", "Verma", "Bose", "Pillai", "Chauhan", "Desai", "Qureshi"]
_STREETS = ["MIDC Industrial Area", "Industrial Estate", "Sector 18", "Ring Road", "GIDC Estate",
            "Okhla Phase II", "Peenya Industrial Area", "Guindy Industrial Estate", "Salt Lake Sector V"]
_PRODUCTS = ["laptops and desktops", "steel office furniture", "solar water heaters", "LED luminaires",
             "UPS systems", "network switches", "office chairs", "CCTV equipment"]
_DEPARTMENTS = ["Ministry of Electronics and IT", "CPWD", "Indian Railways", "DGS&D",
                "National Informatics Centre", "Ministry of New and Renewable Energy"]


def _person(rng: random.Random) -> str:
    return f"{rng.choice(_FIRST)} {rng.choice(_LAST)}"


def _address(rng: random.Random, c: Company) -> str:
    return (f"Plot No. {rng.randint(1, 400)}, {rng.choice(_STREETS)}, {c.city}, "
            f"{c.state_name} - {rng.randint(110001, 855999)}")


def fmt_date(rng: random.Random, d: date) -> str:
    return rng.choice([
        d.strftime("%d/%m/%Y"), d.strftime("%d-%m-%Y"), d.strftime("%d.%m.%Y"), d.isoformat(),
        f"{d.day} {d.strftime('%B')} {d.year}", d.strftime("%d-%b-%Y"), f"{d.strftime('%B')} {d.day}, {d.year}",
    ])


def _sep(rng: random.Random) -> str:
    return rng.choice([": ", " : ", " - ", "  ", ":  "])


def gst_certificate(rng: random.Random, b: DocBuilder, c: Company) -> None:
    b.line("Government of India")
    b.line(rng.choice(["Form GST REG-06", "FORM GST REG-06", "Form GST REG - 06"]))
    b.line("[See Rule 10(1)]")
    b.line("Registration Certificate")
    b.line(rng.choice(["Registration Number", "GSTIN", "Registration No."]), _sep(rng), ("GSTIN", c.gstin))
    rows = [
        ("legal", lambda: b.line(f"{rng.randint(1, 2)}. ",
                                 rng.choice(["Legal Name", "Legal Name of Business", "Name of Business"]),
                                 _sep(rng), ("LEGAL_NAME", c.legal_name))),
        ("trade", lambda: b.line(rng.choice(["Trade Name, if any", "Trade Name", "Trade Name (if any)"]),
                                 _sep(rng), ("TRADE_NAME", c.extra.get("doc_trade_name", c.trade_name)))),
    ]
    if rng.random() < 0.2:
        rows.reverse()
    for _, emit in rows:
        emit()
    if rng.random() < 0.3 and c.cin:
        b.line("CIN", _sep(rng), ("CIN", c.cin))
    b.line("Constitution of Business", _sep(rng), c.constitution)
    b.line("Address of Principal Place of Business", _sep(rng), _address(rng, c))
    b.line("Date of Liability", _sep(rng), fmt_date(rng, c.incorporated + timedelta(days=rng.randint(30, 900))))
    start = fmt_date(rng, random_date(rng, date(2017, 7, 1), date(2024, 12, 31)))
    # The validity *start* date is the classic false positive for an expiry field.
    b.line("Period of Validity  From", _sep(rng), start, "  To", _sep(rng), "Not Applicable")
    b.line("Type of Registration", _sep(rng), rng.choice(["Regular", "Composition"]))
    b.line("Particulars of Approving Authority: ", rng.choice(["Superintendent", "Assistant Commissioner"]))
    b.line("Jurisdictional Office: ", f"Range-{rng.randint(1, 20)}, Division-{rng.choice('ABCDE')}")
    b.line("Date of issue of Certificate", _sep(rng), fmt_date(rng, random_date(rng, date(2018, 1, 1), date(2025, 12, 31))))


def udyam_certificate(rng: random.Random, b: DocBuilder, c: Company) -> None:
    b.line("Government of India")
    b.line("Ministry of Micro, Small and Medium Enterprises")
    b.line(rng.choice(["UDYAM REGISTRATION CERTIFICATE", "Udyam Registration Certificate"]))
    b.line(rng.choice(["UDYAM REGISTRATION NUMBER", "Udyam Registration No.", "Registration Number"]), _sep(rng),
           ("UDYAM", c.udyam_number))
    b.line(rng.choice(["NAME OF ENTERPRISE", "Name of Enterprise"]), _sep(rng), ("LEGAL_NAME", c.legal_name))
    doc_category = c.extra.get("doc_category", c.category)
    if rng.random() < 0.6:
        # Classification table: several years; only the current year's type is the category.
        b.line("TYPE OF ENTERPRISE")
        b.line("SNo.  Classification Year  Enterprise Type  Classification Date")
        year = rng.randint(2023, 2025)
        b.line("1     ", f"{year}-{str(year + 1)[2:]}", "            ", ("CATEGORY", doc_category), "            ",
               fmt_date(rng, date(year, rng.randint(4, 9), rng.randint(1, 28))))
        for i in range(1, rng.randint(1, 3)):
            old = rng.choice(["Micro", "Small", "Medium"])
            b.line(f"{i + 1}     ", f"{year - i}-{str(year - i + 1)[2:]}", "            ", old, "            ",
                   fmt_date(rng, date(year - i, rng.randint(4, 9), rng.randint(1, 28))))
    else:
        b.line(rng.choice(["Type of Enterprise", "Enterprise Type", "Category"]), _sep(rng),
               ("CATEGORY", doc_category.upper() if rng.random() < 0.5 else doc_category))
    b.line(rng.choice(["MAJOR ACTIVITY", "Major Activity", "Nature of Activity"]), _sep(rng),
           ("ACTIVITY", c.extra.get("doc_activity", c.activity)))
    b.line("SOCIAL CATEGORY OF ENTREPRENEUR", _sep(rng), rng.choice(["General", "OBC", "SC", "ST"]))
    b.line("OFFICIAL ADDRESS OF ENTERPRISE", _sep(rng), _address(rng, c))
    b.line("DATE OF INCORPORATION / REGISTRATION OF ENTERPRISE", _sep(rng), fmt_date(rng, c.incorporated))
    b.line("DATE OF COMMENCEMENT OF PRODUCTION/BUSINESS", _sep(rng),
           fmt_date(rng, c.incorporated + timedelta(days=rng.randint(10, 400))))
    b.line("NATIONAL INDUSTRY CLASSIFICATION CODE(S)", _sep(rng), f"{rng.randint(10, 99)} - {rng.randint(1000, 9999)}")
    b.line("DATE OF UDYAM REGISTRATION", _sep(rng), fmt_date(rng, random_date(rng, date(2020, 7, 1), date(2025, 6, 30))))


def mii_certificate(rng: random.Random, b: DocBuilder, c: Company) -> None:
    threshold = c.extra.get("mii_threshold", rng.choice([20, 25, 40, 50, 60]))
    actual = c.extra.get("doc_local_content", rng.randint(15, 90))
    actual_text = str(actual) if rng.random() < 0.85 else f"{actual}.{rng.randint(1, 9)}"
    b.line(rng.choice(["MAKE IN INDIA - SELF CERTIFICATION", "Self-Certification under Make in India Policy",
                       "Annexure - Format for Self Certification of Local Content"]))
    b.line(f"(Public Procurement (Preference to Make in India) Order, {rng.choice([2017, 2020])})")
    b.line("To: ", rng.choice(_DEPARTMENTS))
    b.line(f"Bid Reference: GEM/2026/B/{rng.randint(1000000, 9999999)}")
    style = rng.random()
    if style < 0.45:
        b.line("We, M/s ", ("LEGAL_NAME", c.legal_name), ", GSTIN ", ("GSTIN", c.gstin),
               ", hereby certify that the item(s) offered meet the minimum local content requirement of ",
               f"{threshold}%", " for 'Class-I local supplier'.")
        b.line("The local content of the item(s) offered is ", ("LOCAL_CONTENT", actual_text), "%.")
    elif style < 0.8:
        b.line("Name of Bidder", _sep(rng), ("LEGAL_NAME", c.legal_name))
        b.line("GSTIN of Bidder", _sep(rng), ("GSTIN", c.gstin))
        b.line("Minimum local content required as per tender", _sep(rng), f"{threshold}%")
        b.line(rng.choice(["Percentage of local content", "Local Content (%)", "Local content in offered item"]),
               _sep(rng), ("LOCAL_CONTENT", actual_text), rng.choice(["%", " %", ""]))
    else:
        b.line(f"Class-I local supplier: local content of {threshold}% or more. "
               f"Class-II local supplier: more than 20% but less than {threshold}%.")
        b.line("We M/s ", ("LEGAL_NAME", c.legal_name), " certify that local content in the offered goods is ",
               ("LOCAL_CONTENT", actual_text), " percent.")
        b.line("GSTIN: ", ("GSTIN", c.gstin))
    b.line("The local value addition is made at ", f"{c.city}, {c.state_name}.")
    b.line("Authorised Signatory: ", _person(rng), "   Date: ", fmt_date(rng, random_date(rng, date(2025, 1, 1), date(2026, 9, 1))))


def pan_card(rng: random.Random, b: DocBuilder, c: Company) -> None:
    b.line(rng.choice(["INCOME TAX DEPARTMENT", "Income Tax Department"]), "      GOVT. OF INDIA")
    b.line(rng.choice(["Permanent Account Number Card", "Permanent Account Number", "PAN"]))
    b.line(("PAN", c.pan))
    b.line(rng.choice(["Name", "NAME"]))
    b.line(("LEGAL_NAME", c.legal_name.upper() if rng.random() < 0.6 else c.legal_name))
    b.line(rng.choice(["Date of Incorporation/Formation", "Date of Registration"]))
    b.line(fmt_date(rng, c.incorporated))


def epfo_certificate(rng: random.Random, b: DocBuilder, c: Company) -> None:
    b.line(rng.choice(["EMPLOYEES' PROVIDENT FUND ORGANISATION", "Employees' Provident Fund Organisation"]))
    b.line("Ministry of Labour & Employment, Government of India")
    b.line(f"Regional Office: {c.city}")
    b.line(rng.choice(["Certificate of Compliance", "PF Compliance Certificate", "Labour Law Compliance Undertaking"]))
    b.line(rng.choice(["Establishment Code", "Establishment ID", "PF Code No."]), _sep(rng), ("EPFO", c.establishment_code))
    b.line("Name of Establishment", _sep(rng), ("LEGAL_NAME", c.legal_name))
    b.line("Number of employees covered", _sep(rng), str(c.extra.get("doc_employees", c.employee_count)))
    b.line("ESIC Code No.", _sep(rng), f"{rng.randint(10, 99)}{rng.randint(0, 10**15 - 1):015d}")
    month = random_date(rng, date(2025, 1, 1), date(2026, 8, 31))
    b.line(f"This is to certify that the establishment has remitted contributions up to {month.strftime('%B %Y')}.")
    b.line("Date: ", fmt_date(rng, month + timedelta(days=rng.randint(5, 40))))


def dpiit_certificate(rng: random.Random, b: DocBuilder, c: Company) -> None:
    b.line("Government of India")
    b.line("Ministry of Commerce & Industry")
    b.line("Department for Promotion of Industry and Internal Trade")
    b.line(rng.choice(["Certificate of Recognition", "CERTIFICATE OF RECOGNITION"]))
    b.line("This is to certify that ", ("LEGAL_NAME", c.legal_name),
           f" incorporated as a {c.constitution} on ", fmt_date(rng, c.incorporated),
           " is recognized as a startup by the Department for Promotion of Industry and Internal Trade.")
    b.line(rng.choice(["Certificate No.", "DPIIT No.", "Recognition Number"]), _sep(rng), ("DPIIT", c.dpiit_number))
    b.line("Industry", _sep(rng), rng.choice(["IT Services", "Renewable Energy", "Hardware", "AgriTech"]))
    b.line("Date of Issue", _sep(rng), fmt_date(rng, c.incorporated + timedelta(days=rng.randint(60, 700))))
    valid = c.extra.get("doc_valid_until", c.incorporated + timedelta(days=365 * 10))
    b.line(rng.choice(["Valid upto", "Valid until", "Validity until", "Expiry Date"]), _sep(rng),
           ("VALID_UNTIL", fmt_date(rng, valid)))


def oem_authorization(rng: random.Random, b: DocBuilder, c: Company) -> None:
    oem = random_company(rng, category="Large")
    b.line(rng.choice(["MANUFACTURER'S AUTHORIZATION FORM", "OEM Authorization Certificate", "Annexure VII"]))
    b.line("To,")
    b.line("The Buyer, ", rng.choice(_DEPARTMENTS))
    b.line(f"Ref: Bid No. GEM/2026/B/{rng.randint(1000000, 9999999)}")
    # The OEM's own name and GSTIN come first: a look-alike that must not be extracted.
    b.line(f"We, {oem.legal_name}, GSTIN {oem.gstin}, who are established and reputable manufacturers of "
           f"{rng.choice(_PRODUCTS)} having factories at {oem.city}, {oem.state_name}, do hereby authorize")
    b.line("M/s ", ("LEGAL_NAME", c.legal_name), ", ", _address(rng, c), ", GSTIN ", ("GSTIN", c.gstin),
           ", to submit a bid and sign the contract with you for the goods manufactured by us.")
    b.line("We hereby extend our full guarantee and warranty for the goods offered.")
    if rng.random() < 0.6:
        valid = random_date(rng, date(2026, 10, 1), date(2028, 12, 31))
        b.line(rng.choice(["This authorization is valid until ", "Valid up to "]), ("VALID_UNTIL", fmt_date(rng, valid)), ".")
    b.line("For ", oem.legal_name)
    b.line("Authorized Signatory: ", _person(rng), "   Date: ", fmt_date(rng, random_date(rng, date(2026, 1, 1), date(2026, 9, 20))))


def turnover_certificate(rng: random.Random, b: DocBuilder, c: Company) -> None:
    b.line(rng.choice(["TO WHOMSOEVER IT MAY CONCERN", "TURNOVER CERTIFICATE"]))
    b.line("This is to certify that M/s ", ("LEGAL_NAME", c.legal_name), " having PAN ", ("PAN", c.pan),
           " and GSTIN ", ("GSTIN", c.gstin), " has achieved the following turnover as per audited accounts:")
    if c.cin and rng.random() < 0.5:
        b.line("CIN: ", ("CIN", c.cin))
    year = rng.randint(2023, 2025)
    for fy in range(year - 3, year):
        b.line(f"FY {fy}-{str(fy + 1)[2:]}    Rs. {rng.randint(10, 999)},{rng.randint(10, 99)},{rng.randint(100, 999)},{rng.randint(100, 999)}")
    b.line(f"For {rng.choice(_LAST)} & Associates, Chartered Accountants")
    b.line(f"FRN: {rng.randint(100000, 999999)}{rng.choice('WSNEC')}")
    b.line(f"CA {_person(rng)}, Partner, Membership No. {rng.randint(100000, 999999)}")
    b.line(f"UDIN: {rng.randint(20, 26)}{rng.randint(100000, 999999)}{''.join(rng.choice('ABCDEFGHJKLMNPQRSTUVWXYZ') for _ in range(6))}{rng.randint(1000, 9999)}")
    b.line("Place: ", c.city, "   Date: ", fmt_date(rng, random_date(rng, date(2025, 1, 1), date(2026, 9, 1))))


def nsic_certificate(rng: random.Random, b: DocBuilder, c: Company) -> None:
    b.line("The National Small Industries Corporation Ltd.")
    b.line("Single Point Registration Scheme - Certificate of Registration")
    b.line(f"Registration No.: NSIC/GP/{c.city_code}/{rng.randint(2018, 2024)}/{rng.randint(0, 9999999):07d}")
    b.line("Name of Unit", _sep(rng), ("LEGAL_NAME", c.legal_name))
    b.line("Udyam Registration No.", _sep(rng), ("UDYAM", c.udyam_number))
    b.line("Category", _sep(rng), ("CATEGORY", c.extra.get("doc_category", c.category)), " Enterprise")
    b.line("Nature of Activity", _sep(rng), ("ACTIVITY", c.activity))
    start = random_date(rng, date(2023, 1, 1), date(2025, 12, 31))
    end = start + timedelta(days=365 * rng.randint(1, 3))
    # "Valid from X to Y": only Y is an expiry.
    b.line("Valid from ", fmt_date(rng, start), " to ", ("VALID_UNTIL", fmt_date(rng, end)))


TEMPLATES = {
    "GST_CERTIFICATE": gst_certificate,
    "UDYAM_CERTIFICATE": udyam_certificate,
    "EMD_EXEMPTION_PROOF": udyam_certificate,
    "MII_LOCAL_CONTENT_SELF_CERTIFICATE": mii_certificate,
    "PAN_CARD": pan_card,
    "EPFO_ESIC_COMPLIANCE_CERTIFICATE": epfo_certificate,
    "STARTUP_EMD_EXEMPTION_PROOF": dpiit_certificate,
    "OEM_AUTHORIZATION_LETTER": oem_authorization,
    "TURNOVER_CERTIFICATE_CA": turnover_certificate,
    "NSIC_CERTIFICATE": nsic_certificate,
}


def generate_document(rng: random.Random, doc_type: str | None = None) -> dict:
    """One labelled synthetic certificate: {doc_type, text, spans, noise}."""
    doc_type = doc_type or rng.choice(list(TEMPLATES))
    company = random_company(rng)
    if rng.random() < 0.15:
        company.extra["doc_trade_name"] = variant_name(rng, company.trade_name)

    # Half are clean text-layer PDFs; the rest carry mild-to-heavy OCR noise.
    noise = rng.choice([0.0, 0.0, 0.0, 0.005, 0.01, 0.02])
    builder = DocBuilder(rng, doc_type, noise=noise, uppercase=rng.random() < 0.08)
    TEMPLATES[doc_type](rng, builder, company)
    return {**builder.build(), "noise": noise}
