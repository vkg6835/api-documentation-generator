from pydantic import BaseModel, Field


class BookCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)
    author: str
    price: float = Field(..., ge=0)
    published: bool = False


class Book(BaseModel):
    id: int
    title: str
    author: str
    price: float
    published: bool = False
