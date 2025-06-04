# 📁 Project: NRFI/YRFI Prediction Engine

# ──────────────────────────────────────────────
# 📁 Directory Structure

sports-predictive-models/
├── README.md
├── requirements.txt
├── .env                        # Optional: API keys
├── data/
│   ├── raw/                    # Cached API pulls
│   └── processed/              # Feature-ready CSVs
├── docs/
│   └── images/
│       └── rfi_workflow.png   # Workflow PNG
├── models/
│   └── xgboost_nrfi_model.pkl # Trained model (pickle)
├── notebooks/
│   └── train_xgboost_nrfi.ipynb
├── src/
│   ├── __init__.py
│   ├── config.py               # Model thresholds, weights
│   ├── fetch_schedule.py       # Pull games, starters from MLB Stats API
│   ├── fetch_stats.py          # Pitcher & batter stat extraction
│   ├── features.py             # Feature engineering logic
│   ├── predict.py              # Run XGBoost model on game features
│   ├── agent_writer.py         # LLM/templated recommendation generator
│   ├── export.py               # Output to CSV, Markdown, Google Sheets
│   └── main.py                 # Full pipeline script
└── tests/
    └── test_predict.py         # Unit test example


# ──────────────────────────────────────────────
# 🚀 Usage Flow

# 1. 🔁 Fetch schedule + starters
python src/fetch_schedule.py --date 2025-05-24

# 2. 📊 Pull stats + features
python src/fetch_stats.py
python src/features.py

# 3. 🤖 Predict NRFI/YRFI
python src/predict.py

# 4. ✍️ Generate recommendations
python src/agent_writer.py

# 5. 💾 Export CSV, Markdown, Google Sheets
python src/export.py --to csv --to md

# 6. (Optional) 🧪 Unit tests
pytest tests/


# 🧠 Model
# Train in `notebooks/train_xgboost_nrfi.ipynb` using pitcher/batter feature matrix
# Save model to `models/xgboost_nrfi_model.pkl`

# Want live hosting?
# Extend with FastAPI, Streamlit, or cron jobs for auto-refresh
