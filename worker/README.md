# Worker — Celery AI Engine

This package contains the asynchronous **Celery workers** responsible for all heavy AI processing.

## Structure

```
worker/
├── tasks/
│   ├── __init__.py
│   ├── preprocess.py    # DataPreprocessor: clean CSVs from S3
│   ├── forecast.py      # ProphetStrategy: 30/90 day forecasts
│   ├── sentiment.py     # BERT sentiment analysis
│   └── insights.py      # Groq LLM insight generation
├── celery_app.py        # Celery app configuration
├── requirements.txt
├── Dockerfile
└── .env.example
```

## AI Libraries

- `prophet` — Time Series Forecasting
- `transformers` + `torch` — Multilingual BERT Sentiment Analysis
- `scikit-learn`, `pandas` — Data Processing
- `groq` — LLaMA 3 LLM API for natural language insights

## Local Dev

```bash
pip install -r requirements.txt
celery -A celery_app worker --loglevel=info
```
