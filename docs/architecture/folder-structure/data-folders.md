project-root/
├── config/
│   └── features/
│       └── mlb_rfi_features.json
├── data/
│   ├── raw/                ← External, unprocessed sources (e.g., statcast CSVs)
│   │   └── statcast_7d_raw.csv
│   ├── processed/          ← Aggregated, cleaned, ready for modeling
│   │   └── team_woba_7d.json
│   │   └── team_woba_splits_combined.json
│   ├── interim/            ← Partial pipeline output, not final or clean
│   ├── outputs/            ← Final predictions or exported model-ready sheets
│   │   └── woba3_features_7d_14d.csv
│   └── features/           ← (Optional) if you want to isolate feature matrices (not definitions)
├── logs/
│   └── mlb_pipeline.log
├── models/
├── notebooks/
└── src/
