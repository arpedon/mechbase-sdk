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
    zone_id: int | None
    machine_class: str
    status: int
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> "Asset":
        d = dict(d)
        return cls(
            uuid=d.pop("uuid"),
            asset_id=d.pop("asset_id"),
            name=d.pop("name"),
            zone_id=d.pop("zone_id"),
            machine_class=d.pop("machine_class", ""),
            status=d.pop("status"),
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
