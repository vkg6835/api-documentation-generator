from fastapi import APIRouter, HTTPException, Query
from models import Book, BookCreate

router = APIRouter(prefix="/books")
BOOKS = {}


@router.get("", response_model=list[Book])
def list_books(limit: int = Query(10, ge=1, le=50)):
    """List books up to the requested result limit."""
    return list(BOOKS.values())[:limit]


@router.post("", response_model=Book, status_code=201)
def create_book(book: BookCreate):
    """Create a book in the in-memory catalog."""
    book_id = max(BOOKS, default=0) + 1
    saved = {"id": book_id, **book.model_dump()}
    BOOKS[book_id] = saved
    return saved


@router.get("/{book_id}", response_model=Book)
def get_book(book_id: int):
    """Find a book by its numeric identifier."""
    if book_id not in BOOKS:
        raise HTTPException(status_code=404, detail="Book not found")
    return BOOKS[book_id]


@router.put("/{book_id}", response_model=Book)
def update_book(book_id: int, book: BookCreate):
    """Replace the editable fields of an existing book."""
    if book_id not in BOOKS:
        raise HTTPException(status_code=404, detail="Book not found")
    BOOKS[book_id] = {"id": book_id, **book.model_dump()}
    return BOOKS[book_id]


@router.delete("/{book_id}", status_code=204)
def delete_book(book_id: int):
    """Remove an existing book from the catalog."""
    if book_id not in BOOKS:
        raise HTTPException(status_code=404, detail="Book not found")
    del BOOKS[book_id]
