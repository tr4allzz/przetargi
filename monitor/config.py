"""Search terms and scoring weights. Edit this file to tune relevance.

All matching is case-insensitive substring/regex matching on title + description + buyer.
"""

# Terms used to build server-side queries (TED full-text search etc.).
# Keep them specific: broad terms like "validation" alone return thousands of notices.
QUERY_TERMS = [
    "computer system validation",
    "computerised system validation",
    "computerized system validation",
    "GAMP",
    "Annex 11",
    "21 CFR Part 11",
    "GxP",
    "walidacja systemu",
    "walidacji systemu",
    "walidacja GMP",
    "Aneks 11",
    "Computersystemvalidierung",
    "computergestützter Systeme",
    "Validierung GMP",
    "validation GMP",
    "paperless validation",
    "validation management system",
    "pharmaceutical quality system",
    "eQMS",
    "LIMS validation",
    "IQ OQ PQ",
]

# CPV prefixes worth a bonus (prefix match on the 8-digit code).
CPV_BONUS = {
    "72225": 3.0,   # System quality assurance assessment and review services
    "72": 0.5,      # IT services
    "48": 0.5,      # Software packages
    "73": 0.5,      # R&D services
}

# (weight, label, regex). Each label counts once per tender.
STRONG = 4.0
VALIDATION = 2.0
GXP = 2.5
DOMAIN = 1.0

TERMS: list[tuple[float, str, str]] = [
    # strong, unambiguous CSV terms
    (STRONG, "computer system validation", r"computeri[sz]ed system[s]? validation|computer system[s]? validation"),
    (STRONG, "GAMP", r"\bgamp\s?5?\b"),
    (STRONG, "Annex 11", r"annex\s?11|aneks(u)?\s?11|anhang\s?11"),
    (STRONG, "Part 11", r"21\s?cfr\s?(part\s?)?11"),
    (STRONG, "walidacja systemu", r"walidacj\w*\s+(\w+\s+){0,2}system\w*|system\w*\s+(\w+\s+){0,3}walidacj\w*"),
    (STRONG, "Computersystemvalidierung", r"computersystemvalidierung|validierung\s+computergest|computergest\w+\s+system\w*\s+validier"),
    (STRONG, "CSV/CSA", r"\bcsv\b(?=.{0,60}(valid|walid|gmp|gxp))|\bcsa\b(?=.{0,60}(valid|software assurance))"),
    (STRONG, "systèmes informatisés", r"validation des systèmes informatisés|systèmes? informatisés?"),
    (STRONG, "paperless validation", r"paperless validation|validation (lifecycle )?management (system|software)|digital validation"),
    # validation / qualification
    (VALIDATION, "validation", r"\bvalidat\w*|walidac\w*|validier\w*"),
    (VALIDATION, "IQ/OQ/PQ", r"\biq\s?/\s?oq|\bi\.?q\.?,?\s+o\.?q\.?|kwalifikacj\w* (instalacyjn|operacyjn|procesow)|installation qualification|operational qualification|qualifizierung|qualification d.installation|qualification opérationnelle|\bqi\s?/\s?qo"),
    (VALIDATION, "data integrity", r"data integrity|integralno\w* danych|datenintegrit|alcoa"),
    # GxP context
    (GXP, "GMP/GxP", r"\bbpf\b|bonnes pratiques de fabrication|\bgmp\b|\bgxp\b|\bgdp\b(?=.{0,40}(distribution|dystrybuc))|good manufacturing practice|dobrej praktyki wytwarzania|dobra praktyka wytwarzania|gute herstellungspraxis"),
    (GXP, "PQS/QMS", r"pharmaceutical quality system|\bpqs\b|\beqms\b|quality management system"),
    # domain context
    (DOMAIN, "pharma", r"pharma\w*|farmac\w*|apothek\w*|apteka|aptek\w*|pharmacie|pharmaceutique"),
    (DOMAIN, "radiopharmacy", r"radiofarm\w*|radiopharm\w*|cyklotron|cyclotron"),
    (DOMAIN, "blood/biobank", r"établissement français du sang|krwiodaw\w*|krwiolecz\w*|blood (service|transfusion|bank)|blutspend\w*|biobank\w*|rckik"),
    (DOMAIN, "aseptic/cleanroom", r"aseptic|aseptycz\w*|cleanroom|clean room|reinraum|pomieszcze\w* czyst\w*"),
    (DOMAIN, "LIMS/MES/CDS", r"\blims\b|\bmes\b|\bscada\b|chromatograph\w*|\bcds\b|\bbms\b|\bems\b"),
    (DOMAIN, "monitoring", r"monitoring\w* (temperatur|warunk|środowisk)|temperature monitoring|environmental monitoring|monitorowani\w* temperatur"),
]

# A tender needs at least one of these groups to be considered relevant at all.
REQUIRE_ANY_LABEL = {
    "computer system validation", "systèmes informatisés", "GAMP", "Annex 11", "Part 11", "walidacja systemu",
    "Computersystemvalidierung", "CSV/CSA", "paperless validation",
    "validation", "IQ/OQ/PQ", "data integrity",
}
# Strong terms that are unambiguous on their own. "Annex 11" (any contract annex) and
# "walidacja systemu" (any IT acceptance test) still need GxP/domain context.
SELF_SUFFICIENT_LABELS = {
    "computer system validation", "GAMP", "Part 11", "Computersystemvalidierung",
    "CSV/CSA", "paperless validation",
}
# "systèmes informatisés" alone is any French IT system -> needs GxP context, so not self-sufficient
# ... and at least one GxP/domain hit, unless a self-sufficient term matched.
CONTEXT_LABELS = {"GMP/GxP", "PQS/QMS", "pharma", "radiopharmacy", "blood/biobank",
                  "aseptic/cleanroom", "LIMS/MES/CDS", "monitoring"}

# Terms that indicate a false positive (ML model validation, exams, etc.). Each subtracts.
NEGATIVE: list[tuple[float, str, str]] = [
    (3.0, "ML/finance", r"machine learning|uczeni\w* maszynow|strategi\w* inwestycyjn|trading"),
    (3.0, "exams/education", r"egzamin\w*|kwalifikacj\w* zawodow|szkoleni\w* zawodow"),
    (2.0, "data validation (NHS PAS)", r"patient administration system|\bpas\b.*migrat"),
    (1.5, "analytical method validation", r"walidacj\w* metod\w*|metod\w* analityczn\w*|method validation|bioanalityczn\w*"),
    (5.0, "physio GAMP course", r"mięśniowo|powięziow|fizjoterap|zoga face"),
]

DEFAULT_MIN_SCORE = 3.0


# --- Tender type classification (see scoring.classify) ------------------------------------
KIND_SERVICE = "usługa CSV"
KIND_SYSTEM = "system + walidacja"
KIND_EQUIPMENT = "sprzęt + IQ/OQ"
KIND_DEVICE_SERVICE = "serwis urządzeń"
KIND_OTHER = "inne"
# kinds that are a real fit for CSV work; pricing insights are computed only on these
CSV_KINDS = {KIND_SERVICE, KIND_SYSTEM}
KIND_SCORE_ADJ = {KIND_SERVICE: 2.0, KIND_SYSTEM: 1.0, KIND_EQUIPMENT: -1.0,
                  KIND_DEVICE_SERVICE: -1.0, KIND_OTHER: -1.5}

RX_DEVICE_SERVICE = (r"maintenance (des|d.)\s?(équipements|appareils|matériels)|przegląd\w* techniczn|serwis\w*|usuwania awarii|konserwacj|"
                     r"maintenance of (equipment|devices)|wartung|instandhaltung")
RX_DELIVERY = (r"\bdostaw\w*|wdroż\w*|zakup\w*|wynaj\w*|leasing|lieferung|beschaffung|anschaffung|"
               r"fourniture\w*|acquisition|ersatzbeschaffung|\bsupply\b|purchase|procurement of|acquisition|delivery|aankoop|levering|закупуване|"
               r"implementation of (a|the)? ?(system|software)|installation of")
RX_SYSTEM = (r"\blims\b|\bmes\b|\bebr\b|electronic batch|\beqms\b|\bqms\b|quality management system|"
             r"system\w* (informatyczn|teleinformatyczn|monitor\w*|zarządzania)|monitoring\w* system|"
             r"oprogramowani\w*|software|softwar\w*|\bscada\b|pharma-monitoring|"
             r"system\w* służąc\w* monitorow|monitorowani\w* (sprzętu|temperatur)|dokumentacj\w* elektroniczn")
RX_EQUIPMENT = (r"aparatur\w*|urządze\w*|sprzęt\w*|equipment|apparatus|instrument\w*|gerät\w*|ausstattung|"
                r"analizator|spektrofotometr|spectrophotometer|chromatograf|elektroporator|izolator|isolator|"
                r"synthesizer|zellprozessierungssystem|wirów\w*|centrifug|zamrażar|lodówk|freezer|"
                r"aqua purificata|water for injection|komor\w*|maszyn\w*|machine\w*")
RX_SERVICE = (r"re-?qualifi\w*|qualifizierung|validierung|requalification|"
              r"prestations?|assistance|accompagnement|\busług\w*|dienstleistung\w*|\bservices?\b|consult\w*|beratung|doradztw\w*|"
              r"begleitung|wsparci\w*|^\s*walidacj|^\s*validation|^\s*validierung")
RX_OTHER = (r"assurances?\b|insurance|versicherung\w*|neubau|ersatzneubau|bauleistung\w*|bauabschnitt|"
            r"construction d|travaux|logements|architekt\w*|architect\w*|bauleitung|gesamtleitung|generalplaner|planerleistung|"
            r"badawcz\w*|research|forschung|odczynnik\w*|reagent\w*|pożywk\w*|hodowl\w*|"
            r"pranie|wäsche|reinraumbekleidung|bekleidung|mopps|próbek|samples|antibody|przeciwciał")
EQUIPMENT_CPV_PREFIXES = ("38", "33", "42", "39", "31", "44", "45")
