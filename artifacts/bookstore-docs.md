# Bookstore API

Generated from supplied Python source and usage examples. Descriptions are drafts for review.

Endpoints: 6 · Schemas: 2

## GET `/health`

Report whether the demonstration API process is responding.

Report whether the demonstration API process is responding.

Source: `app.py` lines 9–11 · `SRC-66e3a3d2db`

| Parameter | Location | Type | Required |
|---|---|---|---|

### Responses

- 200: Declared success response

### Usage: Check whether the API process responds

```http
EX-health | Check whether the API process responds
GET http://localhost:8001/health
```
Example source: `requests.http` · `EX-health`

## GET `/v1/books`

List books up to the requested result limit.

List books up to the requested result limit.

Source: `routes.py` lines 9–11 · `SRC-816869edf3`

| Parameter | Location | Type | Required |
|---|---|---|---|
| limit | query | int | No |

### Responses

- 200: Declared success response

### Usage: List the catalog with a result limit

```http
EX-books-list | List the catalog with a result limit
GET http://localhost:8001/v1/books?limit=5
```
Example source: `requests.http` · `EX-books-list`

## POST `/v1/books`

Create a book in the in-memory catalog.

The POST /v1/books endpoint creates a new book in the in-memory catalog. The book is saved in the `BOOKS` dictionary with the id of the book as the key and a dictionary representing the book as its value. The response contains a 201 status code and a JSON response describing the created book.

Source: `routes.py` lines 15–20 · `SRC-3410d789d1`

| Parameter | Location | Type | Required |
|---|---|---|---|
| book | body | BookCreate | Yes |

### Responses

- 201: Declared success response

### Usage: Add a book to the catalog

```http
EX-books-create | Add a book to the catalog
POST http://localhost:8001/v1/books
Content-Type: application/json

{"title":"The Pragmatic Programmer","author":"Andrew Hunt","price":499,"published":true}
```
Example source: `requests.http` · `EX-books-create`

Evidence: SRC-3410d789d1, SRC-022ad8ac01, SRC-dfb2e6e320

Limitations: The book title must be between 1 and 120 characters.

## GET `/v1/books/{book_id}`

Find a book by its numeric identifier.

Find a book by its numeric identifier.

Source: `routes.py` lines 24–28 · `SRC-1b670bedf3`

| Parameter | Location | Type | Required |
|---|---|---|---|
| book_id | path | int | Yes |

### Responses

- 200: Declared success response
- 404: Book not found

### Usage: Find one book by its identifier

```http
EX-books-get | Find one book by its identifier
GET http://localhost:8001/v1/books/1
```
Example source: `requests.http` · `EX-books-get`

## PUT `/v1/books/{book_id}`

Replace the editable fields of an existing book.

Replace the editable fields of an existing book.

Source: `routes.py` lines 32–37 · `SRC-820982fe82`

| Parameter | Location | Type | Required |
|---|---|---|---|
| book_id | path | int | Yes |
| book | body | BookCreate | Yes |

### Responses

- 200: Declared success response
- 404: Book not found

### Usage: Replace a book's editable fields

```http
EX-books-update | Replace a book's editable fields
PUT http://localhost:8001/v1/books/1
Content-Type: application/json

{"title":"The Pragmatic Programmer","author":"Andrew Hunt","price":450,"published":true}
```
Example source: `requests.http` · `EX-books-update`

## DELETE `/v1/books/{book_id}`

Remove an existing book from the catalog.

Remove an existing book from the catalog.

Source: `routes.py` lines 41–45 · `SRC-e85158678b`

| Parameter | Location | Type | Required |
|---|---|---|---|
| book_id | path | int | Yes |

### Responses

- 204: Declared success response
- 404: Book not found

### Usage: Remove a book from the catalog

```http
EX-books-delete | Remove a book from the catalog
DELETE http://localhost:8001/v1/books/1
```
Example source: `requests.http` · `EX-books-delete`

## Schemas

```json
{
  "BookCreate": {
    "type": "object",
    "properties": {
      "title": {
        "type": "string",
        "minLength": 1,
        "maxLength": 120
      },
      "author": {
        "type": "string"
      },
      "price": {
        "type": "number",
        "minimum": 0
      },
      "published": {
        "type": "boolean",
        "default": false
      }
    },
    "required": [
      "title",
      "author",
      "price"
    ]
  },
  "Book": {
    "type": "object",
    "properties": {
      "id": {
        "type": "integer"
      },
      "title": {
        "type": "string"
      },
      "author": {
        "type": "string"
      },
      "price": {
        "type": "number"
      },
      "published": {
        "type": "boolean",
        "default": false
      }
    },
    "required": [
      "id",
      "title",
      "author",
      "price"
    ]
  }
}
```

## Analysis notes

- No static-analysis warnings.