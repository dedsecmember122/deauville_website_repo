from datetime import date, datetime

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from festival import Conflict, Festival, FestivalError, NotFound

app = FastAPI(title="Deauville Festival du Rire")
fest = Festival("data/festival.json")


@app.exception_handler(FestivalError)
def on_error(_, exc: FestivalError):
    code = 404 if isinstance(exc, NotFound) else 409 if isinstance(exc, Conflict) else 422
    return JSONResponse({"detail": str(exc)}, status_code=code)


@app.get("/api/festival")
def festival():
    return {"name": fest.name, "first_day": str(fest.first_day),
            "last_day": str(fest.last_day), "days": [str(d) for d in fest.days]}


@app.get("/api/venues")
def venues():
    return [v.to_view() for v in fest.venues]


@app.get("/api/artists")
def artists():
    return [a.to_view() for a in fest.artists]


@app.get("/api/artists/{slug}")
def artist(slug: str):
    return {**fest.artist(slug).to_view(),
            "performances": [fest.view(p) for p in fest.of_artist(slug)]}


@app.get("/api/programme")
def programme(day: date | None = None, venue: str | None = None):
    return [fest.view(p) for p in fest.programme(day, venue)]


@app.get("/api/performances/{pid}")
def performance(pid: str):
    return fest.view(fest.performance(pid))


@app.get("/api/now")
def now(at: datetime | None = None):
    playing, later = fest.now(at or datetime.now())
    return {"now_playing": [fest.view(p) for p in playing],
            "up_next": [fest.view(p) for p in later]}


class NewPerformance(BaseModel):
    kind: str
    title: str
    venue: str
    start: str
    duration_minutes: int
    description: str = ""
    artist: str | None = None
    host: str | None = None
    acts: list[str] | None = None
    teacher: str | None = None
    max_participants: int | None = None


@app.post("/api/performances", status_code=201)
def add_performance(body: NewPerformance):
    data = body.model_dump(exclude_none=True)
    return fest.view(fest.add(data.pop("kind"), **data))


@app.delete("/api/performances/{pid}", status_code=204)
def cancel(pid: str):
    fest.cancel(pid)


class Person(BaseModel):
    name: str


@app.post("/api/performances/{pid}/participants")
def register(pid: str, body: Person):
    return fest.view(fest.register(pid, body.name))


@app.post("/api/artists", status_code=201)
def new_artist(body: Person):
    return fest.add_artist(body.name).to_view()


app.mount("/", StaticFiles(directory="web/public", html=True))
