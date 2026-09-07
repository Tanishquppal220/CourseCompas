"""
Loads the full curriculum (Terms 1-8, all term-specific baskets, and the
shared Open Minor basket) into Postgres using the models in models.py.

Usage:
    export DATABASE_URL="postgresql+psycopg2://curriculum_user:curriculum_pass@localhost:5432/curriculum_db"
    python models.py       # creates tables
    python seed_data.py    # loads data

Safe to re-run: every insert goes through a get_or_create lookup keyed on
the natural unique key (course code, term number+variant, basket name+term,
term_id+s_no, etc.), so running this twice does not create duplicates.

Notes on data-quality quirks preserved from the source document (flagged so
you can decide whether to reconcile them):
  - MEC136 is titled "ENGINEERING GRAPHICS AND CAD" in Term 1's basket but
    "ENGINEERING DRAWING WITH AUTOCAD" in Term 2's basket, same code/L-T-P.
    The first occurrence (Term 1's title) is kept as canonical.
  - ECE341 "PROGRAMMING IOT" is listed as 1-0-3 (3.0 credits) in Term 4's
    Engineering Minor Elective 2 basket, but as 2-0-2 in the Open Minor
    basket (row 128). The first occurrence (Term 4) is kept as canonical.
"""

import sys
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.database import SessionLocal, engine
from app.models import (
    Base,
    BasketOption,
    Course,
    CourseNature,
    CourseType,
    ElectiveArea,
    ElectiveBasket,
    Term,
    TermSlot,
)

# ---------------------------------------------------------------------------
# Lookup data
# ---------------------------------------------------------------------------

COURSE_TYPES = {
    "APE": "Aptitude Elective",
    "CE": "Core Elective",
    "CR": "Core Course",
    "CR1": "CORE-I",
    "CR3": "Core-III (Community Development)",
    "DE": "Departmental Elective",
    "EM": "Engineering Minor",
    "LE": "Language Elective",
    "OM": "Open/Minor",
    "PW": "Pathway Elective",
    "TE": "Training Elective",
}

COURSE_NATURES = {
    "BSC": "Basic Science",
    "DSC": "Discipline Core",
    "EEA": "Employability Enhancement Activities",
    "ESC": "Engineering Science",
    "LCS": "Language & Communication Skills",
    "OEM": "Open Minor/Open Elective",
    "PRC": "Community Development Project",
    "PRJ": "Project (including Capstone Project and Research Project)",
    "PWE": "Pathway Elective",
    "SMN": "Seminar",
    "TCF": "Training Compulsory - Full term",
    "TCS": "Training Compulsory - Summer",
}

# code -> (title, L, T, P, credit, contact_hours)
COURSES = {
    # ---- Term 1 ----
    "CSE111": ("ORIENTATION TO COMPUTING-I", 2, 0, 0, 2.0, 2.0),
    "CSE326": ("INTERNET PROGRAMMING LABORATORY", 0, 0, 3, 2.0, 3.0),
    "INT108": ("PYTHON PROGRAMMING", 3, 0, 2, 4.0, 5.0),
    "MTH174": ("ENGINEERING MATHEMATICS", 3, 1, 0, 4.0, 4.0),
    "PES318": ("SOFT SKILLS-I", 1, 2, 0, 3.0, 3.0),
    "ECE249": ("BASIC ELECTRICAL AND ELECTRONICS ENGINEERING", 3, 1, 0, 4.0, 4.0),
    "MEC136": ("ENGINEERING GRAPHICS AND CAD", 2, 2, 0, 4.0, 4.0),
    "CHE110": ("ENVIRONMENTAL STUDIES", 2, 0, 0, 2.0, 2.0),
    "PHY110": ("ENGINEERING PHYSICS", 3, 0, 0, 3.0, 3.0),
    "ECE279": (
        "BASIC ELECTRICAL AND ELECTRONICS ENGINEERING LABORATORY",
        0,
        0,
        2,
        1.0,
        2.0,
    ),
    # ---- Term 2 ----
    "CSE101": ("COMPUTER PROGRAMMING", 3, 0, 2, 4.0, 5.0),
    "CSE121": ("ORIENTATION TO COMPUTING-II", 2, 0, 0, 2.0, 2.0),
    "CSE320": ("SOFTWARE ENGINEERING", 3, 0, 0, 3.0, 3.0),
    "INT306": ("DATABASE MANAGEMENT SYSTEMS", 3, 0, 2, 4.0, 5.0),
    "MTH401": ("DISCRETE MATHEMATICS", 3, 1, 0, 4.0, 4.0),
    "PEL121": ("COMMUNICATION SKILLS-I", 1, 0, 3, 3.0, 4.0),
    "PEL125": ("UPPER INTERMEDIATE COMMUNICATION SKILLS-I", 1, 0, 3, 3.0, 4.0),
    "PEL130": ("ADVANCED COMMUNICATION SKILLS-I", 1, 0, 3, 3.0, 4.0),
    # ---- Term 3 ----
    "CSE202": ("OBJECT ORIENTED PROGRAMMING", 3, 0, 2, 4.0, 5.0),
    "CSE205": ("DATA STRUCTURES AND ALGORITHMS", 3, 0, 2, 4.0, 5.0),
    "CSE306": ("COMPUTER NETWORKS", 3, 0, 0, 3.0, 3.0),
    "CSE307": ("INTERNETWORKING ESSENTIALS", 0, 0, 2, 1.0, 2.0),
    "GEN231": ("COMMUNITY DEVELOPMENT PROJECT", 0, 0, 4, 2.0, 4.0),
    "CSE316": ("OPERATING SYSTEMS", 3, 0, 0, 3.0, 3.0),
    "MTH302": ("PROBABILITY AND STATISTICS", 3, 1, 0, 4.0, 4.0),
    "CSE325": ("OPERATING SYSTEMS LABORATORY", 0, 0, 2, 1.0, 2.0),
    "PEL132": ("COMMUNICATION SKILLS-II", 1, 0, 3, 3.0, 4.0),
    "PEL134": ("UPPER INTERMEDIATE COMMUNICATION SKILLS-II", 1, 0, 3, 3.0, 4.0),
    "PEL136": ("ADVANCED COMMUNICATION SKILLS-II", 1, 0, 3, 3.0, 4.0),
    # ---- Term 4 ----
    "PEA305": ("ANALYTICAL SKILLS-I", 2, 1, 0, 3.0, 3.0),
    "PEA307": ("ADVANCED ANALYTICAL SKILLS-I", 2, 1, 0, 3.0, 3.0),
    "INT330": ("MANAGING CLOUD SOLUTIONS", 2, 0, 2, 3.0, 4.0),
    "INT242": ("CYBER SECURITY ESSENTIALS", 2, 0, 2, 3.0, 4.0),
    "INT387": ("DATA ANALYSIS AND VISUALIZATION", 2, 0, 2, 3.0, 4.0),
    "INT219": ("FRONT END WEB DEVELOPER", 2, 0, 2, 3.0, 4.0),
    "ECE217": ("INTRODUCTION TO INTERNET OF THINGS (IOT)", 3, 0, 0, 3.0, 3.0),
    "CSE273": ("FOUNDATIONS OF MACHINE LEARNING", 2, 0, 2, 3.0, 4.0),
    "CSE271": ("SOFTWARE TESTING", 3, 0, 0, 3.0, 3.0),
    "INT362": ("CLOUD ARCHITECTURE AND IMPLEMENTATION-I", 2, 0, 2, 3.0, 4.0),
    "INT249": ("SYSTEM ADMINISTRATION", 2, 0, 2, 3.0, 4.0),
    "INT375": ("DATA SCIENCE TOOLBOX: PYTHON PROGRAMMING", 2, 0, 2, 3.0, 4.0),
    "INT222": ("ADVANCED WEB DEVELOPMENT", 2, 0, 2, 3.0, 4.0),
    "ECE341": ("PROGRAMMING IOT", 1, 0, 3, 3.0, 4.0),
    "CSE274": ("APPLIED MACHINE LEARNING", 2, 0, 2, 3.0, 4.0),
    "CSE272": ("SOFTWARE QUALITY ENGINEERING", 3, 0, 0, 3.0, 3.0),
    "CSE211": ("COMPUTER ORGANIZATION AND DESIGN", 3, 1, 0, 4.0, 4.0),
    "CSE310": ("PROGRAMMING IN JAVA", 3, 0, 2, 4.0, 5.0),
    "INT428": ("ARTIFICIAL INTELLIGENCE ESSENTIALS", 3, 0, 1, 4.0, 4.0),
    # ---- Term 5 ----
    "INT363": ("CLOUD MICROSERVICES", 2, 0, 2, 3.0, 4.0),
    "INT250": ("DIGITAL EVIDENCE ANALYSIS", 2, 0, 2, 3.0, 4.0),
    "INT312": ("BIG DATA FUNDAMENTALS", 2, 0, 2, 3.0, 4.0),
    "INT252": ("WEB APP DEVELOPMENT WITH REACTJS", 2, 0, 2, 3.0, 4.0),
    "ECE128": ("INTRODUCTION TO IOT NETWORKING PROTOCOLS", 3, 0, 0, 3.0, 3.0),
    "CSE471": ("DEEP LEARNING FOR COMPUTER VISION", 2, 0, 2, 3.0, 4.0),
    "CSE376": ("AUTOMATED TESTING", 2, 0, 2, 3.0, 4.0),
    "INT364": ("CLOUD ARCHITECTURE AND IMPLEMENTATION-II", 2, 0, 2, 3.0, 4.0),
    "INT244": ("SECURING COMPUTING SYSTEMS", 2, 0, 2, 3.0, 4.0),
    "INT234": ("PREDICTIVE ANALYTICS", 2, 0, 2, 3.0, 4.0),
    "INT257": ("MODERN WEB APPLICATION DEVELOPMENT", 2, 0, 2, 3.0, 4.0),
    "ECE237": ("ARCHITECTING SMART IOT DEVICES", 2, 0, 2, 3.0, 4.0),
    "CSE472": ("DEEP LEARNING FOR NATURAL LANGUAGE PROCESSING", 2, 0, 2, 3.0, 4.0),
    "CSE377": ("WEB AUTOMATION TESTING", 2, 0, 2, 3.0, 4.0),
    "PEA306": ("ANALYTICAL SKILLS-II", 2, 1, 0, 3.0, 3.0),
    "PEA308": ("ADVANCED ANALYTICAL SKILLS-II", 2, 1, 0, 3.0, 3.0),
    "CSE329": ("PRELUDE TO COMPETITIVE CODING", 2, 0, 1, 3.0, 3.0),
    "CSE333": ("COMBINATORIAL STUDIES-I", 2, 0, 2, 3.0, 4.0),
    "CSE330": ("COMPETITIVE CODING APPROACHES-TECHNIQUES", 2, 0, 1, 3.0, 3.0),
    "PES390": ("SOFT SKILLS", 2, 2, 0, 4.0, 4.0),
    "CSE343": ("TRAINING IN PROGRAMMING", 0, 0, 6, 3.0, 6.0),
    "CSE443": ("SEMINAR ON SUMMER TRAINING", 0, 0, 6, 3.0, 6.0),
    "CSE408": ("DESIGN AND ANALYSIS OF ALGORITHMS", 3, 0, 2, 4.0, 5.0),
    # ---- Term 6 ----
    "INT327": ("CLOUD INFRASTRUCTURE AND RESOURCE MANAGEMENT", 2, 0, 2, 3.0, 4.0),
    "INT245": ("PENETRATION TESTING", 2, 0, 2, 3.0, 4.0),
    "INT315": ("CLUSTER COMPUTING", 2, 0, 2, 3.0, 4.0),
    "INT258": ("ADVANCED DATABASES, SECURITY AND TESTING", 2, 0, 2, 3.0, 4.0),
    "ECE129": ("IOT FOR DIGITAL SOCIETY", 3, 0, 0, 3.0, 3.0),
    "CSE473": ("LARGE LANGUAGE MODELS AND AGENTIC AI", 2, 0, 2, 3.0, 4.0),
    "CSE378": ("WEB SERVICES API AUTOMATION TESTING", 2, 0, 2, 3.0, 4.0),
    "CSE334": ("COMBINATORIAL STUDIES-II", 2, 0, 2, 3.0, 4.0),
    "CSE331": ("CODING PEARLS", 2, 0, 1, 3.0, 3.0),
    "CSE357": ("COMBINATORIAL STUDIES", 2, 0, 2, 3.0, 4.0),
    "PES391": ("COMMUNICATION SKILLS FOR PROFESSIONAL EXCELLENCE", 1, 1, 0, 2.0, 2.0),
    "CSE322": ("FORMAL LANGUAGES AND AUTOMATION THEORY", 3, 0, 0, 3.0, 3.0),
    "CSE332": ("INDUSTRY ETHICS AND LEGAL ISSUES", 2, 0, 0, 2.0, 2.0),
    "CSE393": ("ONLINE ACADEMIC COURSE", 3, 0, 0, 3.0, 3.0),
    # ---- Term 7 (course work) ----
    "CSE304": ("COMPUTER GRAPHICS AND VISUALIZATION", 3, 1, 0, 4.0, 4.0),
    "CSE327": ("SIMULATION AND MODELLING", 3, 0, 0, 3.0, 3.0),
    "CSE406": ("ADVANCED JAVA PROGRAMMING", 3, 0, 2, 4.0, 5.0),
    "CSE434": ("GAME DEVELOPMENT IN 3D", 3, 0, 2, 4.0, 5.0),
    "CSE436": ("BLOCKCHAIN", 3, 0, 2, 4.0, 5.0),
    "INT402": ("MODERN WEB PROGRAMMING TOOLS AND TECHNIQUES", 3, 0, 2, 4.0, 5.0),
    "CSE328": ("SIMULATION AND MODELLING LABORATORY", 0, 0, 2, 1.0, 2.0),
    "INT328": ("NETWORK VIRTUALIZATION AND CLOUD SECURITY", 2, 0, 2, 3.0, 4.0),
    "INT251": ("MALWARE ANALYSIS AND CYBER DEFENCE", 2, 0, 2, 3.0, 4.0),
    "INT388": ("MLOPS:WORKFLOW AUTOMATION AND DEPLOYMENT", 2, 0, 2, 3.0, 4.0),
    "INT340": ("DEVOPS AND SYSTEM DESIGN", 2, 0, 2, 3.0, 4.0),
    "ECE140": ("WORKSHOP ON IOT FOR DIGITAL SOCIETY", 1, 0, 3, 3.0, 4.0),
    "CSE470": ("APPLIED ARTIFICIAL INTELLIGENCE SYSTEMS", 2, 0, 2, 3.0, 4.0),
    "CSE379": ("MOBILE AUTOMATED TESTING", 0, 0, 4, 3.0, 4.0),
    "CSE335": ("COMBINATORIAL STUDIES-III", 2, 0, 2, 3.0, 4.0),
    "CSE339": ("CAPSTONE PROJECT-I", 0, 0, 4, 2.0, 4.0),
    # ---- Term 7 (industrial internship) ----
    "CSE447": ("INDUSTRY CO-OP PROJECT-I", 0, 0, 32, 16.0, 32.0),
    # ---- Term 8 (course work) ----
    "CSE403": ("NETWORK SECURITY AND CRYPTOGRAPHY", 3, 0, 2, 4.0, 5.0),
    "CSE493": ("LINUX SYSTEM ADMINISTRATION", 3, 0, 2, 4.0, 5.0),
    "CSE504": ("STORAGE TECHNOLOGY FOUNDATION", 3, 0, 0, 3.0, 3.0),
    "INT411": ("SOFTWARE PROJECT MANAGEMENT", 3, 0, 0, 3.0, 3.0),
    "CSE507": ("STORAGE TECHNOLOGY FOUNDATION LABORATORY", 0, 0, 2, 1.0, 2.0),
    "INT416": ("SOFTWARE PROJECT MANAGEMENT LABORATORY", 0, 0, 3, 2.0, 3.0),
    "CSE435": ("COMPREHENSIVE SEMINAR", 0, 0, 2, 1.0, 2.0),
    "CSE439": ("CAPSTONE PROJECT-II", 0, 0, 16, 8.0, 16.0),
    # ---- Term 8 (industrial internship) ----
    "CSE441": ("INDUSTRY INTERNSHIP PROJECT", 0, 0, 32, 16.0, 32.0),
    "CSE448": ("INDUSTRY CO-OP PROJECT-II", 0, 0, 32, 16.0, 32.0),
    # ---- Open Minor basket - courses not already listed above ----
    "CSE224": ("FUNDAMENTALS OF ANDROID", 2, 0, 2, 3.0, 4.0),
    "CSE225": ("DEVELOPING ANDROID APPS", 2, 0, 2, 3.0, 4.0),
    "CSE226": ("ANDROID APP DEPLOYMENT", 2, 0, 2, 3.0, 4.0),
    "CSE227": ("ADVANCED ANDROID APP DEVELOPMENT", 2, 0, 2, 3.0, 4.0),
    "FIN314": ("CAPITAL MARKET OPERATIONS", 3, 0, 0, 3.0, 3.0),
    "FIN318": ("MONEY, BANKING AND FINANCIAL SERVICES", 3, 0, 0, 3.0, 3.0),
    "FIN319": ("INVESTMENT BANKING AND FINANCIAL SERVICES", 3, 0, 0, 3.0, 3.0),
    "FIN901": ("FUNDAMENTALS OF BANKING AND INSURANCE", 3, 0, 0, 3.0, 3.0),
    "LAW252": ("BASICS OF CONTRACT", 3, 0, 0, 3.0, 3.0),
    "LAW255": ("SPECIAL CONTRACTS", 3, 0, 0, 3.0, 3.0),
    "LAW256": ("BASICS OF COMPANY LAW", 3, 0, 0, 3.0, 3.0),
    "LAW257": ("BASICS OF INVESTMENT LAW", 3, 0, 0, 3.0, 3.0),
    "SSC231": ("INDIAN CULTURE AND HISTORY", 4, 0, 0, 4.0, 4.0),
    "SSC232": ("INDIAN GEOGRAPHY AND SOCIETY", 4, 0, 0, 4.0, 4.0),
    "SSC233": (
        "INDIAN POLITY, GOVERNANCE AND INTERNATIONAL RELATIONS",
        4,
        0,
        0,
        4.0,
        4.0,
    ),
    "SSC234": ("INDIAN ECONOMY", 4, 0, 0, 4.0, 4.0),
    "INT373": ("AGILE DRIVEN DEVELOPMENT AND PROJECT MANAGEMENT", 2, 0, 2, 3.0, 4.0),
    "INT377": ("CLOUD COMPUTING AND DEVOPS ESSENTIALS", 2, 0, 2, 3.0, 4.0),
    "INT378": ("ADVANCEMENTS IN CLOUD AND DEVOPS", 2, 0, 2, 3.0, 4.0),
    "INT379": ("SITE RELIABILITY ENGINEERING", 2, 0, 2, 3.0, 4.0),
    "INT331": ("FUNDAMENTALS OF DEVOPS", 2, 0, 2, 3.0, 4.0),
    "INT332": ("DEVOPS VIRTUALIZATION AND CONFIGURATION MANAGEMENT", 2, 0, 2, 3.0, 4.0),
    "INT333": ("DEVOPS ADVANCE CONFIGURATION MANAGEMENT", 2, 0, 2, 3.0, 4.0),
    "INT334": ("ENTERPRISE APPLICATION AUTOMATION", 2, 0, 2, 3.0, 4.0),
    "MKT311": ("DIGITAL MARKETING", 0, 0, 3, 2.0, 3.0),
    "MKT905": ("SEARCH ENGINE OPTIMIZATION", 3, 0, 0, 3.0, 3.0),
    "MKT906": ("SOCIAL MEDIA MARKETING", 0, 0, 3, 2.0, 3.0),
    "MKT907": ("WEB ANALYTICS", 0, 0, 3, 2.0, 3.0),
    "ECO214": ("INTRODUCTION TO ECONOMIC ANALYSIS", 3, 0, 0, 3.0, 3.0),
    "ECO215": ("INDIAN ECONOMIC ISSUES AND POLICIES", 3, 0, 0, 3.0, 3.0),
    "ECO324": ("ECONOMICS OF MONEY AND BANKING", 3, 0, 0, 3.0, 3.0),
    "ECO325": ("ECONOMICS OF TRADE", 3, 0, 0, 3.0, 3.0),
    "ENG606": ("CONTEMPORARY SHORT STORIES", 3, 0, 0, 3.0, 3.0),
    "ENG607": ("CONTEMPORARY PROSE AND POETRY", 3, 0, 0, 3.0, 3.0),
    "ENG608": ("CONTEMPORARY DRAMA", 3, 0, 0, 3.0, 3.0),
    "ENG609": ("CONTEMPORARY FICTION", 3, 0, 0, 3.0, 3.0),
    "FST801": ("FASHION STUDIES", 3, 0, 0, 3.0, 3.0),
    "FST802": ("INDIAN CULTURE STUDIES", 3, 0, 0, 3.0, 3.0),
    "FST803": ("FASHION DESIGN PROCESS", 0, 0, 5, 3.0, 5.0),
    "FST804": ("SURFACE DEVELOPMENT", 0, 0, 5, 3.0, 5.0),
    "FIN212": ("BASIC FINANCIAL MANAGEMENT", 3, 0, 0, 3.0, 3.0),
    "FIN213": ("INDIAN FINANCIAL SYSTEM", 3, 0, 0, 3.0, 3.0),
    "FIN308": ("BANKING AND INSURANCE", 3, 0, 0, 3.0, 3.0),
    "FIN214": ("INTRODUCTION TO FINANCIAL MARKETS", 3, 0, 0, 3.0, 3.0),
    "FIN215": ("MUTUAL FUNDS AND EXCHANGE TRADED FUNDS", 3, 0, 0, 3.0, 3.0),
    "FIN358": ("DERIVATIVE MARKET OPERATIONS", 3, 0, 0, 3.0, 3.0),
    "FRN114": ("FOUNDATION FRENCH I", 3, 0, 0, 3.0, 3.0),
    "FRN115": ("FOUNDATION FRENCH II", 3, 0, 0, 3.0, 3.0),
    "FRN116": ("FRENCH LANGUAGE I", 3, 0, 0, 3.0, 3.0),
    "FRN117": ("ELEMENTARY FRENCH IV", 3, 0, 0, 3.0, 3.0),
    "CAP818": ("GAME TOOL-I", 0, 0, 5, 3.0, 5.0),
    "CAP819": ("GAME TOOL-II", 0, 0, 5, 3.0, 5.0),
    "CAP820": ("GAME TOOL-III", 0, 0, 5, 3.0, 5.0),
    "CAP821": ("PROJECT", 0, 0, 5, 3.0, 5.0),
    "GEO295": ("PHYSICAL GEOGRAPHY", 3, 0, 0, 3.0, 3.0),
    "GEO296": ("HUMAN GEOGRAPHY", 3, 0, 0, 3.0, 3.0),
    "GEO297": ("GEOGRAPHY OF INDIA-I", 3, 0, 0, 3.0, 3.0),
    "GEO298": ("GEOGRAPHY OF INDIA-II", 3, 0, 0, 3.0, 3.0),
    "GER107": ("FOUNDATION GERMAN I", 3, 0, 0, 3.0, 3.0),
    "GER108": ("FOUNDATION GERMAN II", 3, 0, 0, 3.0, 3.0),
    "GER109": ("GERMAN LANGUAGE I", 3, 0, 0, 3.0, 3.0),
    "GER110": ("GERMAN LANGUAGE II", 3, 0, 0, 3.0, 3.0),
    "POL371": ("POLITICAL CRISIS MANAGEMENT AND COMMUNICATION", 3, 0, 0, 3.0, 3.0),
    "POL372": ("THE GLOBAL DIPLOMACY", 3, 0, 0, 3.0, 3.0),
    "POL373": ("ETHNIC STUDIES", 3, 0, 0, 3.0, 3.0),
    "POL374": ("MORAL FOUNDATIONS OF POLITICS", 3, 0, 0, 3.0, 3.0),
    "HRM203": ("HUMAN RESOURCE PLANNING AND DEVELOPMENT", 3, 0, 0, 3.0, 3.0),
    "HRM204": ("COMPENSATION MANAGEMENT", 3, 0, 0, 3.0, 3.0),
    "HRM301": ("INDUSTRIAL PSYCHOLOGY", 3, 0, 0, 3.0, 3.0),
    "HRM302": ("CONFLICT MANAGEMENT AND NEGOTIATION", 3, 0, 0, 3.0, 3.0),
    "CSE291": ("GAME DESIGN AND DEVELOPMENT USING UNITY 3D", 2, 0, 2, 3.0, 4.0),
    "CSE292": ("C# PROGRAMMING IN UNITY 3D", 2, 0, 2, 3.0, 4.0),
    "CSE293": ("XR DEVELOPMENT (AR/VR/MR SYSTEMS)", 2, 0, 2, 3.0, 4.0),
    "CSE294": ("ADVANCED AR DEVELOPMENT", 2, 0, 2, 3.0, 4.0),
    "HIS291": ("ANCIENT INDIAN HISTORY AND CULTURE", 3, 0, 0, 3.0, 3.0),
    "HIS292": ("MEDIEVAL INDIAN HISTORY AND CULTURE", 3, 0, 0, 3.0, 3.0),
    "HIS293": ("HISTORY OF THE BRITISH RAAJ IN INDIA", 3, 0, 0, 3.0, 3.0),
    "HIS294": ("MODERN WORLD HISTORY", 3, 0, 0, 3.0, 3.0),
    "INT323": ("DATABASE ESSENTIALS TOWARDS INFORMATICA", 2, 0, 2, 3.0, 4.0),
    "INT324": ("INFORMATICA DATA QUALITY MANAGEMENT", 2, 0, 2, 3.0, 4.0),
    "INT325": ("INFORMATICA DATA INTEGRATION", 2, 0, 2, 3.0, 4.0),
    "INT326": ("CLOUD APPLICATION INTEGRATION PROCESSES", 2, 0, 2, 3.0, 4.0),
    "LAW351": ("COPYRIGHTS AND DESIGNS LAW", 3, 0, 0, 3.0, 3.0),
    "LAW352": ("TRADEMARKS AND ALLIED LAWS", 3, 0, 0, 3.0, 3.0),
    "LAW353": ("PATENTS AND GEOGRAPHICAL INDICATIONS", 3, 0, 0, 3.0, 3.0),
    "LAW354": ("CYBER LAWS", 3, 0, 0, 3.0, 3.0),
    "FIN348": ("INTERNATIONAL FINANCIAL MANAGEMENT", 3, 0, 0, 3.0, 3.0),
    "MGN220": ("INTRODUCTION TO INTERNATIONAL BUSINESS", 3, 0, 0, 3.0, 3.0),
    "MGN902": ("EXPORT IMPORT PROCEDURE AND DOCUMENTATION", 3, 0, 0, 3.0, 3.0),
    "MKT211": ("INTERNATIONAL MARKETING", 3, 0, 0, 3.0, 3.0),
    "JAP105": ("FOUNDATION JAPANESE I", 3, 0, 0, 3.0, 3.0),
    "JAP106": ("BASIC JAPANESE-II", 3, 0, 0, 3.0, 3.0),
    "JAP107": ("ELEMENTARY JAPANESE III", 3, 0, 0, 3.0, 3.0),
    "JAP108": ("ELEMENTARY JAPANESE IV", 3, 0, 0, 3.0, 3.0),
    "ACC211": ("FINANCIAL ACCOUNTING", 3, 0, 0, 3.0, 3.0),
    "MKT202": ("MARKETING MANAGEMENT", 3, 0, 0, 3.0, 3.0),
    "MKT257": ("PERSONAL SELLING SKILLS", 0, 0, 3, 2.0, 3.0),
    "MKT258": ("SALES MANAGEMENT", 3, 0, 0, 3.0, 3.0),
    "PID801": ("FUNDAMENTALS OF DESIGN", 3, 0, 0, 3.0, 3.0),
    "PID802": ("PRODUCT DESIGN STUDIO-I", 0, 0, 5, 3.0, 5.0),
    "PID803": ("PRODUCT DESIGN STUDIO-II", 0, 0, 5, 3.0, 5.0),
    "PID804": ("PACKAGING DESIGN", 0, 0, 5, 3.0, 5.0),
    "PSY281": ("FOUNDATIONS OF PSYCHOLOGY-I", 3, 0, 0, 3.0, 3.0),
    "PSY282": ("FOUNDATIONS OF PSYCHOLOGY - II", 3, 0, 0, 3.0, 3.0),
    "PSY283": ("ISSUES AND APPLICATIONS OF PSYCHOLOGY-I", 3, 0, 0, 3.0, 3.0),
    "PSY284": ("ISSUES AND APPLICATIONS OF PSYCHOLOGY-II", 3, 0, 0, 3.0, 3.0),
    "PSY260": ("CONSUMER PSYCHOLOGY", 3, 0, 0, 3.0, 3.0),
    "PSY261": ("SOCIAL PSYCHOLOGY IN TECHNOLOGY", 3, 0, 0, 3.0, 3.0),
    "PSY262": ("EMOTIONAL INTELLIGENCE", 3, 0, 0, 3.0, 3.0),
    "PSY263": ("PSYCHOLOGY OF WELL-BEING", 3, 0, 0, 3.0, 3.0),
    "PBA396": ("INTRODUCTION TO PUBLIC ADMINISTRATION", 3, 0, 0, 3.0, 3.0),
    "PBA397": ("INTRODUCTION TO ADMINISTRATIVE BEHAVIOR", 3, 0, 0, 3.0, 3.0),
    "PBA398": ("COMPARATIVE PUBLIC ADMINISTRATION", 3, 0, 0, 3.0, 3.0),
    "PBA399": ("PUBLIC POLICY AND ANALYSIS", 3, 0, 0, 3.0, 3.0),
    "INT346": ("ROBOTIC PROCESS AUTOMATION", 2, 0, 2, 3.0, 4.0),
    "INT347": ("WORKFLOW AUTOMATION", 2, 0, 2, 3.0, 4.0),
    "INT348": ("BOT AUTOMATION", 2, 0, 2, 3.0, 4.0),
    "INT349": ("AUTOMATION USING PYTHON", 2, 0, 2, 3.0, 4.0),
    "SOC371": ("SOCIOLOGY OF MEDIA", 3, 0, 0, 3.0, 3.0),
    "SOC372": ("SOCIOLOGY OF AGING", 3, 0, 0, 3.0, 3.0),
    "SOC373": ("ENVIRONMENT AND SOCIETY", 3, 0, 0, 3.0, 3.0),
    "SOC374": ("UNDERSTANDING CRIMINOLOGY", 3, 0, 0, 3.0, 3.0),
    "SPA107": ("FOUNDATION SPANISH I", 3, 0, 0, 3.0, 3.0),
    "SPA108": ("ELEMENTARY SPANISH II", 3, 0, 0, 3.0, 3.0),
    "SPA109": ("SPANISH LANGUAGE I", 3, 0, 0, 3.0, 3.0),
    "SPA110": ("ELEMENTARY SPANISH IV", 3, 0, 0, 3.0, 3.0),
    "IFD801": ("FUNDAMENTALS OF DESIGN", 3, 0, 0, 3.0, 3.0),
    "IFD802": ("STUDIES IN FORM", 0, 0, 5, 3.0, 5.0),
    "IFD803": ("COMPUTER SKILLS", 0, 0, 5, 3.0, 5.0),
    "IFD804": ("SET DESIGN STUDIO", 0, 0, 5, 3.0, 5.0),
    "IXD801": ("INTERACTION DESIGN", 0, 0, 5, 3.0, 5.0),
    "IXD802": ("FUNDAMENTALS TOOLS OF USER INTERFACE", 0, 0, 5, 3.0, 5.0),
    "IXD803": ("DESIGN OF USER INTERFACE AND EXPERIENCE", 0, 0, 5, 3.0, 5.0),
    "IXD804": ("HUMAN COMPUTER INTERACTIONS", 0, 0, 5, 3.0, 5.0),
    "HMT141": ("INTRODUCTION TO TRAVEL AND TOURISM INDUSTRY", 3, 0, 0, 3.0, 3.0),
    "HMT712": ("MANAGEMENT FOR TOURISM AND HOSPITALITY", 3, 0, 0, 3.0, 3.0),
    "HMT752": ("ITINERARY PLANNING AND MANAGEMENT", 3, 0, 0, 3.0, 3.0),
    "HMT754": ("TRAVEL DOCUMENTATION", 3, 0, 0, 3.0, 3.0),
}

# ---------------------------------------------------------------------------
# Term-specific baskets: basket_key -> [(course_code, elective_area_or_None), ...]
# ---------------------------------------------------------------------------

BASKETS = {
    "T1_CE1": [("ECE249", None), ("MEC136", None)],
    "T1_CE2": [("CHE110", None), ("PHY110", None)],
    "T1_CE3": [("ECE279", None)],
    "T2_CE1": [("ECE249", None), ("MEC136", None)],
    "T2_CE2": [("CHE110", None), ("PHY110", None)],
    "T2_CE3": [("ECE279", None)],
    "T2_LE1": [("PEL121", None), ("PEL125", None), ("PEL130", None)],
    "T3_CE4": [("CSE316", None), ("MTH302", None)],
    "T3_CE5": [("CSE325", None)],
    "T3_LE2": [("PEL132", None), ("PEL134", None), ("PEL136", None)],
    "T4_APE1": [("PEA305", None), ("PEA307", None)],
    "T4_CE4": [("CSE316", None), ("MTH302", None)],
    "T4_CE5": [("CSE325", None)],
    "T4_EM1": [
        ("INT330", "CLOUD COMPUTING"),
        ("INT242", "CYBER SECURITY"),
        ("INT387", "DATA SCIENCE"),
        ("INT219", "FULL STACK WEB DEVELOPMENT"),
        ("ECE217", "INTERNET OF THINGS (IOT)"),
        ("CSE273", "MACHINE LEARNING"),
        ("CSE271", "SOFTWARE METHODOLOGIES AND TESTING"),
    ],
    "T4_EM2": [
        ("INT362", "CLOUD COMPUTING"),
        ("INT249", "CYBER SECURITY"),
        ("INT375", "DATA SCIENCE"),
        ("INT222", "FULL STACK WEB DEVELOPMENT"),
        ("ECE341", "INTERNET OF THINGS (IOT)"),
        ("CSE274", "MACHINE LEARNING"),
        ("CSE272", "SOFTWARE METHODOLOGIES AND TESTING"),
    ],
    "T5_EM3": [
        ("INT363", "CLOUD COMPUTING"),
        ("INT250", "CYBER SECURITY"),
        ("INT312", "DATA SCIENCE"),
        ("INT252", "FULL STACK WEB DEVELOPMENT"),
        ("ECE128", "INTERNET OF THINGS (IOT)"),
        ("CSE471", "MACHINE LEARNING"),
        ("CSE376", "SOFTWARE METHODOLOGIES AND TESTING"),
    ],
    "T5_EM4": [
        ("INT364", "CLOUD COMPUTING"),
        ("INT244", "CYBER SECURITY"),
        ("INT234", "DATA SCIENCE"),
        ("INT257", "FULL STACK WEB DEVELOPMENT"),
        ("ECE237", "INTERNET OF THINGS (IOT)"),
        ("CSE472", "MACHINE LEARNING"),
        ("CSE377", "SOFTWARE METHODOLOGIES AND TESTING"),
    ],
    "T5_PW1": [
        ("PEA306", "GOVERNMENT JOBS"),
        ("PEA308", "GOVERNMENT JOBS"),
        ("PEA308", "HIGHER STUDIES"),
        ("PEA306", "HIGHER STUDIES"),
        ("CSE329", "PRODUCT BASED"),
        ("PEA306", "SERVICE BASED"),
        ("PEA308", "SERVICE BASED"),
    ],
    "T5_PW2": [
        ("CSE333", "GOVERNMENT JOBS"),
        ("CSE333", "HIGHER STUDIES"),
        ("CSE330", "PRODUCT BASED"),
        ("PES390", "SERVICE BASED"),
    ],
    "T5_TE1": [("CSE343", None), ("CSE443", None)],
    "T6_EM5": [
        ("INT327", "CLOUD COMPUTING"),
        ("INT245", "CYBER SECURITY"),
        ("INT315", "DATA SCIENCE"),
        ("INT258", "FULL STACK WEB DEVELOPMENT"),
        ("ECE129", "INTERNET OF THINGS (IOT)"),
        ("CSE473", "MACHINE LEARNING"),
        ("CSE378", "SOFTWARE METHODOLOGIES AND TESTING"),
    ],
    "T6_PW3": [
        ("CSE334", "GOVERNMENT JOBS"),
        ("CSE334", "HIGHER STUDIES"),
        ("CSE331", "PRODUCT BASED"),
        ("CSE357", "SERVICE BASED"),
    ],
    "T6_PW4": [("PES391", "PRODUCT BASED"), ("PES391", "SERVICE BASED")],
    "T7CW_DE1": [
        ("CSE304", None),
        ("CSE327", None),
        ("CSE406", None),
        ("CSE434", None),
        ("CSE436", None),
        ("INT402", None),
    ],
    "T7CW_DE1LAB": [("CSE328", None)],
    "T7CW_EM6": [
        ("INT328", "CLOUD COMPUTING"),
        ("INT251", "CYBER SECURITY"),
        ("INT388", "DATA SCIENCE"),
        ("INT340", "FULL STACK WEB DEVELOPMENT"),
        ("ECE140", "INTERNET OF THINGS (IOT)"),
        ("CSE470", "MACHINE LEARNING"),
        ("CSE379", "SOFTWARE METHODOLOGIES AND TESTING"),
    ],
    "T7CW_PW4": [("CSE335", "GOVERNMENT JOBS"), ("CSE335", "HIGHER STUDIES")],
    "T8CW_DE2": [
        ("CSE403", None),
        ("CSE493", None),
        ("CSE504", None),
        ("INT411", None),
    ],
    "T8CW_DE2LAB": [("CSE507", None), ("INT416", None)],
    "T8INT_TE2": [("CSE441", None), ("CSE448", None)],
}

# The Open Minor basket: shared/global, referenced by OPEN MINOR 1-4 across
# Terms 5-8. Not tied to any single term_id.
OM_SHARED = [
    ("CSE273", "AI AND MACHINE LEARNING"),
    ("CSE274", "AI AND MACHINE LEARNING"),
    ("CSE470", "AI AND MACHINE LEARNING"),
    ("CSE471", "AI AND MACHINE LEARNING"),
    ("CSE472", "AI AND MACHINE LEARNING"),
    ("CSE473", "AI AND MACHINE LEARNING"),
    ("CSE224", "ANDROID APPLICATION DEVELOPMENT"),
    ("CSE225", "ANDROID APPLICATION DEVELOPMENT"),
    ("CSE226", "ANDROID APPLICATION DEVELOPMENT"),
    ("CSE227", "ANDROID APPLICATION DEVELOPMENT"),
    ("FIN314", "BANKING, INVESTMENT & FINANCIAL SERVICES"),
    ("FIN318", "BANKING, INVESTMENT & FINANCIAL SERVICES"),
    ("FIN319", "BANKING, INVESTMENT & FINANCIAL SERVICES"),
    ("FIN901", "BANKING, INVESTMENT & FINANCIAL SERVICES"),
    ("LAW252", "BUSINESS LAW, CONTRACTS & CORPORATE COMPLIANCE"),
    ("LAW255", "BUSINESS LAW, CONTRACTS & CORPORATE COMPLIANCE"),
    ("LAW256", "BUSINESS LAW, CONTRACTS & CORPORATE COMPLIANCE"),
    ("LAW257", "BUSINESS LAW, CONTRACTS & CORPORATE COMPLIANCE"),
    ("SSC231", "CIVIL SERVICES GENERAL STUDIES & PUBLIC AWARENESS"),
    ("SSC232", "CIVIL SERVICES GENERAL STUDIES & PUBLIC AWARENESS"),
    ("SSC233", "CIVIL SERVICES GENERAL STUDIES & PUBLIC AWARENESS"),
    ("SSC234", "CIVIL SERVICES GENERAL STUDIES & PUBLIC AWARENESS"),
    ("INT327", "CLOUD COMPUTING"),
    ("INT328", "CLOUD COMPUTING"),
    ("INT330", "CLOUD COMPUTING"),
    ("INT362", "CLOUD COMPUTING"),
    ("INT363", "CLOUD COMPUTING"),
    ("INT364", "CLOUD COMPUTING"),
    ("INT373", "CLOUD, DEVOPS, AND AGILE SYSTEMS ENGINEERING"),
    ("INT377", "CLOUD, DEVOPS, AND AGILE SYSTEMS ENGINEERING"),
    ("INT378", "CLOUD, DEVOPS, AND AGILE SYSTEMS ENGINEERING"),
    ("INT379", "CLOUD, DEVOPS, AND AGILE SYSTEMS ENGINEERING"),
    ("INT242", "CYBER SECURITY"),
    ("INT244", "CYBER SECURITY"),
    ("INT245", "CYBER SECURITY"),
    ("INT249", "CYBER SECURITY"),
    ("INT250", "CYBER SECURITY"),
    ("INT251", "CYBER SECURITY"),
    ("INT234", "DATA SCIENCE"),
    ("INT312", "DATA SCIENCE"),
    ("INT315", "DATA SCIENCE"),
    ("INT375", "DATA SCIENCE"),
    ("INT387", "DATA SCIENCE"),
    ("INT388", "DATA SCIENCE"),
    ("INT331", "DEVOPS"),
    ("INT332", "DEVOPS"),
    ("INT333", "DEVOPS"),
    ("INT334", "DEVOPS"),
    ("MKT311", "DIGITAL MARKETING, SEO & WEB ANALYTICS"),
    ("MKT905", "DIGITAL MARKETING, SEO & WEB ANALYTICS"),
    ("MKT906", "DIGITAL MARKETING, SEO & WEB ANALYTICS"),
    ("MKT907", "DIGITAL MARKETING, SEO & WEB ANALYTICS"),
    ("ECO214", "ECONOMICS, POLICY & TRADE ANALYSIS"),
    ("ECO215", "ECONOMICS, POLICY & TRADE ANALYSIS"),
    ("ECO324", "ECONOMICS, POLICY & TRADE ANALYSIS"),
    ("ECO325", "ECONOMICS, POLICY & TRADE ANALYSIS"),
    ("ENG606", "ENGLISH LANGUAGE AND LITERATURE"),
    ("ENG607", "ENGLISH LANGUAGE AND LITERATURE"),
    ("ENG608", "ENGLISH LANGUAGE AND LITERATURE"),
    ("ENG609", "ENGLISH LANGUAGE AND LITERATURE"),
    ("FST801", "FASHION DESIGN, CULTURE & SURFACE DEVELOPMENT"),
    ("FST802", "FASHION DESIGN, CULTURE & SURFACE DEVELOPMENT"),
    ("FST803", "FASHION DESIGN, CULTURE & SURFACE DEVELOPMENT"),
    ("FST804", "FASHION DESIGN, CULTURE & SURFACE DEVELOPMENT"),
    ("FIN212", "FINANCE, BANKING & INVESTMENT FUNDAMENTALS"),
    ("FIN213", "FINANCE, BANKING & INVESTMENT FUNDAMENTALS"),
    ("FIN308", "FINANCE, BANKING & INVESTMENT FUNDAMENTALS"),
    ("FIN314", "FINANCE, BANKING & INVESTMENT FUNDAMENTALS"),
    ("FIN214", "FINANCIAL MARKETS, TRADING & INVESTMENT PRODUCTS"),
    ("FIN215", "FINANCIAL MARKETS, TRADING & INVESTMENT PRODUCTS"),
    ("FIN314", "FINANCIAL MARKETS, TRADING & INVESTMENT PRODUCTS"),
    ("FIN358", "FINANCIAL MARKETS, TRADING & INVESTMENT PRODUCTS"),
    ("FRN114", "FRENCH"),
    ("FRN115", "FRENCH"),
    ("FRN116", "FRENCH"),
    ("FRN117", "FRENCH"),
    ("INT219", "FULL STACK WEB DEVELOPMENT"),
    ("INT222", "FULL STACK WEB DEVELOPMENT"),
    ("INT252", "FULL STACK WEB DEVELOPMENT"),
    ("INT257", "FULL STACK WEB DEVELOPMENT"),
    ("INT258", "FULL STACK WEB DEVELOPMENT"),
    ("INT340", "FULL STACK WEB DEVELOPMENT"),
    ("CAP818", "GAME DESIGN & INTERACTIVE DEVELOPMENT"),
    ("CAP819", "GAME DESIGN & INTERACTIVE DEVELOPMENT"),
    ("CAP820", "GAME DESIGN & INTERACTIVE DEVELOPMENT"),
    ("CAP821", "GAME DESIGN & INTERACTIVE DEVELOPMENT"),
    ("GEO295", "GEOGRAPHY, ENVIRONMENT & SPATIAL UNDERSTANDING"),
    ("GEO296", "GEOGRAPHY, ENVIRONMENT & SPATIAL UNDERSTANDING"),
    ("GEO297", "GEOGRAPHY, ENVIRONMENT & SPATIAL UNDERSTANDING"),
    ("GEO298", "GEOGRAPHY, ENVIRONMENT & SPATIAL UNDERSTANDING"),
    ("GER107", "GERMAN"),
    ("GER108", "GERMAN"),
    ("GER109", "GERMAN"),
    ("GER110", "GERMAN"),
    ("POL371", "GLOBAL POLITICS, DIPLOMACY & PUBLIC ETHICS"),
    ("POL372", "GLOBAL POLITICS, DIPLOMACY & PUBLIC ETHICS"),
    ("POL373", "GLOBAL POLITICS, DIPLOMACY & PUBLIC ETHICS"),
    ("POL374", "GLOBAL POLITICS, DIPLOMACY & PUBLIC ETHICS"),
    ("HRM203", "HUMAN RESOURCES, NEGOTIATION & WORKPLACE PSYCHOLOGY"),
    ("HRM204", "HUMAN RESOURCES, NEGOTIATION & WORKPLACE PSYCHOLOGY"),
    ("HRM301", "HUMAN RESOURCES, NEGOTIATION & WORKPLACE PSYCHOLOGY"),
    ("HRM302", "HUMAN RESOURCES, NEGOTIATION & WORKPLACE PSYCHOLOGY"),
    ("CSE291", "IMMERSIVE TECHNOLOGIES - AR/VR"),
    ("CSE292", "IMMERSIVE TECHNOLOGIES - AR/VR"),
    ("CSE293", "IMMERSIVE TECHNOLOGIES - AR/VR"),
    ("CSE294", "IMMERSIVE TECHNOLOGIES - AR/VR"),
    ("HIS291", "INDIAN AND WORLD HISTORY FOR CIVIL SERVICES"),
    ("HIS292", "INDIAN AND WORLD HISTORY FOR CIVIL SERVICES"),
    ("HIS293", "INDIAN AND WORLD HISTORY FOR CIVIL SERVICES"),
    ("HIS294", "INDIAN AND WORLD HISTORY FOR CIVIL SERVICES"),
    ("INT323", "INFORMATICA DATA MANAGEMENT"),
    ("INT324", "INFORMATICA DATA MANAGEMENT"),
    ("INT325", "INFORMATICA DATA MANAGEMENT"),
    ("INT326", "INFORMATICA DATA MANAGEMENT"),
    ("LAW351", "INTELLECTUAL PROPERTY, INNOVATION & CYBER LAW"),
    ("LAW352", "INTELLECTUAL PROPERTY, INNOVATION & CYBER LAW"),
    ("LAW353", "INTELLECTUAL PROPERTY, INNOVATION & CYBER LAW"),
    ("LAW354", "INTELLECTUAL PROPERTY, INNOVATION & CYBER LAW"),
    ("FIN348", "INTERNATIONAL TRADE & GLOBAL MARKETING"),
    ("MGN220", "INTERNATIONAL TRADE & GLOBAL MARKETING"),
    ("MGN902", "INTERNATIONAL TRADE & GLOBAL MARKETING"),
    ("MKT211", "INTERNATIONAL TRADE & GLOBAL MARKETING"),
    ("ECE128", "INTERNET OF ROBOTIC THINGS"),
    ("ECE129", "INTERNET OF ROBOTIC THINGS"),
    ("ECE140", "INTERNET OF ROBOTIC THINGS"),
    ("ECE217", "INTERNET OF ROBOTIC THINGS"),
    ("ECE237", "INTERNET OF ROBOTIC THINGS"),
    ("ECE341", "INTERNET OF ROBOTIC THINGS"),
    ("JAP105", "JAPANESE"),
    ("JAP106", "JAPANESE"),
    ("JAP107", "JAPANESE"),
    ("JAP108", "JAPANESE"),
    ("ACC211", "MANAGEMENT, FINANCE & MARKETING ESSENTIALS"),
    ("FIN212", "MANAGEMENT, FINANCE & MARKETING ESSENTIALS"),
    ("HRM203", "MANAGEMENT, FINANCE & MARKETING ESSENTIALS"),
    ("MKT202", "MANAGEMENT, FINANCE & MARKETING ESSENTIALS"),
    ("MKT202", "MARKETING AND SALES"),
    ("MKT257", "MARKETING AND SALES"),
    ("MKT258", "MARKETING AND SALES"),
    ("MKT311", "MARKETING AND SALES"),
    ("PID801", "PRODUCT DESIGN & PACKAGING INNOVATION"),
    ("PID802", "PRODUCT DESIGN & PACKAGING INNOVATION"),
    ("PID803", "PRODUCT DESIGN & PACKAGING INNOVATION"),
    ("PID804", "PRODUCT DESIGN & PACKAGING INNOVATION"),
    ("PSY281", "PSYCHOLOGY FOR COMPETITIVE EXAMS"),
    ("PSY282", "PSYCHOLOGY FOR COMPETITIVE EXAMS"),
    ("PSY283", "PSYCHOLOGY FOR COMPETITIVE EXAMS"),
    ("PSY284", "PSYCHOLOGY FOR COMPETITIVE EXAMS"),
    ("PSY260", "PSYCHOLOGY IN EVERYDAY LIFE"),
    ("PSY261", "PSYCHOLOGY IN EVERYDAY LIFE"),
    ("PSY262", "PSYCHOLOGY IN EVERYDAY LIFE"),
    ("PSY263", "PSYCHOLOGY IN EVERYDAY LIFE"),
    ("PBA396", "PUBLIC ADMINISTRATION, POLICY & GOVERNANCE"),
    ("PBA397", "PUBLIC ADMINISTRATION, POLICY & GOVERNANCE"),
    ("PBA398", "PUBLIC ADMINISTRATION, POLICY & GOVERNANCE"),
    ("PBA399", "PUBLIC ADMINISTRATION, POLICY & GOVERNANCE"),
    ("CSE271", "QUALITY ENGINEERING AND TEST AUTOMATION"),
    ("CSE272", "QUALITY ENGINEERING AND TEST AUTOMATION"),
    ("CSE376", "QUALITY ENGINEERING AND TEST AUTOMATION"),
    ("CSE377", "QUALITY ENGINEERING AND TEST AUTOMATION"),
    ("CSE378", "QUALITY ENGINEERING AND TEST AUTOMATION"),
    ("CSE379", "QUALITY ENGINEERING AND TEST AUTOMATION"),
    ("INT346", "ROBOTIC PROCESS AUTOMATION"),
    ("INT347", "ROBOTIC PROCESS AUTOMATION"),
    ("INT348", "ROBOTIC PROCESS AUTOMATION"),
    ("INT349", "ROBOTIC PROCESS AUTOMATION"),
    ("SOC371", "SOCIETY, MEDIA & SOCIAL BEHAVIOR ANALYSIS"),
    ("SOC372", "SOCIETY, MEDIA & SOCIAL BEHAVIOR ANALYSIS"),
    ("SOC373", "SOCIETY, MEDIA & SOCIAL BEHAVIOR ANALYSIS"),
    ("SOC374", "SOCIETY, MEDIA & SOCIAL BEHAVIOR ANALYSIS"),
    ("SPA107", "SPANISH"),
    ("SPA108", "SPANISH"),
    ("SPA109", "SPANISH"),
    ("SPA110", "SPANISH"),
    ("IFD801", "SPATIAL EXPERIENCE AND INTERIOR DESIGN"),
    ("IFD802", "SPATIAL EXPERIENCE AND INTERIOR DESIGN"),
    ("IFD803", "SPATIAL EXPERIENCE AND INTERIOR DESIGN"),
    ("IFD804", "SPATIAL EXPERIENCE AND INTERIOR DESIGN"),
    ("IXD801", "UI/UX DESIGN & HUMAN-CENTERED INTERFACES"),
    ("IXD802", "UI/UX DESIGN & HUMAN-CENTERED INTERFACES"),
    ("IXD803", "UI/UX DESIGN & HUMAN-CENTERED INTERFACES"),
    ("IXD804", "UI/UX DESIGN & HUMAN-CENTERED INTERFACES"),
    ("HMT141", "VACATION PLANNING AND MANAGEMENT"),
    ("HMT712", "VACATION PLANNING AND MANAGEMENT"),
    ("HMT752", "VACATION PLANNING AND MANAGEMENT"),
    ("HMT754", "VACATION PLANNING AND MANAGEMENT"),
]

# ---------------------------------------------------------------------------
# Term plans: (term_number, variant, label) -> list of slot dicts
# Each slot: s_no, type, nature, and EITHER course=<code> OR basket=<key>,
# with display_name for elective slots.
# ---------------------------------------------------------------------------

TERM_PLANS = [
    (
        1,
        None,
        "Term 1",
        [
            {
                "s_no": 1,
                "type": "CE",
                "nature": "ESC",
                "basket": "T1_CE1",
                "display_name": "CORE ELECTIVE 1",
            },
            {
                "s_no": 2,
                "type": "CE",
                "nature": "BSC",
                "basket": "T1_CE2",
                "display_name": "CORE ELECTIVE 2",
            },
            {
                "s_no": 3,
                "type": "CE",
                "nature": "BSC",
                "basket": "T1_CE3",
                "display_name": "CORE ELECTIVE 3",
            },
            {"s_no": 4, "type": "CR", "nature": "DSC", "course": "CSE111"},
            {"s_no": 5, "type": "CR", "nature": "DSC", "course": "CSE326"},
            {"s_no": 6, "type": "CR", "nature": "DSC", "course": "INT108"},
            {"s_no": 7, "type": "CR", "nature": "BSC", "course": "MTH174"},
            {"s_no": 8, "type": "CR", "nature": "LCS", "course": "PES318"},
        ],
    ),
    (
        2,
        None,
        "Term 2",
        [
            {
                "s_no": 1,
                "type": "CE",
                "nature": "ESC",
                "basket": "T2_CE1",
                "display_name": "CORE ELECTIVE 1",
            },
            {
                "s_no": 2,
                "type": "CE",
                "nature": "BSC",
                "basket": "T2_CE2",
                "display_name": "CORE ELECTIVE 2",
            },
            {
                "s_no": 3,
                "type": "CE",
                "nature": "BSC",
                "basket": "T2_CE3",
                "display_name": "CORE ELECTIVE 3",
            },
            {
                "s_no": 4,
                "type": "LE",
                "nature": "LCS",
                "basket": "T2_LE1",
                "display_name": "LANGUAGE ELECTIVE 1",
            },
            {"s_no": 5, "type": "CR", "nature": "DSC", "course": "CSE101"},
            {"s_no": 6, "type": "CR", "nature": "DSC", "course": "CSE121"},
            {"s_no": 7, "type": "CR", "nature": "DSC", "course": "CSE320"},
            {"s_no": 8, "type": "CR", "nature": "DSC", "course": "INT306"},
            {"s_no": 9, "type": "CR", "nature": "BSC", "course": "MTH401"},
        ],
    ),
    (
        3,
        None,
        "Term 3",
        [
            {
                "s_no": 1,
                "type": "CE",
                "nature": "DSC",
                "basket": "T3_CE4",
                "display_name": "CORE ELECTIVE 4",
            },
            {
                "s_no": 2,
                "type": "CE",
                "nature": "DSC",
                "basket": "T3_CE5",
                "display_name": "CORE ELECTIVE 5",
            },
            {
                "s_no": 3,
                "type": "LE",
                "nature": "LCS",
                "basket": "T3_LE2",
                "display_name": "LANGUAGE ELECTIVE 2",
            },
            {"s_no": 4, "type": "CR", "nature": "DSC", "course": "CSE202"},
            {"s_no": 5, "type": "CR1", "nature": "DSC", "course": "CSE205"},
            {"s_no": 6, "type": "CR1", "nature": "DSC", "course": "CSE306"},
            {"s_no": 7, "type": "CR1", "nature": "DSC", "course": "CSE307"},
            {"s_no": 8, "type": "CR3", "nature": "PRC", "course": "GEN231"},
        ],
    ),
    (
        4,
        None,
        "Term 4",
        [
            {
                "s_no": 1,
                "type": "APE",
                "nature": "EEA",
                "basket": "T4_APE1",
                "display_name": "APTITUDE ELECTIVE 1",
            },
            {
                "s_no": 2,
                "type": "CE",
                "nature": "DSC",
                "basket": "T4_CE4",
                "display_name": "CORE ELECTIVE 4",
            },
            {
                "s_no": 3,
                "type": "CE",
                "nature": "DSC",
                "basket": "T4_CE5",
                "display_name": "CORE ELECTIVE 5",
            },
            {
                "s_no": 4,
                "type": "EM",
                "nature": "DSC",
                "basket": "T4_EM1",
                "display_name": "ENGINEERING MINOR ELECTIVE 1",
            },
            {
                "s_no": 5,
                "type": "EM",
                "nature": "DSC",
                "basket": "T4_EM2",
                "display_name": "ENGINEERING MINOR ELECTIVE 2",
            },
            {"s_no": 6, "type": "CR", "nature": "DSC", "course": "CSE211"},
            {"s_no": 7, "type": "CR", "nature": "DSC", "course": "CSE310"},
            {"s_no": 8, "type": "CR", "nature": "DSC", "course": "INT428"},
        ],
    ),
    (
        5,
        None,
        "Term 5",
        [
            {
                "s_no": 1,
                "type": "EM",
                "nature": "DSC",
                "basket": "T5_EM3",
                "display_name": "ENGINEERING MINOR ELECTIVE 3",
            },
            {
                "s_no": 2,
                "type": "EM",
                "nature": "DSC",
                "basket": "T5_EM4",
                "display_name": "ENGINEERING MINOR ELECTIVE 4",
            },
            {
                "s_no": 3,
                "type": "OM",
                "nature": "OEM",
                "basket": "OM_SHARED",
                "display_name": "OPEN MINOR 1",
            },
            {
                "s_no": 4,
                "type": "PW",
                "nature": "PWE",
                "basket": "T5_PW1",
                "display_name": "PATHWAY ELECTIVE 1",
            },
            {
                "s_no": 5,
                "type": "PW",
                "nature": "PWE",
                "basket": "T5_PW2",
                "display_name": "PATHWAY ELECTIVE 2",
            },
            {
                "s_no": 6,
                "type": "TE",
                "nature": "TCS",
                "basket": "T5_TE1",
                "display_name": "TRAINING ELECTIVE 1",
            },
            {"s_no": 7, "type": "CR", "nature": "DSC", "course": "CSE408"},
        ],
    ),
    (
        6,
        None,
        "Term 6",
        [
            {
                "s_no": 1,
                "type": "EM",
                "nature": "DSC",
                "basket": "T6_EM5",
                "display_name": "ENGINEERING MINOR ELECTIVE 5",
            },
            {
                "s_no": 2,
                "type": "OM",
                "nature": "OEM",
                "basket": "OM_SHARED",
                "display_name": "OPEN MINOR 2",
            },
            {
                "s_no": 3,
                "type": "PW",
                "nature": "PWE",
                "basket": "T6_PW3",
                "display_name": "PATHWAY ELECTIVE 3",
            },
            {
                "s_no": 4,
                "type": "PW",
                "nature": "DSC",
                "basket": "T6_PW4",
                "display_name": "PATHWAY ELECTIVE 4",
            },
            {"s_no": 5, "type": "CR", "nature": "DSC", "course": "CSE322"},
            {"s_no": 6, "type": "CR", "nature": "DSC", "course": "CSE332"},
            {"s_no": 7, "type": "CR", "nature": "DSC", "course": "CSE393"},
        ],
    ),
    (
        7,
        "course_work",
        "Term 7 (course work)",
        [
            {
                "s_no": 1,
                "type": "DE",
                "nature": "DSC",
                "basket": "T7CW_DE1",
                "display_name": "DEPARTMENT ELECTIVE 1",
            },
            {
                "s_no": 2,
                "type": "DE",
                "nature": "DSC",
                "basket": "T7CW_DE1LAB",
                "display_name": "DEPARTMENT ELECTIVE 1 LAB",
            },
            {
                "s_no": 3,
                "type": "EM",
                "nature": "DSC",
                "basket": "T7CW_EM6",
                "display_name": "ENGINEERING MINOR ELECTIVE 6",
            },
            {
                "s_no": 4,
                "type": "OM",
                "nature": "OEM",
                "basket": "OM_SHARED",
                "display_name": "OPEN MINOR 3",
            },
            {
                "s_no": 5,
                "type": "PW",
                "nature": "PWE",
                "basket": "T7CW_PW4",
                "display_name": "PATHWAY ELECTIVE 4",
            },
            {"s_no": 6, "type": "CR", "nature": "PRJ", "course": "CSE339"},
        ],
    ),
    (
        7,
        "industrial_internship",
        "Term 7 (industrial internship)",
        [
            {"s_no": 1, "type": "CR", "nature": "TCF", "course": "CSE447"},
        ],
    ),
    (
        8,
        "course_work",
        "Term 8 (course work)",
        [
            {
                "s_no": 1,
                "type": "DE",
                "nature": "DSC",
                "basket": "T8CW_DE2",
                "display_name": "DEPARTMENT ELECTIVE 2",
            },
            {
                "s_no": 2,
                "type": "DE",
                "nature": "DSC",
                "basket": "T8CW_DE2LAB",
                "display_name": "DEPARTMENT ELECTIVE 2 LAB",
            },
            {
                "s_no": 3,
                "type": "OM",
                "nature": "OEM",
                "basket": "OM_SHARED",
                "display_name": "OPEN MINOR 4",
            },
            {"s_no": 4, "type": "CR", "nature": "SMN", "course": "CSE435"},
            {"s_no": 5, "type": "CR", "nature": "PRJ", "course": "CSE439"},
        ],
    ),
    (
        8,
        "industrial_internship",
        "Term 8 (industrial internship)",
        [
            {
                "s_no": 1,
                "type": "TE",
                "nature": "TCF",
                "basket": "T8INT_TE2",
                "display_name": "TRAINING ELECTIVE 2",
            },
        ],
    ),
]


# ---------------------------------------------------------------------------
# Get-or-create helpers (idempotent loading)
# ---------------------------------------------------------------------------


def get_or_create_lookup(session, model, code, description):
    obj = session.get(model, code)
    if obj is None:
        obj = model(code=code, description=description)
        session.add(obj)
        session.flush()
    return obj


def get_or_create_course(session, code, course_cache):
    if code in course_cache:
        return course_cache[code]
    obj = session.query(Course).filter_by(code=code).one_or_none()
    if obj is None:
        title, l, t, p, credit, contact = COURSES[code]
        obj = Course(
            code=code,
            title=title,
            lecture_hours=l,
            tutorial_hours=t,
            practical_hours=p,
            credits=credit,
            contact_hours=contact,
        )
        session.add(obj)
        session.flush()
    course_cache[code] = obj
    return obj


def get_or_create_area(session, name, area_cache):
    if name is None:
        return None
    if name in area_cache:
        return area_cache[name]
    obj = session.query(ElectiveArea).filter_by(name=name).one_or_none()
    if obj is None:
        obj = ElectiveArea(name=name)
        session.add(obj)
        session.flush()
    area_cache[name] = obj
    return obj


def get_or_create_term(session, number, variant, label):
    obj = session.query(Term).filter_by(number=number, variant=variant).one_or_none()
    if obj is None:
        obj = Term(number=number, variant=variant, label=label)
        session.add(obj)
        session.flush()
    return obj


def get_or_create_basket(session, name, term_id, course_cache, area_cache, options):
    """term_id=None means a shared basket (e.g. the Open Minor basket)."""
    obj = (
        session.query(ElectiveBasket)
        .filter_by(name=name, term_id=term_id)
        .one_or_none()
    )
    if obj is None:
        obj = ElectiveBasket(name=name, term_id=term_id)
        session.add(obj)
        session.flush()
        for i, (course_code, area_name) in enumerate(options, start=1):
            course = get_or_create_course(session, course_code, course_cache)
            area = get_or_create_area(session, area_name, area_cache)
            exists = (
                session.query(BasketOption)
                .filter_by(
                    basket_id=obj.id,
                    course_id=course.id,
                    elective_area_id=(area.id if area else None),
                )
                .one_or_none()
            )
            if exists is None:
                session.add(
                    BasketOption(
                        basket_id=obj.id,
                        course_id=course.id,
                        elective_area_id=(area.id if area else None),
                        s_no=i,
                    )
                )
    return obj


def get_or_create_slot(
    session, term, s_no, display_name, course_id, basket_id, type_code, nature_code
):
    obj = session.query(TermSlot).filter_by(term_id=term.id, s_no=s_no).one_or_none()
    if obj is None:
        obj = TermSlot(
            term_id=term.id,
            s_no=s_no,
            display_name=display_name,
            course_id=course_id,
            basket_id=basket_id,
            course_type_code=type_code,
            course_nature_code=nature_code,
        )
        session.add(obj)
    return obj


# ---------------------------------------------------------------------------
# Main load routine
# ---------------------------------------------------------------------------


def load_all(session):
    course_cache = {}
    area_cache = {}

    # 1. Lookup tables
    for code, desc in COURSE_TYPES.items():
        get_or_create_lookup(session, CourseType, code, desc)
    for code, desc in COURSE_NATURES.items():
        get_or_create_lookup(session, CourseNature, code, desc)

    # 2. Shared Open Minor basket (term_id=None), created once up front
    #    so all four OPEN MINOR slots can point to the same row.
    om_basket = get_or_create_basket(
        session,
        "Open Minor Elective (OM) Basket",
        None,
        course_cache,
        area_cache,
        OM_SHARED,
    )

    # 3. Terms, their fixed courses, and their term-specific baskets
    for number, variant, label, slots in TERM_PLANS:
        term = get_or_create_term(session, number, variant, label)

        for slot in slots:
            course_id = None
            basket_id = None

            if "course" in slot:
                course = get_or_create_course(session, slot["course"], course_cache)
                course_id = course.id
            else:
                basket_key = slot["basket"]
                if basket_key == "OM_SHARED":
                    basket_id = om_basket.id
                else:
                    basket_name = f"{slot['display_name']} BASKET"
                    basket = get_or_create_basket(
                        session,
                        basket_name,
                        term.id,
                        course_cache,
                        area_cache,
                        BASKETS[basket_key],
                    )
                    basket_id = basket.id

            get_or_create_slot(
                session,
                term,
                slot["s_no"],
                slot.get("display_name"),
                course_id,
                basket_id,
                slot["type"],
                slot["nature"],
            )

    session.commit()


if __name__ == "__main__":
    Base.metadata.create_all(engine, checkfirst=True)  # ensure tables exist

    session = SessionLocal()
    try:
        load_all(session)
        print("Load complete.")

        # quick sanity check
        n_courses = session.query(Course).count()
        n_terms = session.query(Term).count()
        n_baskets = session.query(ElectiveBasket).count()
        n_options = session.query(BasketOption).count()
        n_slots = session.query(TermSlot).count()
        print(
            f"courses={n_courses} terms={n_terms} baskets={n_baskets} "
            f"basket_options={n_options} term_slots={n_slots}"
        )
    finally:
        session.close()
