"""Universe definition for the Malaysia healthcare dashboard.

Symbols are TradingView "EXCHANGE:TICKER" ids. Edit this file to add/remove names.
"""

STOCKS = [
    # symbol, Bursa stock code, short, name, segment, news aliases (case-insensitive match in headlines)
    {"symbol": "MYX:IHH", "code": "5225", "short": "IHH", "name": "IHH Healthcare", "segment": "Hospitals",
     "aliases": ["IHH", "Pantai", "Gleneagles", "Prince Court", "Acibadem", "Parkway"],
     "fx": ["FX_IDC:SGDMYR", "SYN:TRYMYR", "FX_IDC:INRMYR"]},
    {"symbol": "MYX:KPJ", "code": "5878", "short": "KPJ", "name": "KPJ Healthcare", "segment": "Hospitals",
     "aliases": ["KPJ", "KJP Healthcare"]},
    {"symbol": "MYX:SUNMED", "code": "5555", "short": "SUNMED", "name": "Sunway Healthcare", "segment": "Hospitals",
     "aliases": ["Sunway Healthcare", "SunMed", "Sunway Medical"]},
    {"symbol": "MYX:PMCK", "code": "0363", "short": "PMCK", "name": "PMCK Berhad", "segment": "Hospitals",
     "aliases": ["PMCK", "Putra Medical"]},
    {"symbol": "MYX:OPTIMAX", "code": "0222", "short": "OPTIMAX", "name": "Optimax Holdings", "segment": "Specialist clinics",
     "aliases": ["Optimax"]},
    {"symbol": "MYX:DPHARMA", "code": "7148", "short": "DPHARMA", "name": "Duopharma Biotech", "segment": "Pharma",
     "aliases": ["Duopharma"],
     "fx": ["FX_IDC:PHPMYR", "SYN:BNDMYR", "FX_IDC:SGDMYR"]},
    {"symbol": "MYX:PHARMA", "code": "7081", "short": "PHARMA", "name": "Pharmaniaga", "segment": "Pharma",
     "aliases": ["Pharmaniaga"],
     "fx": ["FX_IDC:USDMYR"]},
]

# Apex Healthcare (AHEALTH, 7090) was privatised by a Quadria-led consortium and delisted 27 Jan 2026.

INDICES = [
    {"symbol": "MYX:HEALTH", "short": "Bursa Health Care", "country": "MY"},
    {"symbol": "FTSEMYX:FBMKLCI", "short": "FBM KLCI", "country": "MY"},
    {"symbol": "SET:HELTH", "short": "SET Health Care", "country": "TH"},
    {"symbol": "IDX:IDXHEALTH", "short": "IDX Healthcare", "country": "ID"},
]

# FX pairs: price = MYR per 1 unit of foreign currency (pair up = ringgit weaker).
# "synthetic" pairs have no direct TradingView listing and are computed as num / den.
COMMODITIES = [
    {"symbol": "FX_IDC:USDMYR", "short": "USD/MYR", "group": "FX",
     "drives": "Imported APIs, devices & consumables are USD-priced; weaker ringgit squeezes pharma margins under price-controlled tenders."},
    {"symbol": "FX_IDC:SGDMYR", "short": "SGD/MYR", "group": "FX",
     "drives": "Translation of Singapore earnings: IHH's Parkway hospitals and Duopharma's Singapore business."},
    {"symbol": "FX_IDC:INRMYR", "short": "INR/MYR", "group": "FX",
     "drives": "IHH's India hospitals (Fortis, Gleneagles India). India is also the main source of finished generics and many APIs."},
    {"symbol": "SYN:TRYMYR", "short": "TRY/MYR", "group": "FX",
     "synthetic": {"num": "FX_IDC:USDMYR", "den": "FX_IDC:USDTRY"},
     "drives": "IHH's Acibadem (Türkiye). Lira depreciation and hyperinflation accounting weigh on translated earnings. Computed as USD/MYR ÷ USD/TRY."},
    {"symbol": "FX_IDC:PHPMYR", "short": "PHP/MYR", "group": "FX",
     "drives": "Duopharma's Philippines business."},
    {"symbol": "SYN:BNDMYR", "short": "BND/MYR", "group": "FX",
     "synthetic": {"num": "FX_IDC:USDMYR", "den": "FX_IDC:USDBND"},
     "drives": "Duopharma's Brunei business. BND is pegged 1:1 to SGD, so this tracks SGD/MYR. Computed as USD/MYR ÷ USD/BND."},
    {"symbol": "FX_IDC:CNYMYR", "short": "CNY/MYR", "group": "FX",
     "drives": "China supplies the bulk of key starting materials and generic APIs."},
    {"symbol": "CME:HE1!", "short": "Lean hogs", "group": "Agri",
     "drives": "Proxy for heparin (porcine intestinal mucosa) and other porcine-derived inputs."},
    {"symbol": "CBOT:ZC1!", "short": "Corn", "group": "Agri",
     "drives": "Starch/dextrose feedstock for fermentation APIs (antibiotics, vitamins) and IV glucose."},
    {"symbol": "ICEUS:SB1!", "short": "Sugar No.11", "group": "Agri",
     "drives": "Fermentation feedstock and syrup/excipient input."},
    {"symbol": "NYMEX:CL1!", "short": "WTI crude", "group": "Energy",
     "drives": "Petrochemical solvents & synthesis intermediates; plastics for packaging and consumables."},
    {"symbol": "ICEEUR:BRN1!", "short": "Brent crude", "group": "Energy",
     "drives": "Regional energy benchmark; hospital utility and logistics costs."},
    {"symbol": "NYMEX:NG1!", "short": "Natural gas", "group": "Energy",
     "drives": "Energy-intensive API synthesis and solvent recovery."},
    {"symbol": "NYMEX:PA1!", "short": "Palladium", "group": "Metals",
     "drives": "Hydrogenation / cross-coupling catalyst in small-molecule API synthesis."},
]

# Sector-level Google News queries (Malaysia edition), tagged as sector news.
SECTOR_QUERIES = [
    '"Bursa" healthcare stocks',
    'Malaysia "Ministry of Health" OR "MOH" hospital OR medicine',
    'Malaysia "medical inflation" OR "medical insurance" OR "takaful" repricing',
    'Malaysia "drug price" OR "medicine price" OR "price control" pharmaceutical',
    'Malaysia NPRA OR "drug registration" OR "Pharmaceutical Services"',
    'Malaysia Budget 2027 health',
    'Malaysia private hospital',
]

# Global API / raw-material supply news (not filtered to Malaysia), tagged "Supply chain / API".
API_QUERIES = [
    '"active pharmaceutical ingredient" OR "APIs" pharma China OR India prices OR supply',
    'heparin supply OR price OR shortage',
    'pharmaceutical "raw material" OR "key starting material" prices',
    '"drug shortage" OR "medicine shortage" Asia',
    'paracetamol OR antibiotic OR penicillin API price China',
]

# Keyword tagging: (tag, regex). First-match ordering doesn't matter; all matching tags are applied.
TAGS = [
    ("Earnings", r"\b(quarter|1Q|2Q|3Q|4Q|Q[1-4]|FY\d|net profit|earnings|revenue|EPS|results|dividend)\b"),
    ("Contract / tender", r"\b(tender|contract|concession|supply agreement|awarded|LOA|letter of award)\b"),
    ("M&A / corporate", r"\b(acqui|merger|takeover|privati|stake|IPO|listing|placement|rights issue|consolidation|SpA|disposal|bonus issue)\w*"),
    ("Policy / regulation", r"\b(ministry|MOH|minister|government|regulat|NPRA|price control|budget|policy|Bank Negara|BNM|insurance|takaful|reprici|Dzulkefly|PN17)\w*"),
    ("Analyst", r"\b(target price|TP|upgrade|downgrade|maintain|buy call|outperform|underperform|rating|analyst|research|stock picks?|market talk)\b"),
    ("Expansion", r"\b(new hospital|expansion|beds?|opens?|launch|capex|construction|commence)\b"),
    ("Management", r"\b(CEO|MD|managing director|chairman|resign|appoint|board)\b"),
    ("Supply chain / API", r"\b(API|active pharmaceutical|raw material|ringgit|supply chain|shortage|heparin|insulin|vaccine)\b"),
]
