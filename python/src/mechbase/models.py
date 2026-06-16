"""Lightweight dataclass mirrors of the API response schemas.

Kept intentionally small; unknown fields are preserved in ``extra`` so the SDK
doesn't break when the API adds fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _pop(d: dict, key: str, default=None):
    return d.pop(key, default) if key in d else default


@dataclass
class User:
    id: int
    username: str
    full_name: str
    email: str
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> "User":
        d = dict(d)
        return cls(
            id=d.pop("id"),
            username=d.pop("username"),
            full_name=d.pop("full_name"),
            email=d.pop("email", ""),
            extra=d,
        )


@dataclass
class Installation:
    installation_id: int
    name: str
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> "Installation":
        d = dict(d)
        return cls(
            installation_id=d.pop("installation_id"),
            name=d.pop("name"),
            extra=d,
        )


@dataclass
class Me:
    user: User
    installations: list[Installation]
    current_installation_id: int

    @classmethod
    def from_dict(cls, d: dict) -> "Me":
        return cls(
            user=User.from_dict(d["user"]),
            installations=[Installation.from_dict(i) for i in d["installations"]],
            current_installation_id=d["current_installation_id"],
        )


@dataclass
class Asset:
    uuid: str
    asset_id: int | None
    name: str
    section_id: int | None
    zone_id: int | None
    machine_class: str
    equipment_type: str
    status: int
    external_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> "Asset":
        d = dict(d)
        return cls(
            uuid=d.pop("uuid"),
            asset_id=d.pop("asset_id", None),
            name=d.pop("name"),
            section_id=d.pop("section_id", None),
            zone_id=d.pop("zone_id", None),
            machine_class=d.pop("machine_class", ""),
            equipment_type=d.pop("equipment_type", ""),
            status=d.pop("status"),
            external_id=d.pop("external_id", None),
            extra=d,
        )


@dataclass
class MeasurementPoint:
    uuid: str
    point_id: int | None
    name: str
    asset_id: int | None
    transducer_type: str
    measurement_unit_code: str
    location: str
    status: int
    external_id: str | None = None

    @classmethod
    def from_dict(cls, d: dict) -> "MeasurementPoint":
        return cls(
            uuid=d["uuid"],
            point_id=d["point_id"],
            name=d["name"],
            asset_id=d["asset_id"],
            transducer_type=d["transducer_type"],
            measurement_unit_code=d["measurement_unit_code"],
            location=d["location"],
            status=d["status"],
            external_id=d.get("external_id"),
        )


@dataclass
class Measurement:
    uuid: str
    measurement_point_id: int
    point_sequence: int
    data: dict
    status: str
    notes: str
    created_at: str
    external_id: str | None = None
    file_url: str | None = None

    @classmethod
    def from_dict(cls, d: dict) -> "Measurement":
        return cls(
            uuid=d["uuid"],
            measurement_point_id=d["measurement_point_id"],
            point_sequence=d["point_sequence"],
            data=d["data"],
            status=d["status"],
            notes=d.get("notes", ""),
            created_at=d["created_at"],
            external_id=d.get("external_id"),
            file_url=d.get("file_url"),
        )


@dataclass
class Route:
    uuid: str
    name: str
    description: str

    @classmethod
    def from_dict(cls, d: dict) -> "Route":
        return cls(uuid=d["uuid"], name=d["name"], description=d.get("description", ""))


@dataclass
class RouteExecution:
    uuid: str
    route_uuid: str
    status: str
    started_at: str | None
    completed_at: str | None
    session_id: str

    @classmethod
    def from_dict(cls, d: dict) -> "RouteExecution":
        return cls(
            uuid=d["uuid"],
            route_uuid=d["route_uuid"],
            status=d["status"],
            started_at=d.get("started_at"),
            completed_at=d.get("completed_at"),
            session_id=d["session_id"],
        )


@dataclass
class ItemResponse:
    uuid: str
    route_item_uuid: str
    data: dict
    notes: str
    status: int
    created_at: str

    @classmethod
    def from_dict(cls, d: dict) -> "ItemResponse":
        return cls(
            uuid=d["uuid"],
            route_item_uuid=d["route_item_uuid"],
            data=d.get("data", {}),
            notes=d.get("notes", ""),
            status=d["status"],
            created_at=d["created_at"],
        )


@dataclass
class Section:
    uuid: str
    section_id: int | None
    name: str
    external_id: str | None = None

    @classmethod
    def from_dict(cls, d: dict) -> "Section":
        return cls(
            uuid=d["uuid"],
            section_id=d.get("section_id"),
            name=d["name"],
            external_id=d.get("external_id"),
        )


@dataclass
class Zone:
    uuid: str
    zone_id: int | None
    name: str
    section_id: int | None = None
    external_id: str | None = None

    @classmethod
    def from_dict(cls, d: dict) -> "Zone":
        return cls(
            uuid=d["uuid"],
            zone_id=d.get("zone_id"),
            name=d["name"],
            section_id=d.get("section_id"),
            external_id=d.get("external_id"),
        )


@dataclass
class DeleteResult:
    deleted: bool
    uuid: str

    @classmethod
    def from_dict(cls, d: dict) -> "DeleteResult":
        return cls(deleted=d["deleted"], uuid=d["uuid"])


@dataclass
class BatchItemResult:
    index: int
    status: str
    measurement_point_id: int | None = None
    point_sequence: int | None = None
    uuid: str | None = None
    external_id: str | None = None
    detail: str | None = None

    @classmethod
    def from_dict(cls, d: dict) -> "BatchItemResult":
        return cls(
            index=d["index"],
            status=d["status"],
            measurement_point_id=d.get("measurement_point_id"),
            point_sequence=d.get("point_sequence"),
            uuid=d.get("uuid"),
            external_id=d.get("external_id"),
            detail=d.get("detail"),
        )


@dataclass
class BatchResult:
    created: int
    duplicates: int
    errors: int
    results: list[BatchItemResult]

    @classmethod
    def from_dict(cls, d: dict) -> "BatchResult":
        return cls(
            created=d["created"],
            duplicates=d["duplicates"],
            errors=d["errors"],
            results=[BatchItemResult.from_dict(r) for r in d["results"]],
        )


@dataclass
class FileAttachment:
    uuid: str
    name: str
    kind: str
    file_url: str
    created_at: str

    @classmethod
    def from_dict(cls, d: dict) -> "FileAttachment":
        return cls(
            uuid=d["uuid"],
            name=d["name"],
            kind=d["kind"],
            file_url=d["file_url"],
            created_at=d["created_at"],
        )


@dataclass
class MeasurementResult:
    mapping_uuid: str
    ok: bool
    measurement_uuid: str | None = None
    local_uuid: str = ""
    error: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "MeasurementResult":
        return cls(
            mapping_uuid=d["mapping_uuid"],
            ok=d["ok"],
            measurement_uuid=d.get("measurement_uuid"),
            local_uuid=d.get("local_uuid", ""),
            error=d.get("error", ""),
        )
