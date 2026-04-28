# Infrastructure

This folder contains all DevOps and infrastructure configuration.

## Contents

```
infrastructure/
├── docker/           # Per-service Dockerfiles (if not co-located)
├── nginx/            # Nginx reverse proxy config for production
└── README.md
```

The root `docker-compose.yml` (one level up) is the primary local dev entrypoint.

## Production Hosting & Tools

| Category | Tool & Dashboard | Status/Details |
|---|---|---|
| **Cloud Hosting** | DigitalOcean (Frankfurt Droplet live) | Hosting backend/worker/frontend |
| **Secret Ops** | Doppler (Workplace created - replacing .env files) | Secrets injection, no .env commits |
| **Data Layer** | PostgreSQL (DO Managed for core data) & MongoDB (Student Cluster for scraped data) | Relational for transactions, NoSQL for messy hardware data |
| **R&D / Science** | Deepnote (Workspace live) & Camber (AI Chat/Compute) | Model training sandbox |
| **Observability** | Datadog (Student Pack) & Sentry (Error tracking) | Monitoring & error alerts |
| **Optimization** | Blackfire (Health reports live) | Performance profiling |
| **Code Health** | DeepScan (Team dashboard) & CodeScene (Project analysis) | Bug hunting & tech debt |
| **Frontend Dev** | Polypane (Local UI) & BrowserStack (Cloud Testing) | Responsive & cross-browser testing |
| **Architecture** | ToDiagram (Documentation diagrams) | YAML/JSON to architecture maps |
| **Advanced Data** | CARTO (Spatial maps live) | Geographic heatmaps |
| **Team Velocity** | Requestly (API Mocking) & POEditor (Localization) | Frontend dev & i18n |

## Notes
- **Database**: Core data uses PostgreSQL (DO Managed). Scraped data uses MongoDB Student Cluster.
- **Secrets**: Use Doppler for all env vars in production.
- **Monitoring**: Datadog for metrics, Sentry for errors, Blackfire for profiling.
- **Frontend**: Polypane for local dev, BrowserStack for QA.
- **Localization**: POEditor for English/Arabic.
- **Diagrams**: Use ToDiagram for docs.
- **Maps**: CARTO for spatial analysis.
