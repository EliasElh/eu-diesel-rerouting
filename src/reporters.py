"""
Reference table of reporting countries (EU-27 + UK + Norway + Switzerland).
Codes are Comtrade statistical reporter codes, taken from the official reference file: https://comtradeapi.un.org/files/v1/app/reference/Reporters.json
Note: these sometimes differ from pure UN M49 (e.g. France=251 includes Monaco, Switzerland=757 includes Liechtenstein).
"""

REPORTERS = {
    40:  "AUT",  # Austria
    56:  "BEL",  # Belgium
    100: "BGR",  # Bulgaria
    191: "HRV",  # Croatia
    196: "CYP",  # Cyprus
    203: "CZE",  # Czechia
    208: "DNK",  # Denmark
    233: "EST",  # Estonia
    246: "FIN",  # Finland
    251: "FRA",  # France (including Monaco)
    276: "DEU",  # Germany
    300: "GRC",  # Greece
    348: "HUN",  # Hungary
    372: "IRL",  # Ireland
    380: "ITA",  # Italy
    428: "LVA",  # Latvia
    440: "LTU",  # Lithuania
    442: "LUX",  # Luxembourg
    470: "MLT",  # Malta
    528: "NLD",  # Netherlands
    616: "POL",  # Poland
    620: "PRT",  # Portugal
    642: "ROU",  # Romania
    703: "SVK",  # Slovakia
    705: "SVN",  # Slovenia
    724: "ESP",  # Spain
    752: "SWE",  # Sweden
    757: "CHE",  # Switzerland (including Liechtenstein)
    579: "NOR",  # Norway (including Svalbard and Jan Mayen)
    826: "GBR",  # United Kingdom
}