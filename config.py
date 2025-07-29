import os
from pathlib import Path
import streamlit as st

# Base paths
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / 'data'
OUTPUT_DIR = BASE_DIR / 'output'

# Create directories if they don't exist
DATA_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# API Configuration
try:
    DEEPSEEK_API_KEY = st.secrets["DEEPSEEK_API_KEY"]
except:
    DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
DEEPSEEK_MODEL = 'deepseek-reasoner'
DEEPSEEK_BASE_URL = 'https://api.deepseek.com'

# Analysis Configuration
MAX_RETRIES = 2
RETRY_DELAY = 2

# Scoring thresholds
SCORE_LEVELS = {
    'MISSING': 0,
    'POOR': 25,
    'AVERAGE': 50,
    'GOOD': 75,
    'EXCELLENT': 100
}