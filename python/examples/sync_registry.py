"""Upsert a section/zone/asset/point chain by external_id, then batch-push readings."""
from mechbase import Mechbase

client = Mechbase(token="...")
inst = client.for_installation(client.me().current_installation_id)

inst.sections.upsert(external_id="HALL-A", name="Hall A")
inst.zones.upsert(external_id="Z-1", name="Pump Row", section_external_id="HALL-A")
inst.assets.upsert(external_id="PUMP-1", name="Feed Pump 1", zone_external_id="Z-1",
                   equipment_type="pump", machine_class="II")
inst.measurement_points.upsert(external_id="PUMP-1-DE", name="Drive End",
                               asset_external_id="PUMP-1", transducer_type="accel",
                               measurement_unit_code="mm_s")

result = inst.measurements.create_batch([
    {"measurement_point_external_id": "PUMP-1-DE", "data": {"rms": 2.3}, "external_id": "r-1"},
])
print(f"created={result.created} duplicates={result.duplicates} errors={result.errors}")
