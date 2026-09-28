"""Synthetic Indian business entities for training data.

Every identifier follows the real format (GSTIN with a valid mod-36 check character, PAN whose
4th letter encodes the holder type, Udyam/CIN/EPFO/DPIIT layouts) but is random: none
corresponds to a real registered entity.
"""
import random
from dataclasses import dataclass, field
from datetime import date, timedelta

_GSTIN_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

# (GST state code, Udyam/CIN state abbreviation, state name, EPFO regional office codes)
STATES = [
    ("27", "MH", "Maharashtra", ["BAN", "PUN", "THN", "MUM", "NAG"]),
    ("29", "KA", "Karnataka", ["BLR", "MYS", "HBL", "MNG"]),
    ("07", "DL", "Delhi", ["NDL", "SDL", "EDL"]),
    ("24", "GJ", "Gujarat", ["AHM", "SRT", "VDR", "RJK"]),
    ("08", "RJ", "Rajasthan", ["JAI", "JOD", "UDR", "KOT"]),
    ("33", "TN", "Tamil Nadu", ["CHE", "CBE", "MDU", "TRY"]),
    ("09", "UP", "Uttar Pradesh", ["LKO", "KNP", "NOI", "AGR"]),
    ("19", "WB", "West Bengal", ["KOL", "DGP", "SLG"]),
    ("36", "TS", "Telangana", ["HYD", "WGL"]),
    ("32", "KL", "Kerala", ["TVM", "KCH", "KZD"]),
    ("06", "HR", "Haryana", ["GGN", "FBD", "PNP"]),
    ("23", "MP", "Madhya Pradesh", ["BPL", "IND", "JBP"]),
]

_NAME_ROOTS = [
    "Nova", "Bharat", "Suresh", "Global", "Kiran", "Solar", "Metro", "Aadhya", "Om", "Precision",
    "Digital", "Sunrise", "Shree", "Ganesh", "Lakshmi", "Tirupati", "Vishwa", "Apex", "Pioneer",
    "Sai", "Jai", "Mahalaxmi", "Balaji", "Krishna", "Ashoka", "Indus", "Ganga", "Himalaya",
    "Deccan", "Eastern", "Western", "Coastal", "Sahyadri", "Vindhya", "Narmada", "Kaveri",
    "Trident", "Orbit", "Zenith", "Quantum", "Vertex", "Sterling", "Royal", "United", "National",
    "Prime", "Elite", "Supreme", "Vardhman", "Shakti", "Arihant", "Siddhi", "Mangal", "Anand",
]
_NAME_MIDDLES = [
    "Electro", "Steel", "Tech", "Infra", "Power", "Agro", "Pharma", "Textile", "Auto", "Solar",
    "Info", "Enviro", "Build", "Chem", "Plast", "Fab", "Print", "Security", "Facility", "Logistics",
    "Manpower", "Engineering", "Electricals", "Furnishers", "Traders", "Components", "Systems",
]
_NAME_TAILS = [
    "Systems", "Works", "Enterprises", "Solutions", "Industries", "Services", "Technologies",
    "Traders", "Corporation", "Associates", "Products", "Renewables", "Infotech", "Components",
    "Engineers", "Suppliers", "Ventures", "Exports", "Manufacturers", "Facilities",
]
# (legal-name suffix, CIN company-type code or None, PAN 4th letter)
_CONSTITUTIONS = [
    ("Private Limited", "PTC", "C"),
    ("Pvt Ltd", "PTC", "C"),
    ("Pvt. Ltd.", "PTC", "C"),
    ("Limited", "PLC", "C"),
    ("LLP", None, "F"),
    ("", None, "F"),  # partnership firm
    ("", None, "P"),  # proprietorship
]

ACTIVITIES = [
    ("manufacturer", "Manufacturing - Electronics"),
    ("manufacturer", "Manufacturing - Fabricated Metal Products"),
    ("manufacturer", "Manufacturing - Furniture"),
    ("manufacturer", "Manufacturing - Electrical Equipment"),
    ("manufacturer", "Manufacturing - Renewable Energy Equipment"),
    ("manufacturer", "Manufacturing - Textiles"),
    ("manufacturer", "Manufacture of Computer Peripherals"),
    ("trader", "Trading - IT Hardware"),
    ("trader", "Trading - Office Supplies"),
    ("trader", "Wholesale Trading - Electrical Goods"),
    ("services", "IT Services"),
    ("services", "Services - Security and Facility Management"),
    ("services", "Manpower Supply Services"),
    ("services", "Maintenance and Repair Services"),
]

MSME_CATEGORIES = ("Micro", "Small", "Medium")

CITIES = {
    "MH": ["Mumbai", "Pune", "Thane", "Nagpur", "Nashik"],
    "KA": ["Bengaluru", "Mysuru", "Hubballi", "Mangaluru"],
    "DL": ["New Delhi", "Dwarka", "Rohini"],
    "GJ": ["Ahmedabad", "Surat", "Vadodara", "Rajkot"],
    "RJ": ["Jaipur", "Jodhpur", "Udaipur", "Kota"],
    "TN": ["Chennai", "Coimbatore", "Madurai", "Tiruchirappalli"],
    "UP": ["Lucknow", "Kanpur", "Noida", "Agra"],
    "WB": ["Kolkata", "Durgapur", "Siliguri"],
    "TS": ["Hyderabad", "Warangal"],
    "KL": ["Thiruvananthapuram", "Kochi", "Kozhikode"],
    "HR": ["Gurugram", "Faridabad", "Panipat"],
    "MP": ["Bhopal", "Indore", "Jabalpur"],
}


def gstin_check_char(first14: str) -> str:
    """The GSTIN's 15th character: mod-36 Luhn-style checksum over the first 14."""
    total = 0
    for i, ch in enumerate(first14):
        product = _GSTIN_CHARS.index(ch) * (2 if i % 2 else 1)
        total += product // 36 + product % 36
    return _GSTIN_CHARS[(36 - total % 36) % 36]


def random_pan(rng: random.Random, holder_type: str, name: str) -> str:
    first = "".join(rng.choice(_LETTERS) for _ in range(3))
    initial = next((c for c in name.upper() if c.isalpha()), "X")
    return f"{first}{holder_type}{initial}{rng.randint(0, 9999):04d}{rng.choice(_LETTERS)}"


def random_gstin(rng: random.Random, state_code: str, pan: str) -> str:
    entity = rng.choice("123456789" + "ABC")
    first14 = f"{state_code}{pan}{entity}Z"
    return first14 + gstin_check_char(first14)


def random_date(rng: random.Random, start: date, end: date) -> date:
    return start + timedelta(days=rng.randint(0, (end - start).days))


@dataclass
class Company:
    legal_name: str
    trade_name: str
    pan: str
    gstin: str
    state_code: str
    state_abbr: str
    state_name: str
    city_code: str
    constitution: str
    udyam_number: str
    cin: str | None
    establishment_code: str
    dpiit_number: str
    activity_role: str
    activity: str
    category: str
    employee_count: int
    incorporated: date
    city: str = ""
    extra: dict = field(default_factory=dict)


def random_company(rng: random.Random, *, category: str | None = None) -> Company:
    state_code, state_abbr, state_name, offices = rng.choice(STATES)
    core = rng.choice(_NAME_ROOTS)
    if rng.random() < 0.6:
        core += " " + rng.choice(_NAME_MIDDLES)
    core += " " + rng.choice(_NAME_TAILS)
    suffix, cin_type, holder = rng.choice(_CONSTITUTIONS)
    legal_name = f"{core} {suffix}".strip()
    # Trade names usually drop the legal suffix; some businesses trade under a variant.
    trade_name = core if rng.random() < 0.85 else core.replace(" and ", " & ")
    pan = random_pan(rng, holder, core)
    incorporated = random_date(rng, date(1990, 1, 1), date(2022, 12, 31))

    category = category or rng.choices(["Micro", "Small", "Medium", "Large"], weights=[25, 40, 20, 15])[0]
    employees = {
        "Micro": rng.randint(2, 20),
        "Small": rng.randint(10, 60),
        "Medium": rng.randint(40, 250),
        "Large": rng.randint(200, 3000),
    }[category]
    role, activity = rng.choice(ACTIVITIES)

    cin = None
    if cin_type:
        cin = (
            f"{rng.choice('UL') if cin_type == 'PLC' else 'U'}{rng.randint(10000, 99999)}"
            f"{state_abbr}{incorporated.year}{cin_type}{rng.randint(0, 999999):06d}"
        )

    return Company(
        legal_name=legal_name,
        trade_name=trade_name,
        pan=pan,
        gstin=random_gstin(rng, state_code, pan),
        state_code=state_code,
        state_abbr=state_abbr,
        state_name=state_name,
        city_code=rng.choice(offices),
        constitution=suffix or ("Partnership" if holder == "F" else "Proprietorship"),
        udyam_number=f"UDYAM-{state_abbr}-{rng.randint(1, 45):02d}-{rng.randint(0, 9999999):07d}",
        cin=cin,
        establishment_code=f"{state_abbr}/{rng.choice(offices)}/{rng.randint(0, 9999999):07d}/{rng.randint(0, 999):03d}",
        dpiit_number=f"DIPP{rng.randint(1000, 999999)}",
        activity_role=role,
        activity=activity,
        category=category,
        employee_count=employees,
        incorporated=incorporated,
        city=rng.choice(CITIES[state_abbr]),
    )


def variant_name(rng: random.Random, name: str) -> str:
    """A plausibly different business name: what a tampered or outdated certificate shows."""
    words = name.split()
    move = rng.random()
    if move < 0.4:
        words.insert(max(1, len(words) - 1), rng.choice(["&", "and"]) + " " + rng.choice(_NAME_MIDDLES))
    elif move < 0.7:
        words[0] = rng.choice([w for w in _NAME_ROOTS if w != words[0]])
    else:
        words[-1] = rng.choice([w for w in _NAME_TAILS if w != words[-1]])
    return " ".join(words)
