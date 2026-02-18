import { useEffect, useRef } from 'react';
import { useMap } from 'react-leaflet';
import L from 'leaflet';

const DisasterAreasLayer = ({ floodData, earthquakeData, isVisible, layerVisibility }) => {
  const map = useMap();
  const disasterLayersRef = useRef([]);

  useEffect(() => {
    if (!isVisible) return;

    // Clear existing layers
    if (disasterLayersRef.current) {
      disasterLayersRef.current.forEach(layer => {
        if (map.hasLayer(layer)) {
          map.removeLayer(layer);
        }
      });
      disasterLayersRef.current = [];
    }

    // Handle Flood Data
    if (floodData) {
      // Create circular region around the analysis point
      const center = [floodData.location.latitude, floodData.location.longitude];
      const radius = floodData.location.radius_km * 1000; // Convert km to meters
      
      // Add analysis region boundary
      const regionCircle = L.circle(center, {
        radius: radius,
        color: '#3b82f6',
        weight: 2,
        fillColor: '#3b82f6',
        fillOpacity: 0.1
      }).addTo(map);
      
      disasterLayersRef.current.push(regionCircle);

      // Add region label
      const regionLabel = L.marker(center, {
        icon: L.divIcon({
          className: 'flood-region-label',
          html: `<div class="bg-blue-600 text-white px-2 py-1 rounded text-xs font-medium">Flood Analysis (${floodData.location.radius_km}km)</div>`,
          iconSize: [120, 30],
          iconAnchor: [60, 15]
        })
      }).addTo(map);
      
      disasterLayersRef.current.push(regionLabel);

      // Add satellite layers based on visibility
      Object.entries(floodData.satellite_layers).forEach(([key, layer]) => {
        if (layerVisibility[key]) {
          const tileLayer = L.tileLayer(layer.tile_url, {
            opacity: 0.7,
            attribution: `GEE: ${layer.name}`
          }).addTo(map);
          
          disasterLayersRef.current.push(tileLayer);
        }
      });

      // Add flood statistics overlay
      const statsHtml = `
        <div class="bg-white p-3 rounded-lg shadow-lg border">
          <h4 class="font-medium text-gray-800 mb-2">🌊 Flood Analysis Results</h4>
          <div class="text-sm text-gray-600 space-y-1">
            <div><strong>Flood Area:</strong> ${floodData.flood_statistics.flood_area_km2.toFixed(2)} km²</div>
            <div><strong>Analysis Radius:</strong> ${floodData.location.radius_km} km</div>
            <div><strong>Threshold:</strong> ${floodData.threshold_used} dB</div>
          </div>
        </div>
      `;
      
      const statsOverlay = L.control({ position: 'bottomright' });
      statsOverlay.onAdd = function() {
        const div = L.DomUtil.create('div', 'flood-stats-overlay');
        div.innerHTML = statsHtml;
        return div;
      };
      statsOverlay.addTo(map);
      disasterLayersRef.current.push(statsOverlay);

      // Fit map to show the entire analysis region
      map.fitBounds(regionCircle.getBounds(), { padding: [20, 20] });
    }

    // Handle Earthquake Data
    if (earthquakeData) {
      // Create circular region around the analysis point
      const center = [earthquakeData.location.latitude, earthquakeData.location.longitude];
      const radius = earthquakeData.location.radius_km * 1000; // Convert km to meters
      
      // Add analysis region boundary
      const regionCircle = L.circle(center, {
        radius: radius,
        color: '#f97316', // Orange for earthquake
        weight: 2,
        fillColor: '#f97316',
        fillOpacity: 0.1
      }).addTo(map);
      
      disasterLayersRef.current.push(regionCircle);

      // Add region label
      const regionLabel = L.marker(center, {
        icon: L.divIcon({
          className: 'earthquake-region-label',
          html: `<div class="bg-orange-600 text-white px-2 py-1 rounded text-xs font-medium">Earthquake Analysis (${earthquakeData.location.radius_km}km)</div>`,
          iconSize: [140, 30],
          iconAnchor: [70, 15]
        })
      }).addTo(map);
      
      disasterLayersRef.current.push(regionLabel);

      // Add satellite layers based on visibility
      Object.entries(earthquakeData.satellite_layers).forEach(([key, layer]) => {
        if (layerVisibility[key]) {
          const tileLayer = L.tileLayer(layer.tile_url, {
            opacity: 0.7,
            attribution: `GEE: ${layer.name}`
          }).addTo(map);
          
          disasterLayersRef.current.push(tileLayer);
        }
      });

      // Add earthquake statistics overlay
      const statsHtml = `
        <div class="bg-white p-3 rounded-lg shadow-lg border">
          <h4 class="font-medium text-gray-800 mb-2">🌋 Earthquake Analysis Results</h4>
          <div class="text-sm text-gray-600 space-y-1">
            <div><strong>Max Deformation:</strong> ${earthquakeData.deformation_statistics.max_deformation.toFixed(2)} dB</div>
            <div><strong>Affected Area:</strong> ${earthquakeData.deformation_statistics.affected_area_km2.toFixed(2)} km²</div>
            <div><strong>Analysis Radius:</strong> ${earthquakeData.location.radius_km} km</div>
          </div>
        </div>
      `;
      
      const statsOverlay = L.control({ position: 'bottomright' });
      statsOverlay.onAdd = function() {
        const div = L.DomUtil.create('div', 'earthquake-stats-overlay');
        div.innerHTML = statsHtml;
        return div;
      };
      statsOverlay.addTo(map);
      disasterLayersRef.current.push(statsOverlay);

      // Fit map to show the entire analysis region
      map.fitBounds(regionCircle.getBounds(), { padding: [20, 20] });
    }

    return () => {
      // Cleanup function
      if (disasterLayersRef.current) {
        disasterLayersRef.current.forEach(layer => {
          if (map.hasLayer(layer)) {
            map.removeLayer(layer);
          }
        });
        disasterLayersRef.current = [];
      }
    };
  }, [floodData, earthquakeData, isVisible, layerVisibility, map]);

  return null;
};

export default DisasterAreasLayer;
