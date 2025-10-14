# FAANG Validator Backend Service

A FastAPI-based microservice for validating FAANG (Facebook, Amazon, Apple, Netflix, Google) data.

## Features

- Single API endpoint that returns a welcome message
- Containerized with Docker for easy deployment
- Built with FastAPI for high performance and automatic API documentation

## Requirements

- Python 3.9+
- FastAPI
- Uvicorn
- Docker (for containerized deployment)

## Running Locally

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/faang-validator-backend-service.git
   cd faang-validator-backend-service
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Run the application:
   ```
   python app.main.py
   ```

   Alternatively, you can use Uvicorn directly:
   ```
   uvicorn app.main:app --reload
   ```

4. Access the API at http://localhost:8000

## Docker Deployment

1. Build the Docker image:
   ```
   docker build -t faang-validator-api .
   ```

2. Run the container:
   ```
   docker run -p 8000:8000 faang-validator-api
   ```

3. Access the API at http://localhost:8000

## API Documentation

Once the application is running, you can access the automatic API documentation:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API Endpoints

### GET /

Returns a welcome message and status.

**Response Example:**
```json
{
  "message": "Welcome to FAANG Validator API",
  "status": "operational"
}
```
