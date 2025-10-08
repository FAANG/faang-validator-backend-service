from fastapi import FastAPI

app = FastAPI(
    title="FAANG Validator API",
    description="API for validating FAANG data",
    version="0.1.0"
)

@app.get("/")
async def root():
    """
    Root endpoint that returns a welcome message.
    """
    return {
        "message": "Welcome to FAANG Validator API",
        "status": "operational"
    }

