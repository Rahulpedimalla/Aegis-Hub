from fastapi import APIRouter, Query, HTTPException
from datetime import datetime
from typing import Any, Dict
import os
import hashlib
import math

router = APIRouter()

# Optional Earth Engine import: app must still boot when GEE is unavailable.
EE_AVAILABLE = False
EE_READY = False
EE_ERROR = None
ee = None

try:
    import ee as _ee  # type: ignore
    ee = _ee
    EE_AVAILABLE = True
except Exception as exc:
    EE_AVAILABLE = False
    EE_ERROR = f"earthengine-api not installed: {exc}"


TELANGANA_REGIONS = [
    {"name": "Hyderabad", "latitude": 17.3850, "longitude": 78.4867, "risk_profile": "Urban flood hotspots"},
    {"name": "Warangal", "latitude": 17.9689, "longitude": 79.5941, "risk_profile": "Tank overflow and drainage risk"},
    {"name": "Nizamabad", "latitude": 18.6725, "longitude": 78.0941, "risk_profile": "Riverine flooding"},
    {"name": "Khammam", "latitude": 17.2473, "longitude": 80.1514, "risk_profile": "Godavari belt flood risk"},
    {"name": "Karimnagar", "latitude": 18.4386, "longitude": 79.1288, "risk_profile": "Monsoon runoff zones"},
    {"name": "Nalgonda", "latitude": 17.0575, "longitude": 79.2684, "risk_profile": "Low-lying settlements"},
    {"name": "Mahabubnagar", "latitude": 16.7488, "longitude": 78.0035, "risk_profile": "Flash flood pockets"},
    {"name": "Adilabad", "latitude": 19.6756, "longitude": 78.5339, "risk_profile": "Tributary flooding"},
]


def _init_earth_engine() -> None:
    global EE_READY, EE_ERROR
    if not EE_AVAILABLE:
        return

    if EE_READY:
        return

    project = os.getenv("GEE_PROJECT") or os.getenv("GOOGLE_EARTH_ENGINE_PROJECT")
    try:
        if project:
            ee.Initialize(project=project)
        else:
            ee.Initialize()
        EE_READY = True
        EE_ERROR = None
    except Exception as exc:
        EE_READY = False
        EE_ERROR = str(exc)


def _deterministic_value(seed: str, min_v: float, max_v: float) -> float:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    ratio = int(digest[:8], 16) / 0xFFFFFFFF
    return min_v + (max_v - min_v) * ratio


def _simulated_flood_response(
    latitude: float,
    longitude: float,
    radius_km: float,
    pre_flood_start: str,
    pre_flood_end: str,
    post_flood_start: str,
    post_flood_end: str,
    threshold: float,
) -> Dict[str, Any]:
    seed = f"{latitude:.4f}:{longitude:.4f}:{radius_km}:{pre_flood_start}:{post_flood_end}:{threshold}"
    flood_area = _deterministic_value(seed, 1.2, max(5.0, radius_km * 0.9))
    confidence = _deterministic_value(seed + ":c", 0.71, 0.94)

    # Keep layer names stable for frontend.
    dummy_template = (
        "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
    )

    return {
        "success": True,
        "location": {
            "latitude": latitude,
            "longitude": longitude,
            "radius_km": radius_km
        },
        "analysis_date": datetime.utcnow().isoformat(),
        "date_range": {
            "pre_flood": f"{pre_flood_start} to {pre_flood_end}",
            "post_flood": f"{post_flood_start} to {post_flood_end}"
        },
        "threshold_used": threshold,
        "flood_statistics": {
            "flood_area_km2": round(flood_area, 3),
            "analysis_radius_km": radius_km,
            "confidence": round(confidence, 2),
        },
        "satellite_layers": {
            "pre_flood_vh": {"name": "Pre-flood VH (dB)", "tile_url": dummy_template, "description": "Simulated preview"},
            "pre_flood_vv": {"name": "Pre-flood VV (dB)", "tile_url": dummy_template, "description": "Simulated preview"},
            "post_flood_vh": {"name": "Post-flood VH (dB)", "tile_url": dummy_template, "description": "Simulated preview"},
            "post_flood_vv": {"name": "Post-flood VV (dB)", "tile_url": dummy_template, "description": "Simulated preview"},
            "vh_change": {"name": "VH Change (dB)", "tile_url": dummy_template, "description": "Simulated change map"},
            "vv_change": {"name": "VV Change (dB)", "tile_url": dummy_template, "description": "Simulated change map"},
            "permanent_water": {"name": "Permanent Water", "tile_url": dummy_template, "description": "Simulated mask"},
            "flooded_areas": {"name": "Flooded Areas", "tile_url": dummy_template, "description": "Simulated flood mask"},
        },
        "data_source": {
            "satellite": "Sentinel-1 GRD (simulated fallback)",
            "polarization": "VH and VV",
            "resolution": "10m",
            "water_mask": "JRC Global Surface Water (simulated)",
            "analysis_method": "Change detection with threshold-based classification",
        }
    }


def _gee_tile_url(image, vis_params):
    map_id_dict = ee.Image(image).getMapId(vis_params)
    return map_id_dict["tile_fetcher"].url_format


def _run_gee_flood(
    latitude: float,
    longitude: float,
    radius_km: float,
    pre_flood_start: str,
    pre_flood_end: str,
    post_flood_start: str,
    post_flood_end: str,
    threshold: float,
) -> Dict[str, Any]:
    point = ee.Geometry.Point([longitude, latitude])
    region = point.buffer(radius_km * 1000)

    def _get_s1(polarization: str, start: str, end: str):
        return (
            ee.ImageCollection("COPERNICUS/S1_GRD")
            .filterBounds(region)
            .filterDate(start, end)
            .filter(ee.Filter.eq("instrumentMode", "IW"))
            .filter(ee.Filter.eq("resolution_meters", 10))
            .filter(ee.Filter.listContains("transmitterReceiverPolarisation", polarization))
            .select(polarization)
            .median()
        )

    pre_flood_vh = _get_s1("VH", pre_flood_start, pre_flood_end)
    post_flood_vh = _get_s1("VH", post_flood_start, post_flood_end)
    pre_flood_vv = _get_s1("VV", pre_flood_start, pre_flood_end)
    post_flood_vv = _get_s1("VV", post_flood_start, post_flood_end)

    vh_change = post_flood_vh.subtract(pre_flood_vh)
    vv_change = post_flood_vv.subtract(pre_flood_vv)
    permanent_water = ee.Image("JRC/GSW1_4/GlobalSurfaceWater").select("occurrence").gt(90)

    vh_flooded = vh_change.lt(-threshold).selfMask()
    vv_flooded = vv_change.lt(-threshold).selfMask()
    flooded_areas = vh_flooded.Or(vv_flooded).updateMask(permanent_water.Not())

    flood_area = flooded_areas.multiply(ee.Image.pixelArea()).reduceRegion(
        reducer=ee.Reducer.sum(),
        geometry=region,
        scale=10,
        maxPixels=1e10
    ).get("VH")
    flood_area_val = flood_area.getInfo() or 0

    pre_vis = {"min": -20, "max": -5, "palette": ["white", "black"]}
    change_vis = {"min": -5, "max": 5, "palette": ["red", "white", "blue"]}
    flood_vis = {"palette": ["0000FF"]}
    perm_water_vis = {"palette": ["FF0000"]}

    return {
        "success": True,
        "location": {"latitude": latitude, "longitude": longitude, "radius_km": radius_km},
        "analysis_date": datetime.utcnow().isoformat(),
        "date_range": {
            "pre_flood": f"{pre_flood_start} to {pre_flood_end}",
            "post_flood": f"{post_flood_start} to {post_flood_end}",
        },
        "threshold_used": threshold,
        "flood_statistics": {
            "flood_area_km2": float(flood_area_val) / 1e6 if flood_area_val else 0.0,
            "analysis_radius_km": radius_km,
        },
        "satellite_layers": {
            "pre_flood_vh": {"name": "Pre-flood VH (dB)", "tile_url": _gee_tile_url(pre_flood_vh, pre_vis), "description": "Pre-flood VH"},
            "pre_flood_vv": {"name": "Pre-flood VV (dB)", "tile_url": _gee_tile_url(pre_flood_vv, pre_vis), "description": "Pre-flood VV"},
            "post_flood_vh": {"name": "Post-flood VH (dB)", "tile_url": _gee_tile_url(post_flood_vh, pre_vis), "description": "Post-flood VH"},
            "post_flood_vv": {"name": "Post-flood VV (dB)", "tile_url": _gee_tile_url(post_flood_vv, pre_vis), "description": "Post-flood VV"},
            "vh_change": {"name": "VH Change (dB)", "tile_url": _gee_tile_url(vh_change, change_vis), "description": "VH change"},
            "vv_change": {"name": "VV Change (dB)", "tile_url": _gee_tile_url(vv_change, change_vis), "description": "VV change"},
            "permanent_water": {"name": "Permanent Water", "tile_url": _gee_tile_url(permanent_water, perm_water_vis), "description": "Water mask"},
            "flooded_areas": {"name": "Flooded Areas", "tile_url": _gee_tile_url(flooded_areas, flood_vis), "description": "Flooded area"},
        },
        "data_source": {
            "satellite": "Sentinel-1 GRD",
            "polarization": "VH and VV",
            "resolution": "10m",
            "water_mask": "JRC Global Surface Water",
            "analysis_method": "Change detection with threshold-based classification",
        }
    }


@router.get("/regions")
async def get_supported_regions():
    return {"state": "Telangana", "regions": TELANGANA_REGIONS}


@router.get("/satellite-status")
async def get_satellite_status():
    _init_earth_engine()
    if EE_READY:
        return {
            "satellite_available": True,
            "status": "operational",
            "last_update": datetime.utcnow().isoformat(),
            "data_source": "Sentinel-1 GRD",
            "coverage": "Global",
            "update_frequency": "6-12 days",
            "message": "Earth Engine connected successfully",
        }

    fallback_message = EE_ERROR or "Earth Engine unavailable; simulated fallback will be used."
    return {
        "satellite_available": False,
        "status": "fallback",
        "last_update": datetime.utcnow().isoformat(),
        "data_source": "Sentinel-1 GRD (fallback mode)",
        "coverage": "Global",
        "update_frequency": "N/A",
        "message": fallback_message,
    }


@router.get("/analyze")
async def analyze_flood_detection(
    latitude: float = Query(..., description="Latitude of the location to analyze"),
    longitude: float = Query(..., description="Longitude of the location to analyze"),
    radius_km: float = Query(10.0, description="Radius in kilometers around the point to analyze"),
    pre_flood_start: str = Query("2024-07-01", description="Pre-flood start date (YYYY-MM-DD)"),
    pre_flood_end: str = Query("2024-07-15", description="Pre-flood end date (YYYY-MM-DD)"),
    post_flood_start: str = Query("2024-07-16", description="Post-flood start date (YYYY-MM-DD)"),
    post_flood_end: str = Query("2024-07-31", description="Post-flood end date (YYYY-MM-DD)"),
    threshold: float = Query(1.5, description="Flood detection threshold (dB)"),
):
    try:
        _init_earth_engine()
        if EE_READY:
            return _run_gee_flood(
                latitude=latitude,
                longitude=longitude,
                radius_km=radius_km,
                pre_flood_start=pre_flood_start,
                pre_flood_end=pre_flood_end,
                post_flood_start=post_flood_start,
                post_flood_end=post_flood_end,
                threshold=threshold,
            )

        return _simulated_flood_response(
            latitude=latitude,
            longitude=longitude,
            radius_km=radius_km,
            pre_flood_start=pre_flood_start,
            pre_flood_end=pre_flood_end,
            post_flood_start=post_flood_start,
            post_flood_end=post_flood_end,
            threshold=threshold,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error in flood analysis: {exc}")


@router.get("/historical")
async def get_historical_data(
    latitude: float = Query(..., description="Latitude"),
    longitude: float = Query(..., description="Longitude"),
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
):
    _init_earth_engine()
    if not EE_READY:
        seed = f"{latitude}:{longitude}:{start_date}:{end_date}"
        vh_count = int(_deterministic_value(seed + ":vh", 2, 18))
        vv_count = int(_deterministic_value(seed + ":vv", 2, 18))
        return {
            "location": {"latitude": latitude, "longitude": longitude},
            "date_range": {"start": start_date, "end": end_date},
            "data_availability": {
                "vh_images": vh_count,
                "vv_images": vv_count,
                "total_images": vh_count + vv_count,
            },
            "analysis_ready": True,
            "mode": "fallback",
        }

    try:
        point = ee.Geometry.Point([longitude, latitude])
        historical_vh = (
            ee.ImageCollection("COPERNICUS/S1_GRD")
            .filterBounds(point)
            .filterDate(start_date, end_date)
            .filter(ee.Filter.eq("instrumentMode", "IW"))
            .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
            .select("VH")
        )
        historical_vv = (
            ee.ImageCollection("COPERNICUS/S1_GRD")
            .filterBounds(point)
            .filterDate(start_date, end_date)
            .filter(ee.Filter.eq("instrumentMode", "IW"))
            .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
            .select("VV")
        )
        vh_count = historical_vh.size().getInfo()
        vv_count = historical_vv.size().getInfo()
        return {
            "location": {"latitude": latitude, "longitude": longitude},
            "date_range": {"start": start_date, "end": end_date},
            "data_availability": {
                "vh_images": vh_count,
                "vv_images": vv_count,
                "total_images": vh_count + vv_count,
            },
            "analysis_ready": vh_count > 0 and vv_count > 0,
            "mode": "earth-engine",
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error getting historical data: {exc}")


@router.get("/earthquake-analyze")
async def analyze_earthquake_detection(
    latitude: float = Query(..., description="Latitude of the location to analyze"),
    longitude: float = Query(..., description="Longitude of the location to analyze"),
    radius_km: float = Query(50.0, description="Radius in kilometers around the point to analyze"),
    pre_quake_start: str = Query("2015-04-10", description="Pre-earthquake start date (YYYY-MM-DD)"),
    pre_quake_end: str = Query("2015-04-24", description="Pre-earthquake end date (YYYY-MM-DD)"),
    post_quake_start: str = Query("2015-04-27", description="Post-earthquake start date (YYYY-MM-DD)"),
    post_quake_end: str = Query("2015-05-10", description="Post-earthquake end date (YYYY-MM-DD)"),
):
    # For now, earthquake endpoint uses deterministic fallback.
    seed = f"{latitude}:{longitude}:{radius_km}:{pre_quake_start}:{post_quake_end}"
    max_def = _deterministic_value(seed + ":d", -2.5, 2.5)
    affected_km2 = _deterministic_value(seed + ":a", 2.0, max(10.0, radius_km * 0.8))
    dummy_template = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"

    return {
        "success": True,
        "location": {"latitude": latitude, "longitude": longitude, "radius_km": radius_km},
        "analysis_date": datetime.utcnow().isoformat(),
        "date_range": {
            "pre_quake": f"{pre_quake_start} to {pre_quake_end}",
            "post_quake": f"{post_quake_start} to {post_quake_end}",
        },
        "deformation_statistics": {
            "max_deformation": round(max_def, 3),
            "affected_area_km2": round(affected_km2, 3),
            "analysis_radius_km": radius_km,
        },
        "satellite_layers": {
            "pre_quake": {"name": "Pre-earthquake VV (dB)", "tile_url": dummy_template, "description": "Simulated pre-event"},
            "post_quake": {"name": "Post-earthquake VV (dB)", "tile_url": dummy_template, "description": "Simulated post-event"},
            "ground_deformation": {"name": "Ground Deformation (dB)", "tile_url": dummy_template, "description": "Simulated deformation"},
        },
        "data_source": {
            "satellite": "Sentinel-1 GRD (fallback)",
            "polarization": "VV",
            "resolution": "10m",
            "analysis_method": "Differential SAR-based change detection (simulated)",
        },
    }

