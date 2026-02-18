# Flood Detection Integration (Telangana)

## Overview

Flood detection is integrated for Telangana operations using Sentinel-style change analysis workflows and map overlays.

Current implementation supports operational simulation and API wiring, with production-ready extension points for Google Earth Engine (GEE).

## Capabilities

- Flood analysis request/response APIs.
- Map overlay support for detected flood polygons.
- Historical flood analysis retrieval.
- Satellite-status endpoint for monitoring.

## API endpoints

- `POST /api/flood-detection/analyze`
- `POST /api/flood-detection/earthquake-analyze`
- `GET /api/flood-detection/historical`
- `GET /api/flood-detection/satellite-status`
- `GET /api/flood-detection/regions`

## Telangana focus

Region defaults and examples are aligned to Telangana locations such as:

- Hyderabad
- Warangal
- Khammam
- Nizamabad

## Production GEE extension

To move from simulation to live satellite execution:

1. Configure a GEE service account.
2. Enable Earth Engine API access.
3. Implement Sentinel-1 fetch + change-detection pipeline.
4. Persist outputs to operational storage for dashboard playback.

## Frontend integration

Frontend map components consume flood endpoints and render polygon layers for response teams, enabling dynamic geospatial correction and situational awareness during dispatch.
