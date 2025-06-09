tennis_model_project/
├── README.md
├── requirements.txt
├── config/
│   └── settings.py              # global constants, API keys, weights, thresholds
├── data/
│   ├── raw/                     # pulled or scraped raw data
│   ├── processed/               # cleaned and engineered feature sets
│   └── external/                # manually added stats or expert previews
├── features/
│   ├── __init__.py
│   ├── surface_skill.py         # ✅ where the SurfaceSkillFeature class goes
│   ├── overusage.py             # handles fatigue-based metrics
│   ├── recent_form.py           # calculates momentum / recent wins
│   └── head_to_head.py          # encapsulates H2H-specific logic
├── models/
│   ├── __init__.py
│   ├── logistic_model.py        # base logistic model with all features
│   └── monte_carlo_sim.py       # simulation logic for totals, spreads, etc.
├── pipelines/
│   ├── __init__.py
│   ├── generate_features.py     # loads raw data → returns feature vectors
│   └── inference.py             # runs the model and returns predictions
├── notebooks/
│   └── exploratory_analysis.ipynb  # backtesting, feature analysis
├── outputs/
│   ├── predictions/
│   └── backtests/
├── utils/
│   ├── scraper.py               # scraping flashscore/tennisabstract
│   ├── helpers.py               # general utilities
│   └── ev_calculator.py         # expected value logic
└── main.py                      # CLI or interface entry point
