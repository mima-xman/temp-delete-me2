"""
Configuration constants for the GitHub account generator project.

This module contains all configuration settings for GitHub account generation,
browser settings, and output paths.
"""

import os
from typing import Dict, List

# ==============================================================================
# Tor Network Settings
# ==============================================================================

# Tor SOCKS proxy port (9150 for Tor Browser, 9050 for system Tor)
TOR_PORT: int = int(os.getenv("TOR_PORT", 9150))

# Tor control port for circuit renewal (9151 for Tor Browser, 9051 for system Tor)
TOR_CONTROL_PORT: int = int(os.getenv("TOR_CONTROL_PORT", 9151))

# ==============================================================================
# Account Generation Settings
# ==============================================================================

FIRST_NAMES: List[str] = [
    "Liam", "Noah", "Oliver", "Elijah", "William", "James", "Benjamin", "Lucas",
    "Henry", "Alexander", "Mason", "Michael", "Ethan", "Daniel", "Jacob", "Logan",
    "Jackson", "Levi", "Sebastian", "Mateo", "Jack", "Owen", "Theodore", "Aiden",
    "Samuel", "Joseph", "John", "David", "Wyatt", "Matthew", "Luke", "Asher",
    "Carter", "Julian", "Grayson", "Leo", "Jayden", "Gabriel", "Isaac", "Lincoln",
    "Anthony", "Hudson", "Dylan", "Ezra", "Thomas", "Charles", "Christopher",
    "Jaxon", "Maverick", "Josiah", "Isaiah", "Andrew", "Elias", "Joshua", "Nathan",
    "Caleb", "Ryan", "Adrian", "Miles", "Eli", "Nolan", "Christian", "Aaron",
    "Cameron", "Ezekiel", "Colton", "Luca", "Landon", "Hunter", "Jonathan",
    "Santiago", "Axel", "Easton", "Cooper", "Jeremiah", "Angel", "Roman", "Connor",
    "Jameson", "Robert", "Greyson", "Jordan", "Ian", "Carson", "Jaxson", "Leonardo",
    "Nicholas", "Dominic", "Austin", "Everett", "Brooks", "Xavier", "Kai", "Jose",
    "Parker", "Adam", "Jace", "Wesley", "Kayden", "Silas", "Bennett", "Declan",
    "Waylon", "Weston", "Evan", "Emmett", "Micah", "Ryder", "Beau", "Damian",
    "Brayden", "Gael", "Rowan", "Harrison", "Bryson", "Sawyer", "Amir", "Kingston",
    "Jason", "Giovanni", "Vincent", "Ayden", "Chase", "Myles", "Diego", "Nathaniel",
    "Legend", "Jonah", "River", "Tyler", "Cole", "Braxton", "George", "Milo",
    "Zachary", "Ashton", "Luis", "Jasper", "Kaiden", "Adriel", "Gavin", "Bentley",
    "Calvin", "Zion", "Juan", "Maxwell", "Max", "Ryker", "Carlos", "Emmanuel",
    "Jayce", "Lorenzo", "Ivan", "Jude", "August", "Kevin", "Malachi", "Elliott",
    "Rhett", "Archer", "Karter", "Arthur", "Lukas", "Elliot", "Thiago", "Brandon",
    "Camden", "Justin", "Jesus", "Maddox", "King", "Theo", "Enzo", "Matteo",
    "Emilio", "Dean", "Hayden", "Finn", "Brody", "Antonio", "Abel", "Tristan",
    "Graham", "Zayden", "Judah", "Xander", "Miguel", "Atlas", "Tucker", "Timothy"
]

LAST_NAMES: List[str] = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
    "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker",
    "Young", "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill",
    "Flores", "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell",
    "Mitchell", "Carter", "Roberts", "Gomez", "Phillips", "Evans", "Turner",
    "Diaz", "Parker", "Cruz", "Edwards", "Collins", "Reyes", "Stewart", "Morris",
    "Morales", "Murphy", "Cook", "Rogers", "Gutierrez", "Ortiz", "Morgan", "Cooper",
    "Peterson", "Bailey", "Reed", "Kelly", "Howard", "Ramos", "Kim", "Cox",
    "Ward", "Richardson", "Watson", "Brooks", "Chavez", "Wood", "James", "Bennett",
    "Gray", "Mendoza", "Ruiz", "Hughes", "Price", "Alvarez", "Castillo", "Sanders",
    "Patel", "Myers", "Long", "Ross", "Foster", "Jimenez", "Powell", "Jenkins",
    "Perry", "Russell", "Sullivan", "Bell", "Coleman", "Butler", "Henderson",
    "Barnes", "Gonzales", "Fisher", "Vasquez", "Simmons", "Romero", "Jordan",
    "Patterson", "Alexander", "Hamilton", "Graham", "Reynolds", "Griffin",
    "Wallace", "Moreno", "West", "Cole", "Hayes", "Bryant", "Herrera", "Gibson",
    "Ellis", "Tran", "Medina", "Aguilar", "Stevens", "Murray", "Ford", "Castro",
    "Marshall", "Owens", "Harrison", "Fernandez", "McDonald", "Woods", "Washington",
    "Kennedy", "Wells", "Vargas", "Henry", "Chen", "Freeman", "Webb", "Tucker",
    "Guzman", "Burns", "Crawford", "Olson", "Simpson", "Porter", "Hunter", "Gordon",
    "Mendez", "Silva", "Shaw", "Snyder", "Mason", "Dixon", "Munoz", "Hunt",
    "Hicks", "Holmes", "Palmer", "Wagner", "Black", "Robertson", "Boyd", "Rose",
    "Stone", "Salazar", "Fox", "Warren", "Mills", "Meyer", "Rice", "Schmidt",
    "Garza", "Daniels", "Ferguson", "Nichols", "Stephens", "Soto", "Weaver",
    "Ryan", "Gardner", "Payne", "Grant", "Dunn", "Kelley", "Spencer", "Hawkins"
]

# Username suffix appended to generated usernames
USERNAME_SUFFIX: str = "miamore"

# Maximum wait time for verification code (in seconds)
MAX_WAIT_TIME_FOR_VERIFICATION_CODE: int = 120

# Maximum retries for account creation
MAX_RETRIES_FOR_ACCOUNT_CREATION: int = 3

# ==============================================================================
# Browser Settings
# ==============================================================================

# Browser viewport dimensions
VIEWPORT: Dict[str, int] = {'width': 1024, 'height': 768}

# Browser locale for internationalization
LOCALE: str = 'fr-FR'

# User agent string for browser requests
USER_AGENT: str = (
    'Mozilla/5.0 (Linux; Android 12; SM-G975F Build/QP1A.190711.002; wv) '
    'AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/120.0.0.0 '
    'Mobile Safari/537.36'
)

# Run browser in headless mode
HEADLESS: bool = False

# Browser launch arguments for anti-detection
ARGS: List[str] = [
    '--disable-blink-features=AutomationControlled',
    '--no-sandbox',
    '--disable-setuid-sandbox',
    '--disable-infobars',
    '--ignore-certificate-errors',
    f'--user-agent={USER_AGENT}'
]

# Browser executable paths
BRAVE_PATH: str = r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"
CHROME_PATH: str = os.getenv("CHROME_PATH", r"C:\Program Files\Google\Chrome\Application\chrome.exe")

# ==============================================================================
# Output Settings
# ==============================================================================

OUTPUT_DIR: str = "output"