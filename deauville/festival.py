"""Domain model: classes + rules. No web code here."""
import json
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

GAP = timedelta(minutes=30)


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return "-".join(text.lower().split())


class FestivalError(Exception): ...
class NotFound(FestivalError): ...
class Conflict(FestivalError): ...
class Invalid(FestivalError): ...


@dataclass
class Venue:
    name: str
    capacity: int
    address: str

    @property
    def slug(self):
        return slugify(self.name)

    def to_view(self):
        return {"slug": self.slug, "name": self.name,
                "capacity": self.capacity, "address": self.address}


@dataclass
class Artist:
    name: str
    bio: str = ""
    photo_url: str = ""

    @property
    def slug(self):
        return slugify(self.name)

    def __eq__(self, other):
        return isinstance(other, Artist) and self.slug == other.slug

    def to_view(self):
        return {"slug": self.slug, "name": self.name,
                "bio": self.bio, "photo_url": self.photo_url}


@dataclass
class Performance:
    """Base of the family: solo, lineup, workshop override the 3 hooks."""
    title: str
    venue: str
    start: datetime
    duration_minutes: int
    description: str = ""
    kind = "performance"

    @property
    def end(self):
        return self.start + timedelta(minutes=self.duration_minutes)

    @property
    def festival_day(self):  # a show at 01:00 belongs to the previous day
        return (self.start - timedelta(hours=6)).date()

    @property
    def id(self):
        return f"{self.venue}-{self.start:%Y-%m-%d-%H%M}"

    def artist_slugs(self) -> list[str]:
        return []

    def summary(self) -> str:
        return ""

    def extra(self) -> dict:
        return {}

    def to_data(self):
        return {"kind": self.kind, "title": self.title, "venue": self.venue,
                "start": f"{self.start:%Y-%m-%dT%H:%M}",
                "duration_minutes": self.duration_minutes,
                "description": self.description, **self.extra()}

    def __lt__(self, other):
        return (self.start, self.venue) < (other.start, other.venue)


@dataclass
class Solo(Performance):
    artist: str = ""
    min_age: int = 0
    kind = "solo"

    def artist_slugs(self):
        return [self.artist]

    def extra(self):
        return {"artist": self.artist, "min_age": self.min_age}


@dataclass
class Lineup(Performance):
    host: str = ""
    acts: list[str] = field(default_factory=list)
    kind = "lineup"

    def artist_slugs(self):
        return [self.host, *self.acts]

    def extra(self):
        return {"host": self.host, "acts": list(self.acts)}


@dataclass
class Workshop(Performance):
    teacher: str = ""
    max_participants: int = 10
    participants: list[str] = field(default_factory=list)
    kind = "workshop"

    def artist_slugs(self):
        return [self.teacher]

    def extra(self):
        return {"teacher": self.teacher, "max_participants": self.max_participants,
                "participants": list(self.participants)}


KINDS = {"solo": Solo, "lineup": Lineup, "workshop": Workshop}


class Festival:
    def __init__(self, path="data/festival.json"):
        self._path = Path(path)
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        self.name = raw["name"]
        self.first_day = date.fromisoformat(raw["first_day"])
        self.last_day = date.fromisoformat(raw["last_day"])
        self._venues = [Venue(**v) for v in raw["venues"]]
        self._artists = [Artist(**a) for a in raw["artists"]]
        self._performances: list[Performance] = []
        for p in raw["performances"]:
            p = dict(p)
            p["start"] = datetime.fromisoformat(p["start"])
            self._performances.append(KINDS[p.pop("kind")](**p))

    # ---- reading (copies only: nobody bypasses the rules) ----
    @property
    def days(self):
        n = (self.last_day - self.first_day).days
        return [self.first_day + timedelta(days=i) for i in range(n + 1)]

    @property
    def venues(self):
        return list(self._venues)

    @property
    def artists(self):
        return sorted(self._artists, key=lambda a: a.slug)

    def venue(self, slug):
        for v in self._venues:
            if v.slug == slug:
                return v
        raise NotFound(f"No venue '{slug}'.")

    def artist(self, slug):
        for a in self._artists:
            if a.slug == slug:
                return a
        raise NotFound(f"No artist '{slug}'.")

    def performance(self, pid):
        for p in self._performances:
            if p.id == pid:
                return p
        raise NotFound(f"No performance '{pid}'.")

    def programme(self, day=None, venue=None):
        if venue:
            self.venue(venue)
        return sorted(p for p in self._performances
                      if (day is None or p.festival_day == day)
                      and (venue is None or p.venue == venue))

    def of_artist(self, slug):
        self.artist(slug)
        return sorted(p for p in self._performances if slug in p.artist_slugs())

    def now(self, at: datetime):
        playing = [p for p in self.programme() if p.start <= at < p.end]
        later = [p for p in self.programme() if p.start > at]
        return playing, later[:3]

    # ---- writing: every rule lives here ----
    def add(self, kind, **data):
        if kind not in KINDS:
            raise Invalid(f"Unknown kind '{kind}'.")
        try:
            data["start"] = datetime.fromisoformat(data["start"])
            perf = KINDS[kind](**data)
        except (KeyError, TypeError, ValueError) as e:
            raise Invalid(f"Invalid performance: {e}") from e
        self._check(perf)
        self._performances.append(perf)
        self.save()
        return perf

    def _check(self, perf, ignore=None):
        venue = self.venue(perf.venue)
        for slug in perf.artist_slugs():
            self.artist(slug)
        if not 1 <= perf.duration_minutes <= 360:
            raise Invalid("Duration must be between 1 and 360 minutes.")
        if not self.first_day <= perf.festival_day <= self.last_day:
            raise Invalid(f"{perf.festival_day} is outside the festival.")
        if isinstance(perf, Lineup) and len(perf.acts) < 2:
            raise Invalid("A lineup needs at least two acts.")
        if isinstance(perf, Workshop) and len(perf.participants) > perf.max_participants:
            raise Invalid("Too many participants.")
        if any(slug_count > 1 for slug_count in
               (perf.artist_slugs().count(s) for s in perf.artist_slugs())):
            raise Invalid("An artist appears twice in the same show.")
        for o in self._performances:
            if o is ignore:
                continue
            close = perf.start < o.end + GAP and o.start < perf.end + GAP
            if close and o.venue == perf.venue:
                raise Conflict(f"{venue.name} is busy with {o.title}.")
            if close:
                for s in set(perf.artist_slugs()) & set(o.artist_slugs()):
                    raise Conflict(f"{self.artist(s).name} is on stage ({o.title}).")

    def cancel(self, pid):
        self._performances.remove(self.performance(pid))
        self.save()

    def register(self, pid, name):
        p = self.performance(pid)
        if not isinstance(p, Workshop):
            raise Invalid("Only workshops take participants.")
        name = name.strip()
        if not name:
            raise Invalid("Name is empty.")
        if name.lower() in (x.lower() for x in p.participants):
            raise Conflict(f"{name} is already registered.")
        if len(p.participants) >= p.max_participants:
            raise Conflict("This workshop is full.")
        p.participants.append(name)
        self.save()
        return p

    def add_artist(self, name, bio=""):
        a = Artist(name.strip(), bio)
        if not a.name:
            raise Invalid("Name is empty.")
        if a in self._artists:
            raise Conflict(f"Artist '{a.name}' already exists.")
        self._artists.append(a)
        self.save()
        return a

    # ---- views ----
    def view(self, p: Performance):
        arts = [{"slug": s, "name": self.artist(s).name} for s in p.artist_slugs()]
        out = {**p.to_data(), "id": p.id, "venue_name": self.venue(p.venue).name,
               "end": f"{p.end:%Y-%m-%dT%H:%M}", "festival_day": str(p.festival_day),
               "capacity": self.venue(p.venue).capacity, "artists": arts}
        if isinstance(p, Workshop):
            out["places_left"] = p.max_participants - len(p.participants)
        return out

    def save(self):
        data = {"name": self.name, "first_day": str(self.first_day),
                "last_day": str(self.last_day),
                "venues": [{"name": v.name, "capacity": v.capacity, "address": v.address}
                           for v in self._venues],
                "artists": [{"name": a.name, "bio": a.bio, "photo_url": a.photo_url}
                            for a in self._artists],
                "performances": [p.to_data() for p in sorted(self._performances)]}
        self._path.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                              encoding="utf-8")
