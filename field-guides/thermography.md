# Thermography — Field Guide

Camera: **FLIR Edge series** handheld (visual + thermal, MSX enhancement, FLIR ONE app)

---

## How the camera measures temperature

Thermal measurements show the **surface** temperature of the target. Accuracy depends on three factors:

| Factor | What to watch |
|---|---|
| **Distance to target** | Closer = better spatial resolution and spot size. Get as close/zoomed as safely possible. |
| **Ambient temperature** | Note ambient; it is the reference for ΔT calculations. |
| **Emissivity** | How efficiently the surface radiates heat (see below). |

### Emissivity

- **Matte / painted / oxidised surfaces** — good emitters; the camera's default ~0.95 setting is a fair approximation.
- **Bare / glossy / shiny metal** — poor emitters; the default setting will under-read. Apply a strip of high-emissivity tape or a dab of matt paint over the spot, **or** manually set the known emissivity in the camera before reading.

---

## Camera setup

1. Power on; let the camera warm up briefly.
2. Set the **temperature range** to suit the expected target (e.g. a wider range for electrical gear under fault conditions).
3. Choose a suitable **colour palette** (e.g. Iron or Rainbow for electrical; Greyscale for quick scans).
4. Enable **MSX** and set the MSX distance to match the target distance — this overlays visual detail on the thermal image for easier interpretation.
5. Use the **adjustable measurement spots** to track the hottest and coldest points in the frame. The camera periodically auto-calibrates (mechanical shutter click + brief freeze) — this is normal; wait for it to complete before reading.

---

## Inspection technique

### General

- Inspect under **normal / representative operating load** — an unloaded circuit or idle machine hides faults.
- Keep the **view angle within ~30° of perpendicular** to the target surface to limit reflection error.

### Electrical (switchboards, distribution panels)

1. Open the inspection cover or use an IR window where required (PPE: arc-flash rated).
2. Scan **busbars, breakers, incoming terminals, and all connections**.
3. Compare the **same component across all three phases** — a phase running hotter than its siblings under similar load indicates a loose or corroded connection, an overloaded circuit, or a failing device.
4. Note the hottest spot temperature (°C) and the ΔT above ambient or the reference phase.

### Mechanical (motors, bearings, pumps)

1. Scan **bearing housings** and **couplings**.
2. Compare each bearing housing against its pair or against its known baseline.
3. A bearing running hotter than its baseline or its paired housing suggests a lubrication or wear issue.

---

## Judging severity

Judge findings by **ΔT** (temperature rise over a reference point — ambient air, the established baseline, or a similar phase / component), not by absolute temperature alone.

| ΔT (over reference) | Typical severity |
|---|---|
| < 10 °C | Monitor — recheck at next route interval |
| 10–30 °C | Investigate — plan corrective action |
| > 30 °C | Act promptly — potential imminent failure |

*These are general guidelines; the Mechbase route item shows the configured limit band for this specific point.*

---

## Safety

- Do **not** point the camera at the sun or laser sources.
- For live electrical panels, maintain safe working distance and use appropriate PPE; use an IR window or a non-contact safe zone wherever possible.

---

## Recording the reading in Mechbase

Open the assigned **Route** → tap the **Measurement Item** for this thermal point → the item shows the limit band (minor alert: ~65 °C; major alert: ~90 °C in this demo). Enter the **maximum spot temperature** (°C) observed at the target and confirm.
