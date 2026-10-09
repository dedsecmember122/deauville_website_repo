# Deauville Festival du Rire

    uv sync
    uv run python main.py      # starts the server and opens http://127.0.0.1:8000

Files: `festival.py` (classes + rules), `api.py` (FastAPI routes), `main.py` (launcher),
`web/public/index.html` (frontend), `data/festival.json` (data, saved on every change).
API docs: http://127.0.0.1:8000/docs

## Concepts to learn (and where)
- JSON -> dict/list: `Festival.__init__`
- dataclass, @property, __post_init__-style checks: `Venue`, `Artist`, `Performance.end`
- Inheritance + polymorphism (no `if kind ==`): `Solo`, `Lineup`, `Workshop` override `artist_slugs`/`extra`
- Special methods: `__lt__` (sorting), `__eq__` (same artist = same slug)
- datetime/timedelta: festival day = start minus 6h
- Encapsulation: `_performances`, getters return copies, only `add/cancel/register` write
- Custom exceptions: `FestivalError` -> `NotFound`/`Conflict`/`Invalid`
- FastAPI: routes, pydantic bodies, one exception handler (404/409/422), StaticFiles
- fetch() in JavaScript calling the API
