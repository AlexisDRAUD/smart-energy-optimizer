# Smart Energy Optimizer API

FastAPI implementation of the authoritative v1 contract. Interactive OpenAPI
documentation is served at [`/docs`](http://localhost:8080/docs); all business
routes are under `/api/v1`.

## Run locally

```sh
cd services/api
cp .env.example .env # set a real JWT_SECRET_KEY outside local development
./scripts/start.sh
```

The startup script verifies the database and applies Alembic migrations before
starting the server. Schema changes live in `alembic/versions`; the application
does not call `create_all`.

For a local SQLite database, the first application startup creates a small
demonstration dataset. This is only a local/test convenience: production ETL
owns `sites`, `readings`, `sensor_status`, `etl_runs`, and
`data_quality_daily`. The API runtime loop writes only `predictions`.

```sh
.venv/bin/pytest -q
```

## Authentication and roles

`POST /api/v1/auth/login` accepts JSON:

```json
{"email": "camille.martin@enervision.demo", "password": "EnerVisionDemo2026!"}
```

It returns a signed 15-minute bearer token. Send it as
`Authorization: Bearer <token>`. `GET /api/v1/auth/me` returns the current
identity.

| Role | Permissions |
| --- | --- |
| `viewer` | Read every site and dashboard resource |
| `operator` | Viewer permissions and acknowledge alerts |
| `admin` | Viewer permissions and manage accounts at `/api/v1/users` |

Local demo accounts are `camille.martin@enervision.demo` (admin),
`lucas.bernard@enervision.demo` (operator), and
`marc.legrand@enervision.demo` (viewer), all with the password above.
There is no provisioning key or per-user site restriction.

## Endpoint summary

| Resource | Routes |
| --- | --- |
| Sites and readings | `GET /sites`, `GET /sites/{site_id}`, `GET /sites/{site_id}/latest`, `GET /readings` |
| Dashboard quality | `GET /overview`, `GET /quality`, `GET /quality/sensors`, `GET /status` |
| Predictions | `GET /predictions/latest`, `GET /predictions`, `GET /predictions/model`, `GET /predictions/model/performance` |
| Alerts | `GET /alerts`, `GET /alerts/summary`, `POST /alerts/{id}/acknowledge` |
| Recommendations | `GET /recommendations?site_id=...` |
| Accounts | `GET/POST /users`, `PATCH /users/{id}` (admin) |

`site_id` is a source-supplied string. Reading requests require it and accept
UTC ISO-8601 `start` and `end`, `granularity` (`minute`, `quarter`, `hour`,
`day`), `limit`, and `offset`. They always include a completeness summary.
Lists that can be paged include `total`, `limit`, and `offset`.

All timestamps are returned in UTC with a `Z` suffix. Errors use
`{"error":{"code":"...","message":"..."}}`. The public `/health` endpoint
reports database availability and the applied Alembic model version.

## Prediction fallback

The API has no MLflow dependency. If MLflow is unavailable,
`GET /predictions/model` explicitly reports the locally loaded
`local-moving-average` fallback and `mlflow_available: false`. Forecast records
are stored in `predictions`, never in `readings`, at a 120-minute horizon.
