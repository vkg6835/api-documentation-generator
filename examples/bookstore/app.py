from fastapi import FastAPI
from routes import router as book_router

app = FastAPI(title="Bookstore API")
app.include_router(book_router, prefix="/v1")


@app.get("/health")
def health():
    """Report whether the demonstration API process is responding."""
    return {"status": "ok"}
