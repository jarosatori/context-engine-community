"""Pydantic models for Context Engine input validation."""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class Domain(str, Enum):
    work = "work"
    personal = "personal"
    home = "home"
    health = "health"
    finance = "finance"
    family = "family"
    education = "education"
    other = "other"


class Status(str, Enum):
    active = "active"
    inactive = "inactive"
    to_verify = "to_verify"


class Formality(str, Enum):
    ty = "ty"
    vy = "vy"
    uncertain = "uncertain"


class Tone(str, Enum):
    formalny = "formalny"
    priatelsky = "priatelsky"
    vecny = "vecny"
    neformlny = "neformlny"


class Priority(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class RelationshipType(str, Enum):
    klient = "klient"
    partner = "partner"
    tim = "tim"
    vendor = "vendor"
    kontakt = "kontakt"
    mentor = "mentor"
    rodina = "rodina"
    priatel = "priatel"


class CompanyType(str, Enum):
    vlastna = "vlastna"
    klient = "klient"
    partner = "partner"
    vendor = "vendor"
    ina = "ina"


class ProjectType(str, Enum):
    produkt = "produkt"
    kampan = "kampan"
    interni = "interni"
    klientsky = "klientsky"
    strategia = "strategia"
    osobny = "osobny"


class ProjectStatus(str, Enum):
    active = "active"
    paused = "paused"
    done = "done"
    cancelled = "cancelled"
    to_verify = "to_verify"


class Channel(str, Enum):
    email = "email"
    slack = "slack"
    asana = "asana"
    call = "call"
    meeting = "meeting"
    sms = "sms"
    other = "other"


class Direction(str, Enum):
    incoming = "incoming"
    outgoing = "outgoing"
    both = "both"


# --- Input models ---

class PersonInput(BaseModel):
    name: str = Field(..., description="Meno a priezvisko")
    email: Optional[str] = None
    phone: Optional[str] = None
    company_id: Optional[int] = None
    company_name: Optional[str] = None
    role: Optional[str] = None
    relationship: Optional[str] = None
    formality: Optional[str] = Field(default="uncertain")
    tone: Optional[str] = None
    language: Optional[str] = Field(default="sk")
    projects: Optional[str] = Field(default=None, description="JSON array of project names")
    notes: Optional[str] = None
    status: Optional[str] = Field(default="active")
    source: Optional[str] = None
    domain: Optional[str] = Field(default="work")


class CompanyInput(BaseModel):
    name: str = Field(..., description="Nazov firmy")
    type: Optional[str] = None
    industry: Optional[str] = None
    my_role: Optional[str] = None
    website: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = Field(default="active")
    domain: Optional[str] = Field(default="work")


class ProjectInput(BaseModel):
    name: str = Field(..., description="Nazov projektu")
    company_id: Optional[int] = None
    company_name: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = None
    status: Optional[str] = Field(default="active")
    team: Optional[str] = Field(default=None, description="JSON array of person names")
    my_role: Optional[str] = None
    asana_id: Optional[str] = None
    slack_channel: Optional[str] = None
    drive_folder: Optional[str] = None
    key_contacts: Optional[str] = Field(default=None, description="JSON array")
    notes: Optional[str] = None
    deadline: Optional[str] = None
    domain: Optional[str] = Field(default="work")


class ProductInput(BaseModel):
    name: str = Field(..., description="Nazov produktu/sluzby")
    company_id: Optional[int] = None
    company_name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[str] = None
    format: Optional[str] = None
    availability: Optional[str] = None
    target_audience: Optional[str] = None
    min_criteria: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = Field(default="active")
    domain: Optional[str] = Field(default="work")


class RuleInput(BaseModel):
    context: str = Field(..., description="Kedy pravidlo plati")
    rule: str = Field(..., description="Co robit")
    example: Optional[str] = None
    priority: Optional[str] = Field(default="medium")
    category: Optional[str] = None
    applies_to: Optional[str] = Field(default=None, description="JSON: company/person/project names")
    notes: Optional[str] = None
    status: Optional[str] = Field(default="active")
    domain: Optional[str] = Field(default="work")


class InteractionInput(BaseModel):
    person_id: Optional[int] = None
    person_name: Optional[str] = None
    channel: Optional[str] = None
    direction: Optional[str] = None
    summary: Optional[str] = None
    context: Optional[str] = None
    date: Optional[str] = None
    source_ref: Optional[str] = None
    domain: Optional[str] = Field(default="work")


class NoteInput(BaseModel):
    title: str = Field(..., description="Nazov/nadpis poznamky")
    content: Optional[str] = Field(default=None, description="Obsah — volny text alebo markdown")
    domain: Optional[str] = Field(default="personal")
    category: Optional[str] = Field(default=None, description="Kategoria: health, finance, recipe, idea, reference...")
    tags: Optional[str] = Field(default=None, description="JSON array tagov")
    related_person_id: Optional[int] = None
    related_project_id: Optional[int] = None
    source: Optional[str] = None
    status: Optional[str] = Field(default="active")


class UpdateInput(BaseModel):
    table: str = Field(..., description="Tabulka: people, companies, projects, products, rules, notes")
    record_id: int = Field(..., description="ID zaznamu")
    data: dict = Field(..., description="Polia na aktualizaciu")
