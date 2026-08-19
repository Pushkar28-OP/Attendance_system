# Aurelix Smart Attendance

A production-oriented MVP for internal employee attendance. A check-in is accepted only after authenticated identity, a single-face embedding match, a short motion-based liveness challenge, and an office geofence check all pass.

> **MVP security note:** liveness currently verifies natural frame-to-frame embedding movement. It is deliberately isolated behind `backend/app/services/liveness_service.py` so a calibrated anti-spoofing model can replace it before high-security production use.

## Architecture

- **Frontend:** React, Vite, Tailwind CSS, React Router, Axios, browser camera and geolocation APIs.
- **Backend:** FastAPI, Pydantic, Uvicorn, JWT, bcrypt, SlowAPI.
- **Database:** MongoDB / MongoDB Atlas through PyMongo.
- **Computer vision:** InsightFace ArcFace embeddings with OpenCV image decoding. Raw face images are not persisted.
- **Cloud readiness:** stateless API, environment configuration, CORS allowlist, no local file storage.

The verification service runs: authenticated employee -> face extraction -> embedding similarity -> liveness -> Haversine geofence -> duplicate check -> attendance write and audit event.

## Structure

```text
backend/
  app/
    api/              auth, employees, attendance, face, admin, audit routes
    core/             settings and JWT/password security
    db/               MongoDB client and indexes
    models/           persistence document builders
    schemas/          validated request/response models
    services/         face, liveness, location, attendance decision engine
    utils/            Haversine distance helper
  scripts/create_admin.py
  tests/test_core.py
frontend/
  src/App.jsx         authenticated shell, login, employee and admin views
  src/services/api.js Axios client
  src/styles.css      responsive enterprise UI
```

## Prerequisites

- Python 3.11+
- Node.js 20+
- MongoDB 7+ locally or a MongoDB Atlas cluster
- A browser with camera and geolocation support; camera/geolocation generally require HTTPS outside localhost

## Setup

From the repository root:

```powershell
Copy-Item .env.example .env
```

Edit `.env`. Set `OFFICE_LATITUDE`, `OFFICE_LONGITUDE`, and `OFFICE_RADIUS_METERS` to the authorized Aurelix office. Never commit `.env`.

### Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:PYTHONPATH = (Get-Location).Path
uvicorn app.main:app --reload
```

For camera enrollment and ArcFace verification, install the optional biometric runtime as well:

```powershell
pip install -r requirements-face.txt
```

InsightFace includes native dependencies and may require compatible prebuilt wheels or Microsoft C++ Build Tools on Windows. The rest of the API and its tests do not require that optional package.

The API is available at `http://localhost:8000` and OpenAPI docs at `http://localhost:8000/docs`.

### Frontend

In another terminal:

```powershell
cd frontend
Copy-Item .env.example .env
npm install
npm run dev
```

Open `http://localhost:5173`.

## Environment variables

| Variable | Purpose |
| --- | --- |
| `MONGODB_URI` | MongoDB or Atlas connection string |
| `DATABASE_NAME` | Database name |
| `JWT_SECRET` | Long random signing secret |
| `JWT_ALGORITHM` | JWT algorithm, normally `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token lifetime |
| `FACE_MATCH_THRESHOLD` | Calibrated cosine similarity threshold |
| `OFFICE_LATITUDE`, `OFFICE_LONGITUDE` | Authorized office coordinates |
| `OFFICE_RADIUS_METERS` | Geofence radius |
| `CORS_ORIGINS` | Comma-separated frontend origins |
| `VITE_API_URL` | Frontend API base URL |

The face threshold is not universally secure; calibrate it with representative enrollment and verification data for the chosen model and environment.

## First admin and employee registration

With the backend virtual environment active and MongoDB reachable:

```powershell
cd backend
$env:PYTHONPATH = (Get-Location).Path
python scripts/create_admin.py
```

The script prompts for credentials unless `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `ADMIN_NAME`, and `ADMIN_EMPLOYEE_ID` are set in the process environment. The password is hashed with bcrypt.

Sign in as the admin, open **People**, and create an employee. Face enrollment is intentionally admin-only and is available through the API:

```powershell
curl -X POST http://localhost:8000/api/face/register `
  -H "Authorization: Bearer <admin-token>" `
  -H "Content-Type: application/json" `
  -d '{"employee_id":"EMP-001","image":"data:image/jpeg;base64,<frame>"}'
```

The production UI should expose this same endpoint through an admin camera enrollment screen; the API already rejects missing/multiple/low-quality faces and stores only the embedding.

## Attendance flow

1. Employee signs in and receives a short-lived JWT.
2. The browser requests camera access only on the attendance page.
3. The employee captures a frame and a small frame burst.
4. The backend extracts an ArcFace embedding, compares it to the registered embedding, checks liveness movement, then requests and verifies GPS coordinates against the configured Haversine geofence.
5. The unique employee/date index prevents duplicate check-ins.
6. Accepted and rejected decisions are written to separate attendance and audit records.

Location is collected only during the verification action. The application does not continuously track employees.

## Testing

```powershell
cd backend
$env:PYTHONPATH = (Get-Location).Path
pytest -q
```

Frontend production build:

```powershell
cd frontend
npm run build
```

## Troubleshooting

- **MongoDB unavailable:** confirm `MONGODB_URI`, network access, Atlas IP allowlist, and that MongoDB is running. The API still starts for health checks but data endpoints need MongoDB.
- **Camera blocked:** use localhost or HTTPS, allow camera permission, and avoid another application using the camera.
- **Location rejected:** enable high-accuracy location, retry outdoors or near a window, and check `accuracy` against the office radius.
- **Face service unavailable:** install the backend requirements and ensure the machine can download InsightFace model assets on first use. CPU inference is supported but model initialization is intentionally lazy.

## Deployment and security considerations

Deploy the frontend and backend separately, set the deployed frontend origin in `CORS_ORIGINS`, use Atlas TLS, rotate `JWT_SECRET`, and provide secrets through the platform secret manager. Run behind HTTPS, add a managed rate limit/WAF, monitor audit events, restrict MongoDB network access, and use a dedicated service account with least privilege.

Before high-security use, add a presentation-attack detection model, encrypted embedding fields or a managed biometric vault, consent/retention policies, device risk signals, stronger enrollment review, alerting, and independent biometric/privacy review.
