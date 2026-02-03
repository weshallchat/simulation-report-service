# Simulation & Report Backend Service

A simulation-agnostic backend API service for running simulations and generating reports. The service is designed to be completely agnostic to the type of simulation being run - it handles job management, storage, and API operations while delegating actual simulation/report execution to pluggable handlers.

## Features

- **Simulation Agnostic**: The service doesn't interpret simulation types or parameters - they're passed through to handlers
- **Multi-user Support**: JWT-based authentication with user isolation
- **Async Job Processing**: Long-running simulations are processed asynchronously via Celery workers
- **Hybrid Storage**: PostgreSQL for metadata, S3 (or compatible) for large payloads
- **Plugin Architecture**: Register custom handlers for different simulation and report types
- **Pre-signed URLs**: Secure, time-limited download URLs for reports

## API Endpoints

### Authentication
- `POST /api/v1/auth/register` - Register a new user
- `POST /api/v1/auth/login` - Login and get access token
- `GET /api/v1/auth/me` - Get current user info

### Simulations
- `POST /api/v1/simulations` - Submit a simulation job
- `GET /api/v1/simulations/{job_id}` - Get simulation status/metadata
- `GET /api/v1/simulations/{job_id}/result` - Get simulation result
- `GET /api/v1/simulations` - List simulation jobs
- `POST /api/v1/simulations/{job_id}/cancel` - Cancel a simulation

### Reports
- `POST /api/v1/reports` - Request report generation
- `GET /api/v1/reports/{report_id}` - Get report status and download URL
- `GET /api/v1/reports` - List reports

## Quick Start

### Using Docker Compose (Recommended)

1. Clone the repository and navigate to the project directory:
   ```bash
   cd vibe_coding_round
   ```

2. Copy the environment file:
   ```bash
   cp .env.example .env
   ```

3. Start all services:
   ```bash
   docker-compose up -d
   ```

4. Access the API:
   - API: http://localhost:8000
   - API Documentation: http://localhost:8000/api/v1/docs
   - Celery Flower (monitoring): http://localhost:5555
   - MinIO Console: http://localhost:9001 (minioadmin/minioadmin)

### Local Development

1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. Start PostgreSQL, Redis, and MinIO (or use docker-compose for just these):
   ```bash
   docker-compose up -d postgres redis minio minio-init
   ```

5. Run database migrations:
   ```bash
   alembic upgrade head
   ```

6. Start the API server:
   ```bash
   uvicorn app.main:app --reload
   ```

7. Start Celery workers (in separate terminals):
   ```bash
   # Simulation worker
   celery -A app.workers.celery_app worker --loglevel=info -Q simulations
   
   # Report worker
   celery -A app.workers.celery_app worker --loglevel=info -Q reports
   ```

## Usage Example

### 1. Register a User

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "securepassword123",
    "full_name": "Test User"
  }'
```

### 2. Login

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=user@example.com&password=securepassword123"
```

Save the returned `access_token` for subsequent requests.

### 3. Submit a Simulation

```bash
curl -X POST http://localhost:8000/api/v1/simulations \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "simulation_type": "monte_carlo",
    "parameters": {
      "iterations": 10000,
      "seed": 42,
      "config": {"option1": "value1"}
    },
    "job_metadata": {"project": "test"}
  }'
```

### 4. Check Simulation Status

```bash
curl http://localhost:8000/api/v1/simulations/{job_id} \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### 5. Get Simulation Result

```bash
curl http://localhost:8000/api/v1/simulations/{job_id}/result \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### 6. Generate a Report

```bash
curl -X POST http://localhost:8000/api/v1/reports \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "simulation_job_ids": ["job_id_1", "job_id_2"],
    "report_type": "summary",
    "output_format": "PDF",
    "parameters": {}
  }'
```

### 7. Get Report (with Download URL)

```bash
curl http://localhost:8000/api/v1/reports/{report_id} \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## Implementing Custom Handlers

The service uses a plugin architecture for simulation and report handlers. To add support for a specific simulation type:

### Simulation Handler

```python
from app.handlers import SimulationHandler, SimulationHandlerRegistry

class MonteCarloHandler(SimulationHandler):
    def execute(self, job_id, simulation_type, parameters, progress_callback=None):
        # Your simulation logic here
        result = run_monte_carlo_simulation(parameters)
        
        # Report progress if callback provided
        if progress_callback:
            progress_callback(0.5)  # 50% complete
        
        return {
            "output": result,
            "statistics": calculate_stats(result)
        }

# Register the handler (typically in app startup)
SimulationHandlerRegistry.register("monte_carlo", MonteCarloHandler())
```

### Report Handler

```python
from app.handlers import ReportHandler, ReportHandlerRegistry

class SummaryReportHandler(ReportHandler):
    def generate(self, report_id, report_type, output_format, parameters, simulation_results):
        # Generate report from simulation results
        if output_format == "PDF":
            content = generate_pdf(simulation_results)
            return content, "application/pdf", "report.pdf"
        else:
            content = generate_json(simulation_results)
            return content, "application/json", "report.json"

# Register the handler
ReportHandlerRegistry.register("summary", SummaryReportHandler())
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         API Layer (FastAPI)                     │
│  POST /simulations  GET /simulations/{id}                       │
│  GET /simulations/{id}/result                                   │
│  POST /reports      GET /reports/{id}                           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Service Layer                              │
│   SimulationService (agnostic)    ReportService (agnostic)      │
└─────────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  Celery + Redis │  │   PostgreSQL    │  │   S3 / MinIO    │
│  (Async Jobs)   │  │   (Metadata)    │  │   (Blobs)       │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

## Configuration

See `.env.example` for all configuration options. Key settings:

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://...` |
| `S3_BUCKET_NAME` | S3 bucket for blob storage | `simulation-data` |
| `S3_ENDPOINT_URL` | Custom S3 endpoint (for MinIO) | None |
| `PARAMETERS_SIZE_THRESHOLD` | Threshold for storing in S3 vs DB | 100KB |
| `SECRET_KEY` | JWT signing key | (required) |

## Running Tests

```bash
pytest tests/ -v
```

## License

MIT License
