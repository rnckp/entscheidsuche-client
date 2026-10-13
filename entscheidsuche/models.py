"""
Data models for the entscheidsuche.ch API.
"""

from dataclasses import field
from datetime import datetime
from pathlib import PurePosixPath
from typing import Any, Literal
from urllib.parse import unquote

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationInfo, field_validator
from pydantic.dataclasses import dataclass

from .config import DEFAULT_CONFIG, EntscheidsucheConfig
from .paths import document_url, quote_segment, validate_document_path, validate_identifier

_MODEL_CONFIG = ConfigDict(strict=True, hide_input_in_errors=True)
_JSON_OBJECT = TypeAdapter(dict[str, Any], config=_MODEL_CONFIG)
_JSON_OBJECTS = TypeAdapter(list[dict[str, Any]], config=_MODEL_CONFIG)


class FacetNode(BaseModel):
    """Live labels and source mappings, keyed by hierarchy IDs."""

    model_config = ConfigDict(strict=True, extra="allow", hide_input_in_errors=True)
    de: str | None = None
    fr: str | None = None
    it: str | None = None
    en: str | None = None
    spider: str | None = None
    gerichte: dict[str, "FacetNode"] = Field(default_factory=dict)
    kammern: dict[str, "FacetNode"] = Field(default_factory=dict)


class FileStatus(BaseModel):
    """Status and provenance for one file in a Jobs response."""

    model_config = ConfigDict(strict=True, extra="allow", hide_input_in_errors=True)
    status: str
    checksum: str | None = None
    last_change: str | None = None
    scrapedate: str | None = None


class ShardInfo(BaseModel):
    """Shard execution details retained from a search response."""

    model_config = ConfigDict(strict=True, extra="allow", hide_input_in_errors=True)
    total: int = Field(default=0, ge=0)
    successful: int = Field(default=0, ge=0)
    skipped: int = Field(default=0, ge=0)
    failed: int = Field(default=0, ge=0)
    failures: list[dict[str, Any]] = Field(default_factory=list)


class _SearchSource(BaseModel):
    """Validate the source fields used by public hit properties."""

    model_config = ConfigDict(strict=True, extra="allow", hide_input_in_errors=True)
    hierarchy: list[str] = Field(default_factory=list)
    title: dict[str, str] = Field(default_factory=dict)
    abstract: dict[str, str] = Field(default_factory=dict)
    meta: dict[str, str] = Field(default_factory=dict)
    attachment: dict[str, Any] = Field(default_factory=dict)
    id: str | None = None
    Signatur: str | None = None
    Spider: str | None = None
    date: str | None = None
    Datum: str | None = None
    Sprache: str | None = None
    scrapedate: str | None = None
    reference: str | list[str] | None = None

    @field_validator("hierarchy", "title", "abstract", "meta", "attachment", mode="before")
    @classmethod
    def normalize_null(cls, value: Any, info: ValidationInfo) -> Any:
        """Treat null optional collections as absent."""
        if value is None:
            return [] if info.field_name == "hierarchy" else {}
        return value

    @field_validator("attachment")
    @classmethod
    def validate_attachment(cls, value: dict[str, Any]) -> dict[str, Any]:
        """Constrain the attachment values exposed by properties."""
        for key in ("language", "content_url"):
            if value.get(key) is not None and not isinstance(value[key], str):
                raise ValueError(f"attachment.{key} must be a string or null")
        return value


def _file_identity(path: str) -> tuple[str, str]:
    """Validate a scraper-relative path and return document ID and format."""
    validate_document_path(path)
    parts = unquote(path).split("/")
    if len(parts) != 2:
        raise ValueError("File paths must contain a scraper directory and filename")
    filename = PurePosixPath(parts[1])
    format_ = filename.suffix.removeprefix(".")
    if format_ not in {"json", "html", "pdf"}:
        raise ValueError("Unsupported document file format")
    return validate_identifier(filename.stem, "document ID"), format_


class _Summary(BaseModel):
    """Collection count with open-ended status counters."""

    model_config = ConfigDict(strict=True, extra="allow", hide_input_in_errors=True)
    gesamt: int = Field(ge=0)


class _IndexPayload(BaseModel):
    """Current Index action and summary layout."""

    model_config = ConfigDict(strict=True, extra="allow", hide_input_in_errors=True)
    actions: dict[str, Literal["new", "update", "delete"]]
    signaturen: dict[str, _Summary] = Field(default_factory=dict)
    gesamt: _Summary | None = None


def _text_by_language(value: Any) -> dict[str, str]:
    """Normalize entscheidsuche multilingual text shapes into lang -> text."""
    if isinstance(value, dict):
        return {str(language): str(text) for language, text in value.items()}

    result: dict[str, str] = {}
    if isinstance(value, list):
        for item in value:
            if not isinstance(item, dict):
                continue
            text = item.get("Text")
            languages = item.get("Sprachen", [])
            if isinstance(languages, str):
                languages = [languages]
            if text is None or not isinstance(languages, list):
                continue
            for language in languages:
                result[str(language)] = str(text)
        return result

    if isinstance(value, str):
        return {"de": value}
    return result


def _document_path(value: Any) -> str | None:
    """Extract the relative docs path from live HTML/PDF metadata objects."""
    if isinstance(value, dict):
        path = value.get("Datei")
        return str(path) if path else None
    if isinstance(value, str):
        return value
    return None


def _source_url(value: Any) -> str | None:
    if isinstance(value, dict):
        url = value.get("URL")
        return str(url) if url else None
    return None


def _document_id_from_path(path: str | None) -> str | None:
    if not path:
        return None
    return PurePosixPath(path).stem


@dataclass(config=_MODEL_CONFIG)
class ScraperInfo:
    """Information about a scraper/spider."""

    name: str
    document_count: int
    new_count: int
    last_update: datetime | None
    status: str  # "komplett", "update", "neu", etc.

    @classmethod
    def from_status_line(cls, name: str, line: str) -> "ScraperInfo":
        """Return placeholder counts and unknown status; line is not parsed."""
        return cls(
            name=name,
            document_count=0,
            new_count=0,
            last_update=None,
            status="unknown",
        )


@dataclass(config=_MODEL_CONFIG)
class CaseDocument:
    """A legal case document from entscheidsuche.ch."""

    signatur: str
    spider: str
    language: str
    date: str
    html_path: str | None = None
    pdf_path: str | None = None
    url: str | None = None
    document_id: str | None = None
    num: list[str] = field(default_factory=list)
    kopfzeile: dict[str, str] = field(default_factory=dict)
    meta: dict[str, str] = field(default_factory=dict)
    abstract: dict[str, str] = field(default_factory=dict)
    checksum: str | None = None
    time_utc: str | None = None
    docs_url: str = DEFAULT_CONFIG.docs_url

    @classmethod
    def from_json(
        cls,
        data: dict[str, Any],
        document_id: str | None = None,
        docs_url: str = DEFAULT_CONFIG.docs_url,
    ) -> "CaseDocument":
        """Create a CaseDocument from JSON data."""
        data = _JSON_OBJECT.validate_python(data)
        kopfzeile = _text_by_language(data.get("Kopfzeile"))
        meta = _text_by_language(data.get("Meta"))
        abstract = _text_by_language(data.get("Abstract"))

        for key, value in data.items():
            if key != "Kopfzeile" and key.startswith("Kopfzeile"):
                lang_key = key.replace("Kopfzeile", "").lower() or "de"
                kopfzeile[lang_key] = str(value)
            elif key != "Meta" and key.startswith("Meta"):
                lang_key = key.replace("Meta", "").lower() or "de"
                meta[lang_key] = str(value)
            elif key != "Abstract" and key.startswith("Abstract"):
                lang_key = key.replace("Abstract", "").lower() or "de"
                abstract[lang_key] = str(value)

        num = data.get("Num", [])
        if isinstance(num, str):
            num = [num]
        elif isinstance(num, dict):
            num = [str(value) for value in num.values()]
        elif isinstance(num, list):
            num = [str(value) for value in num]
        else:
            num = []

        html_path = _document_path(data.get("HTML"))
        pdf_path = _document_path(data.get("PDF"))
        resolved_document_id = (
            document_id
            or _document_id_from_path(html_path)
            or _document_id_from_path(pdf_path)
            or data.get("id")
        )
        source_url = (
            data.get("URL") or _source_url(data.get("HTML")) or _source_url(data.get("PDF"))
        )

        return cls(
            docs_url=docs_url,
            signatur=data.get("Signatur", ""),
            spider=data.get("Spider", ""),
            language=data.get("Sprache", "de"),
            date=data.get("Datum", ""),
            html_path=html_path,
            pdf_path=pdf_path,
            url=str(source_url) if source_url else None,
            document_id=str(resolved_document_id) if resolved_document_id else None,
            num=num,
            kopfzeile=kopfzeile,
            meta=meta,
            abstract=abstract,
            checksum=data.get("Checksum", None),
            time_utc=data.get("Zeit UTC", None),
        )

    def __post_init__(self) -> None:
        """Normalize and validate the endpoint carried by this document."""
        self.docs_url = EntscheidsucheConfig(docs_url=self.docs_url).docs_url.rstrip("/")

    @property
    def html_url(self) -> str | None:
        """Get full URL for HTML document."""
        if self.html_path:
            return document_url(self.docs_url, self.html_path)
        return None

    @property
    def pdf_url(self) -> str | None:
        """Get full URL for PDF document."""
        if self.pdf_path:
            return document_url(self.docs_url, self.pdf_path)
        return None

    @property
    def json_url(self) -> str:
        """Get URL for the JSON metadata file."""
        document_id = self.document_id or self.signatur
        validate_identifier(document_id, "document ID")
        return document_url(self.docs_url, f"{quote_segment(document_id)}.json")


@dataclass(config=_MODEL_CONFIG)
class IndexFile:
    """Index file containing document updates for a scraper run."""

    jobtyp: str  # "komplett", "unvollständig", "neu", "update"
    time: str
    scraper: str
    total_count: int
    new_documents: list[str] = field(default_factory=list)
    updated_documents: list[str] = field(default_factory=list)
    deleted_documents: list[str] = field(default_factory=list)

    job: str | None = None
    start_time: str | None = None
    actions: dict[str, Literal["new", "update", "delete"]] = field(default_factory=dict)

    @classmethod
    def from_json(cls, data: dict[str, Any], scraper: str) -> "IndexFile":
        """Parse action paths into document IDs while retaining the checkpoint."""
        data = _JSON_OBJECT.validate_python(data)
        payload = _IndexPayload.model_validate(data)
        changes: dict[str, list[str]] = {"new": [], "update": [], "delete": []}
        for path, action in payload.actions.items():
            document_id, format_ = _file_identity(path)
            if format_ != "json":
                raise ValueError("Index actions must reference JSON metadata")
            changes[action].append(document_id)
        total = (
            payload.gesamt.gesamt
            if payload.gesamt is not None
            else sum(summary.gesamt for summary in payload.signaturen.values())
        )
        return cls(
            jobtyp=data.get("jobtyp", "unknown"),
            time=data.get("time", ""),
            scraper=scraper,
            total_count=total,
            new_documents=changes["new"],
            updated_documents=changes["update"],
            deleted_documents=changes["delete"],
            actions=payload.actions,
            job=data.get("job"),
            start_time=data.get("start_time"),
        )


@dataclass(config=_MODEL_CONFIG)
class JobsFile:
    """Per-file statuses and document IDs aggregated from a Jobs response."""

    jobtyp: str
    time: str
    scraper: str
    documents: dict[str, dict[str, FileStatus]] = field(default_factory=dict)
    files: dict[str, FileStatus] = field(default_factory=dict)
    job: str | None = None
    start_time: str | None = None
    lastjob: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_json(cls, data: dict[str, Any], scraper: str) -> "JobsFile":
        """Parse dateien, retaining per-file provenance and prior-job metadata."""
        data = _JSON_OBJECT.validate_python(data)
        if "dateien" not in data:
            raise ValueError("Jobs response is missing dateien")
        files = TypeAdapter(dict[str, FileStatus]).validate_python(data["dateien"])
        documents: dict[str, dict[str, FileStatus]] = {}
        for path, status in files.items():
            document_id, format_ = _file_identity(path)
            documents.setdefault(document_id, {})[format_] = status
        return cls(
            jobtyp=data.get("jobtyp", "unknown"),
            time=data.get("time", ""),
            scraper=scraper,
            documents=documents,
            files=files,
            job=data.get("job"),
            start_time=data.get("start_time"),
            lastjob=data.get("lastjob", {}),
        )

    def get_documents_by_status(self, status: str) -> list[str]:
        """Return each document ID once if any of its files has the status."""
        return [
            document_id
            for document_id, formats in self.documents.items()
            if any(value.status == status for value in formats.values())
        ]


@dataclass(config=_MODEL_CONFIG)
class SearchHit:
    """A single search result hit."""

    id: str
    score: float | None
    source: dict[str, Any]
    index: str = ""
    docs_url: str = DEFAULT_CONFIG.docs_url
    sort: list[str | int | float | bool | None] | None = None

    def __post_init__(self) -> None:
        """Validate source fields and retain endpoint context."""
        self.source = _SearchSource.model_validate(self.source).model_dump(exclude_none=True)
        self.docs_url = EntscheidsucheConfig(docs_url=self.docs_url).docs_url.rstrip("/")

    @property
    def signatur(self) -> str:
        """Get full document ID from source id, _id, or legacy Signatur."""
        return self.source.get("id") or self.id or self.source.get("Signatur", "")

    @property
    def court_id(self) -> str | None:
        """Get the court hierarchy ID, distinct from the scraper directory."""
        hierarchy = self.source.get("hierarchy", [])
        return hierarchy[1] if len(hierarchy) >= 2 else None

    @property
    def spider(self) -> str:
        """Resolve the scraper from explicit metadata, a docs path, or known index."""
        if self.source.get("Spider"):
            return self.source["Spider"]
        path = self._content_path()
        if path:
            return unquote(path).split("/")[0]
        index_spider = self.index.removeprefix("entscheidsuche.v2-")
        return next((name for name in SCRAPERS if name.lower() == index_spider), "")

    def _content_path(self) -> str | None:
        """Extract a validated path only from the configured docs endpoint."""
        if self.content_url:
            prefix = f"{self.docs_url}/"
            if self.content_url.startswith(prefix):
                path = self.content_url.removeprefix(prefix)
                validate_document_path(path)
                return path
        return None

    @property
    def date(self) -> str:
        """Get document date."""
        return self.source.get("date") or self.source.get("Datum") or ""

    @property
    def language(self) -> str:
        """Get document language."""
        attachment = self.source.get("attachment", {})
        if isinstance(attachment, dict):
            return attachment.get("language") or self.source.get("Sprache", "de")
        return self.source.get("Sprache", "de")

    @property
    def title(self) -> dict[str, str]:
        """Get document title in available languages."""
        return self.source.get("title", {})

    @property
    def abstract(self) -> dict[str, str]:
        """Get document abstract in available languages."""
        return self.source.get("abstract", {})

    @property
    def content_url(self) -> str | None:
        """Get URL to the document content."""
        attachment = self.source.get("attachment", {})
        if isinstance(attachment, dict):
            return attachment.get("content_url")
        return None

    @property
    def reference(self) -> list[str]:
        """Get case references/numbers."""
        reference = self.source.get("reference", [])
        if isinstance(reference, str):
            return [reference]
        if isinstance(reference, list):
            return [str(item) for item in reference]
        return []

    def to_case_document(self) -> CaseDocument:
        """Convert search hit to CaseDocument."""
        html_path = None
        pdf_path = None
        relative_path = self._content_path()
        if relative_path:
            if relative_path.endswith(".html"):
                html_path = relative_path
            elif relative_path.endswith(".pdf"):
                pdf_path = relative_path

        return CaseDocument(
            docs_url=self.docs_url,
            signatur=self.signatur,
            spider=self.spider,
            language=self.language,
            date=self.date,
            html_path=html_path,
            pdf_path=pdf_path,
            url=self.content_url,
            document_id=self.signatur,
            num=self.reference,
            kopfzeile=self.title if isinstance(self.title, dict) else {},
            meta=self.source.get("meta", {}) if isinstance(self.source.get("meta"), dict) else {},
            abstract=self.abstract if isinstance(self.abstract, dict) else {},
            time_utc=self.source.get("scrapedate"),
        )


@dataclass(config=_MODEL_CONFIG)
class SearchResult:
    """Search results from the Elasticsearch API."""

    total: int
    max_score: float | None
    hits: list[SearchHit]
    took_ms: int
    total_relation: Literal["eq", "gte"] | None = None
    timed_out: bool = False
    shards: ShardInfo | None = None

    @property
    def is_complete(self) -> bool:
        """Whether all queried shards completed without a timeout."""
        return not self.timed_out and (
            self.shards is None or (self.shards.failed == 0 and not self.shards.failures)
        )

    @classmethod
    def from_json(
        cls, data: dict[str, Any], docs_url: str = DEFAULT_CONFIG.docs_url
    ) -> "SearchResult":
        """Create a SearchResult from Elasticsearch response."""
        data = _JSON_OBJECT.validate_python(data)
        if "hits" not in data:
            raise ValueError("Search response is missing hits")
        hits_data = _JSON_OBJECT.validate_python(data["hits"])
        total = hits_data.get("total", {})
        if isinstance(total, dict):
            total_count = total.get("value", 0)
        else:
            total_count = total

        hits = [
            SearchHit(
                id=hit.get("_id", ""),
                score=hit.get("_score", 0.0),
                source=hit.get("_source", {}),
                index=hit.get("_index", ""),
                docs_url=docs_url,
                sort=hit.get("sort"),
            )
            for hit in _JSON_OBJECTS.validate_python(hits_data.get("hits", []))
        ]

        result = cls(
            total=total_count,
            total_relation=total.get("relation") if isinstance(total, dict) else "eq",
            timed_out=data.get("timed_out", False),
            shards=ShardInfo.model_validate(data["_shards"]) if "_shards" in data else None,
            max_score=hits_data.get("max_score"),
            hits=hits,
            took_ms=data.get("took", 0),
        )

        if not result.is_complete:
            raise IncompleteSearchError(result)
        return result


class IncompleteSearchError(RuntimeError):
    """A timed-out or failed-shard response; partial data is available in result."""

    def __init__(self, result: SearchResult) -> None:
        self.result = result
        super().__init__("Search is incomplete: timeout or shard failure")


# Canton codes and names mapping
CANTONS = {
    "AG": "Aargau",
    "AI": "Appenzell Innerrhoden",
    "AR": "Appenzell Ausserrhoden",
    "BE": "Bern",
    "BL": "Basel-Land",
    "BS": "Basel-Stadt",
    "FR": "Freiburg",
    "GE": "Genf",
    "GL": "Glarus",
    "GR": "Graubünden",
    "JU": "Jura",
    "LU": "Luzern",
    "NE": "Neuenburg",
    "NW": "Nidwalden",
    "OW": "Obwalden",
    "SG": "St. Gallen",
    "SH": "Schaffhausen",
    "SO": "Solothurn",
    "SZ": "Schwyz",
    "TG": "Thurgau",
    "TI": "Tessin",
    "UR": "Uri",
    "VD": "Waadt",
    "VS": "Wallis",
    "ZG": "Zug",
    "ZH": "Zürich",
    "CH": "Bund",  # Federal level
}

# Known scrapers
SCRAPERS = [
    "AG_Baugesetzgebung",
    "AG_Gerichte",
    "CH_BGer",
    "CH_BSTG",
    "CH_Bundesrat",
    "CH_EDOEB",
    "CH_EGMR",
    "CH_MKG",
    "CH_UNIBE",
    "CH_VB",
    "CH_WEKO",
    "NE_Omni",
    "SH_OG",
    "SZ_Verwaltungsgericht",
    "TA_SST",
    "ZG_Obergericht",
    "CH_BGE",
    "CH_BVGer",
    "CH_BPatG",
    "AG_Weitere",
    "AI_Aktuell",
    "AI_Bericht",
    "AR_Gerichte",
    "BE_ZivilStraf",
    "BE_Anwaltsaufsicht",
    "BE_Verwaltungsgericht",
    "BE_Steuerrekurs",
    "BE_BVD",
    "BE_Weitere",
    "BL_Gerichte",
    "BS_Omni",
    "FR_Gerichte",
    "GE_Gerichte",
    "GL_Omni",
    "GR_Gerichte",
    "JU_Gerichte",
    "LU_Gerichte",
    "NW_Gerichte",
    "OW_Gerichte",
    "SG_Gerichte",
    "SG_Publikationen",
    "SO_Omni",
    "SZ_Gerichte",
    "TI_Gerichte",
    "TG_OG",
    "UR_Gerichte",
    "VD_FindInfo",
    "VD_Omni",
    "VS_Gerichte",
    "ZG_Verwaltungsgericht",
    "ZH_Obergericht",
    "ZH_Verwaltungsgericht",
    "ZH_Steuerrekurs",
    "ZH_Baurekurs",
    "ZH_Sozialversicherungsgericht",
    "XX_Upload",
]
