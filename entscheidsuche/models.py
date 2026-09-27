"""
Data models for the entscheidsuche.ch API.
"""

from dataclasses import field
from datetime import datetime
from pathlib import PurePosixPath
from typing import Any

from pydantic import ConfigDict, TypeAdapter
from pydantic.dataclasses import dataclass

from .config import DEFAULT_CONFIG

_MODEL_CONFIG = ConfigDict(strict=True, hide_input_in_errors=True)
_JSON_OBJECT = TypeAdapter(dict[str, Any], config=_MODEL_CONFIG)
_JSON_OBJECTS = TypeAdapter(list[dict[str, Any]], config=_MODEL_CONFIG)


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
        """Parse scraper info from status page line."""
        # This is a simplified parser - actual parsing depends on HTML structure
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

    @classmethod
    def from_json(cls, data: dict[str, Any], document_id: str | None = None) -> "CaseDocument":
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

    @property
    def html_url(self) -> str | None:
        """Get full URL for HTML document."""
        if self.html_path:
            return f"{DEFAULT_CONFIG.docs_url}/{self.html_path}"
        return None

    @property
    def pdf_url(self) -> str | None:
        """Get full URL for PDF document."""
        if self.pdf_path:
            return f"{DEFAULT_CONFIG.docs_url}/{self.pdf_path}"
        return None

    @property
    def json_url(self) -> str:
        """Get URL for the JSON metadata file."""
        document_id = self.document_id or self.signatur
        return f"{DEFAULT_CONFIG.docs_url}/{document_id}.json"


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

    @classmethod
    def from_json(cls, data: dict[str, Any], scraper: str) -> "IndexFile":
        """Create an IndexFile from JSON data."""
        data = _JSON_OBJECT.validate_python(data)
        signaturen = _JSON_OBJECT.validate_python(data.get("signaturen", {}))
        total = 0
        new_docs = []
        updated_docs = []
        deleted_docs = []

        for sig_data in signaturen.values():
            if isinstance(sig_data, dict):
                total += sig_data.get("gesamt", 0)
                new_docs.extend(sig_data.get("new", []))
                updated_docs.extend(sig_data.get("update", []))
                deleted_docs.extend(sig_data.get("delete", []))
            elif isinstance(sig_data, int):
                total += sig_data

        return cls(
            jobtyp=data.get("jobtyp", "unknown"),
            time=data.get("time", ""),
            scraper=scraper,
            total_count=total,
            new_documents=new_docs,
            updated_documents=updated_docs,
            deleted_documents=deleted_docs,
        )


@dataclass(config=_MODEL_CONFIG)
class JobsFile:
    """Jobs file containing all documents for a scraper."""

    jobtyp: str
    time: str
    scraper: str
    documents: dict[str, dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def from_json(cls, data: dict[str, Any], scraper: str) -> "JobsFile":
        """Create a JobsFile from JSON data."""
        data = _JSON_OBJECT.validate_python(data)
        return cls(
            jobtyp=data.get("jobtyp", "unknown"),
            time=data.get("time", ""),
            scraper=scraper,
            documents=data.get("signaturen", {}),
        )

    def get_documents_by_status(self, status: str) -> list[str]:
        """Get document names by status (neu, identisch, update, nicht_mehr_da, etc.)."""
        result = []
        for doc_name, formats in self.documents.items():
            if any(
                (value.get("status") if isinstance(value, dict) else value) == status
                for value in formats.values()
            ):
                result.append(doc_name)
        return result


@dataclass(config=_MODEL_CONFIG)
class SearchHit:
    """A single search result hit."""

    id: str
    score: float | None
    source: dict[str, Any]
    index: str = ""

    @property
    def signatur(self) -> str:
        """Get document signature (from _id or source)."""
        return self.source.get("id") or self.id or self.source.get("Signatur", "")

    @property
    def spider(self) -> str:
        """Get spider name from hierarchy or index."""
        hierarchy = self.source.get("hierarchy", [])
        if len(hierarchy) >= 2:
            return hierarchy[1]  # e.g., "AG_BG" from ["AG", "AG_BG", "AG_BG_001"]
        # Try to extract from index name
        if self.index:
            # Index format: entscheidsuche.v2-ag_baugesetzgebung
            parts = self.index.split("-")
            if len(parts) > 1:
                return parts[1].upper()
        return self.source.get("Spider", "")

    @property
    def date(self) -> str:
        """Get document date."""
        return self.source.get("date", "") or self.source.get("Datum", "")

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
        if self.content_url:
            docs_prefix = f"{DEFAULT_CONFIG.docs_url}/"
            if self.content_url.startswith(docs_prefix):
                relative_path = self.content_url.removeprefix(docs_prefix)
                if relative_path.endswith(".html"):
                    html_path = relative_path
                elif relative_path.endswith(".pdf"):
                    pdf_path = relative_path

        return CaseDocument(
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

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "SearchResult":
        """Create a SearchResult from Elasticsearch response."""
        data = _JSON_OBJECT.validate_python(data)
        hits_data = _JSON_OBJECT.validate_python(data.get("hits", {}))
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
            )
            for hit in _JSON_OBJECTS.validate_python(hits_data.get("hits", []))
        ]

        return cls(
            total=total_count,
            max_score=hits_data.get("max_score"),
            hits=hits,
            took_ms=data.get("took", 0),
        )


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
