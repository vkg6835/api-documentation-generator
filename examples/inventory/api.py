from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="Inventory API")
ITEMS = {}


class ItemCreate(BaseModel):
    sku: str = Field(..., min_length=1, max_length=40)
    quantity: int = Field(..., ge=0)
    warehouse: str = "Surat"


@app.post("/api/items", response_model=ItemCreate, status_code=201)
def create_item(item: ItemCreate):
    """Add a stock item to the in-memory inventory; reject a duplicate SKU."""
    if item.sku in ITEMS:
        raise HTTPException(status_code=409, detail="SKU already exists")
    saved = item.model_dump()
    ITEMS[item.sku] = saved
    return saved


@app.get("/api/items/{sku}", response_model=ItemCreate)
def get_item(sku: str):
    """Return a stock item by SKU, or report that the SKU is missing."""
    if sku not in ITEMS:
        raise HTTPException(status_code=404, detail="SKU not found")
    return ITEMS[sku]
