# Sports Predictive Models 🧠⚾🏀

A collection of machine learning models designed to make sports predictions, starting with MLB Run First Inning (RFI) predictions.

---

## 📂 Project Structure


## Getting Started

### 1. Create & activate a virtual environment  
```bash
python3 -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1

Install Dependencies
pip install --upgrade pip
pip install .[tests]


## Usage

**Fetch today’s schedule** (defaults to today’s date):  
```bash
python fetch_schedule.py

Fetch for a specific date:
python fetch_schedule.py 2025-07-02

Save raw JSON into your configured directory:
python fetch_schedule.py 2025-07-02 --save-json

Run the unit tests:
python fetch_schedule.py --test
