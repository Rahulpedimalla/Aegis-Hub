import React, { useState, useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import AnalysisPanel from '../components/FloodDetection';
import DisasterAreasLayer from '../components/FloodAreasLayer';
import L from 'leaflet';
import { 
  BarChart3, 
  Layers, 
  Filter,
  Search,
  AlertTriangle,
  Home,
  Activity,
  Info,
  X
} from 'lucide-react';
import 'leaflet/dist/leaflet.css';
import axios from 'axios';
import { toast } from 'react-hot-toast';
import { useAuth } from '../contexts/AuthContext';

// Fix for default markers in Leaflet
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: require('leaflet/dist/images/marker-icon-2x.png'),
  iconUrl: require('leaflet/dist/images/marker-icon.png'),
  shadowUrl: require('leaflet/dist/images/marker-shadow.png'),
});

// Custom marker icons
const createCustomIcon = (color, size = 25) => {
  return L.divIcon({
    html: `<div style="
      width: ${size}px; 
      height: ${size}px; 
      background-color: ${color}; 
      border: 2px solid white; 
      border-radius: 50%; 
      box-shadow: 0 2px 4px rgba(0,0,0,0.3);
      display: flex;
      align-items: center;
      justify-content: center;
      color: white;
      font-weight: bold;
      font-size: 12px;
    "></div>`,
    className: 'custom-marker',
    iconSize: [size, size],
    iconAnchor: [size/2, size/2]
  });
};

// Component to handle map view state changes
const MapController = ({ center, zoom, onMove }) => {
  const map = useMap();
  
  useEffect(() => {
    map.setView(center, zoom);
  }, [center, zoom, map]);

  useEffect(() => {
    const handleMove = () => {
      const center = map.getCenter();
      const zoom = map.getZoom();
      onMove({ longitude: center.lng, latitude: center.lat, zoom });
    };

    map.on('moveend', handleMove);
    return () => {
      map.off('moveend', handleMove);
    };
  }, [map, onMove]);

  return null;
};

const MapViewPage = () => {
  const { user } = useAuth();
  const canUseSatelliteAnalysis = user?.role === 'admin';
  const [viewState, setViewState] = useState({
    longitude: 78.4867, // Hyderabad, Telangana
    latitude: 17.3850,
    zoom: 7
  });
  const [sosData, setSosData] = useState([]);
  const [shelters, setShelters] = useState([]);
  const [hospitals, setHospitals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [floodData, setFloodData] = useState(null);
  const [earthquakeData, setEarthquakeData] = useState(null);
  const [layers, setLayers] = useState({
    sos: true,
    shelters: true,
    hospitals: true,
    flood: false,
    earthquake: false,
    // Satellite layers for flood analysis
    pre_flood_vh: false,
    pre_flood_vv: false,
    post_flood_vh: false,
    post_flood_vv: false,
    vh_change: false,
    vv_change: false,
    permanent_water: false,
    flooded_areas: false,
    // Satellite layers for earthquake analysis
    pre_quake: false,
    post_quake: false,
    ground_deformation: false
  });
  const [filters, setFilters] = useState({
    status: '',
    category: '',
    priority: ''
  });
  const [selectedMarker, setSelectedMarker] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => {
    fetchMapData();
  }, []);

  const fetchMapData = async () => {
    try {
      setLoading(true);
      const [sosRes, sheltersRes, hospitalsRes] = await Promise.all([
        axios.get('/api/sos/map'),
        axios.get('/api/shelters/'),
        axios.get('/api/hospitals/')
      ]);

      setSosData(sosRes.data);
      setShelters(sheltersRes.data);
      setHospitals(hospitalsRes.data);
    } catch (error) {
      toast.error('Failed to fetch map data');
      console.error('Map data fetch error:', error);
    } finally {
      setLoading(false);
    }
  };

  const getPriorityColor = (priority) => {
    const colors = {
      1: '#6b7280',
      2: '#3b82f6',
      3: '#f59e0b',
      4: '#f97316',
      5: '#ef4444'
    };
    return colors[priority] || colors[1];
  };

  const handleMarkerClick = (marker) => {
    setSelectedMarker(marker);
  };

  const handleFloodDataUpdate = (data) => {
    setFloodData(data);
    setEarthquakeData(null); // Clear earthquake data when flood analysis is run
    
    // Only update map view if data is not null
    if (data && data.location) {
      setViewState({
        latitude: data.location.latitude,
        longitude: data.location.longitude,
        zoom: 10
      });
    }
  };

  const handleEarthquakeDataUpdate = (data) => {
    setEarthquakeData(data);
    setFloodData(null); // Clear flood data when earthquake analysis is run
    
    // Only update map view if data is not null
    if (data && data.location) {
      setViewState({
        latitude: data.location.latitude,
        longitude: data.location.longitude,
        zoom: 10
      });
    }
  };

  const closePopup = () => {
    setSelectedMarker(null);
  };

  const filteredSosData = sosData.filter(sos => {
    if (filters.status && sos.status !== filters.status) return false;
    if (filters.category && sos.category !== filters.category) return false;
    if (filters.priority && sos.priority !== parseInt(filters.priority)) return false;
    if (searchTerm) {
      const search = searchTerm.toLowerCase();
      return (
        sos.place?.toLowerCase().includes(search) ||
        sos.category?.toLowerCase().includes(search) ||
        sos.text?.toLowerCase().includes(search)
      );
    }
    return true;
  });

  const filteredShelters = shelters.filter(shelter => {
    if (searchTerm) {
      const search = searchTerm.toLowerCase();
      return (
        shelter.name?.toLowerCase().includes(search) ||
        shelter.address?.toLowerCase().includes(search)
      );
    }
    return true;
  });

  const filteredHospitals = hospitals.filter(hospital => {
    if (searchTerm) {
      const search = searchTerm.toLowerCase();
      return (
        hospital.name?.toLowerCase().includes(search) ||
        hospital.address?.toLowerCase().includes(search)
      );
    }
    return true;
  });

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <div className="w-80 bg-white shadow-lg border-r border-gray-200 flex flex-col">
        {/* Header */}
        {/* Search and Filters */}
        <div className="p-4 border-b border-gray-200 bg-gray-50">
          <div className="space-y-3">
            {/* Search */}
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
              <input
                type="text"
                placeholder="Search locations..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>

            {/* Quick Stats */}
            <div className="grid grid-cols-2 gap-2">
              <div className="bg-white p-3 rounded-lg border border-gray-200">
                <div className="flex items-center space-x-2">
                  <AlertTriangle className="w-4 h-4 text-red-500" />
                  <span className="text-sm font-medium text-gray-700">SOS</span>
                </div>
                <div className="text-lg font-bold text-red-600">{filteredSosData.length}</div>
              </div>
              <div className="bg-white p-3 rounded-lg border border-gray-200">
                <div className="flex items-center space-x-2">
                  <Home className="w-4 h-4 text-green-500" />
                  <span className="text-sm font-medium text-gray-700">Shelters</span>
                </div>
                <div className="text-lg font-bold text-green-600">{filteredShelters.length}</div>
              </div>
            </div>
          </div>
        </div>

        {/* Layer Controls */}
        <div className="flex-1 p-4 overflow-y-auto">
          <div className="space-y-4">
            {/* Basic Layers */}
            <div className="bg-white rounded-lg border border-gray-200 p-4">
              <h3 className="font-semibold text-gray-900 mb-3 flex items-center space-x-2">
                <Layers className="w-4 h-4" />
                <span>Map Layers</span>
              </h3>
              
              <div className="space-y-2">
                <label className="flex items-center space-x-3 p-2 rounded-lg hover:bg-gray-50 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={layers.sos}
                    onChange={(e) => setLayers({...layers, sos: e.target.checked})}
                    className="rounded border-gray-300 text-red-500 focus:ring-red-500"
                  />
                  <AlertTriangle className="w-4 h-4 text-red-500" />
                  <span className="text-sm font-medium">SOS Requests</span>
                  <span className="ml-auto text-xs text-gray-500 bg-red-100 text-red-700 px-2 py-1 rounded-full">
                    {filteredSosData.length}
                  </span>
                </label>
                
                <label className="flex items-center space-x-3 p-2 rounded-lg hover:bg-gray-50 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={layers.shelters}
                    onChange={(e) => setLayers({...layers, shelters: e.target.checked})}
                    className="rounded border-gray-300 text-green-500 focus:ring-green-500"
                  />
                  <Home className="w-4 h-4 text-green-500" />
                  <span className="text-sm font-medium">Shelters</span>
                  <span className="ml-auto text-xs text-gray-500 bg-green-100 text-green-700 px-2 py-1 rounded-full">
                    {filteredShelters.length}
                  </span>
                </label>
                
                <label className="flex items-center space-x-3 p-2 rounded-lg hover:bg-gray-50 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={layers.hospitals}
                    onChange={(e) => setLayers({...layers, hospitals: e.target.checked})}
                    className="rounded border-gray-300 text-blue-500 focus:ring-blue-500"
                  />
                  <Activity className="w-4 h-4 text-blue-500" />
                  <span className="text-sm font-medium">Hospitals</span>
                  <span className="ml-auto text-xs text-gray-500 bg-blue-100 text-blue-700 px-2 py-1 rounded-full">
                    {filteredHospitals.length}
                  </span>
                </label>
              </div>
            </div>

            {/* Analysis Layers */}
            {(floodData || earthquakeData) && (
              <div className="bg-white rounded-lg border border-gray-200 p-4">
                <h3 className="font-semibold text-gray-900 mb-3 flex items-center space-x-2">
                  <BarChart3 className="w-4 h-4" />
                  <span>Analysis Results</span>
                </h3>
                
                <div className="space-y-3">
                  {/* Flood Analysis */}
                  {floodData && (
                    <div className="space-y-2">
                      <label className="flex items-center space-x-3 p-2 rounded-lg hover:bg-blue-50 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={layers.flood}
                          onChange={(e) => setLayers({...layers, flood: e.target.checked})}
                          className="rounded border-gray-300 text-blue-500 focus:ring-blue-500"
                        />
                        <div className="w-3 h-3 rounded-full bg-blue-500"></div>
                        <span className="text-sm font-medium text-blue-700">🌊 Flood Detection</span>
                      </label>
                      
                      {layers.flood && (
                        <div className="ml-6 space-y-2">
                          <div className="flex space-x-2">
                            <button
                              onClick={() => {
                                const newLayers = {...layers};
                                Object.keys(newLayers).forEach(key => {
                                  if (key.startsWith('pre_flood_') || key.startsWith('post_flood_') || 
                                      key.startsWith('vh_change') || key.startsWith('vv_change') || 
                                      key === 'permanent_water' || key === 'flooded_areas') {
                                    newLayers[key] = true;
                                  }
                                });
                                setLayers(newLayers);
                              }}
                              className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded hover:bg-blue-200 transition-colors"
                            >
                              Show All
                            </button>
                            <button
                              onClick={() => {
                                const newLayers = {...layers};
                                Object.keys(newLayers).forEach(key => {
                                  if (key.startsWith('pre_flood_') || key.startsWith('post_flood_') || 
                                      key.startsWith('vh_change') || key.startsWith('vv_change') || 
                                      key === 'permanent_water' || key === 'flooded_areas') {
                                    newLayers[key] = false;
                                  }
                                });
                                setLayers(newLayers);
                              }}
                              className="text-xs bg-gray-100 text-gray-700 px-2 py-1 rounded hover:bg-gray-200 transition-colors"
                            >
                              Hide All
                            </button>
                          </div>
                          
                          {Object.entries(floodData.satellite_layers).map(([key, layer]) => (
                            <label key={key} className="flex items-center space-x-2 text-xs">
                              <input
                                type="checkbox"
                                checked={layers[key]}
                                onChange={(e) => setLayers({...layers, [key]: e.target.checked})}
                                className="rounded border-gray-300"
                              />
                              <span>{layer.name}</span>
                            </label>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Earthquake Analysis */}
                  {earthquakeData && (
                    <div className="space-y-2">
                      <label className="flex items-center space-x-3 p-2 rounded-lg hover:bg-orange-50 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={layers.earthquake}
                          onChange={(e) => setLayers({...layers, earthquake: e.target.checked})}
                          className="rounded border-gray-300 text-orange-500 focus:ring-orange-500"
                        />
                        <div className="w-3 h-3 rounded-full bg-orange-500"></div>
                        <span className="text-sm font-medium text-orange-700">🌋 Earthquake Deformation</span>
                      </label>
                      
                      {layers.earthquake && (
                        <div className="ml-6 space-y-2">
                          <div className="flex space-x-2">
                            <button
                              onClick={() => {
                                const newLayers = {...layers};
                                Object.keys(newLayers).forEach(key => {
                                  if (key.startsWith('pre_quake') || key.startsWith('post_quake') || 
                                      key === 'ground_deformation') {
                                    newLayers[key] = true;
                                  }
                                });
                                setLayers(newLayers);
                              }}
                              className="text-xs bg-orange-100 text-orange-700 px-2 py-1 rounded hover:bg-orange-200 transition-colors"
                            >
                              Show All
                            </button>
                            <button
                              onClick={() => {
                                const newLayers = {...layers};
                                Object.keys(newLayers).forEach(key => {
                                  if (key.startsWith('pre_quake') || key.startsWith('post_quake') || 
                                      key === 'ground_deformation') {
                                    newLayers[key] = false;
                                  }
                                });
                                setLayers(newLayers);
                              }}
                              className="text-xs bg-gray-100 text-gray-700 px-2 py-1 rounded hover:bg-gray-200 transition-colors"
                            >
                              Hide All
                            </button>
                          </div>
                          
                          {Object.entries(earthquakeData.satellite_layers).map(([key, layer]) => (
                            <label key={key} className="flex items-center space-x-2 text-xs">
                              <input
                                type="checkbox"
                                checked={layers[key]}
                                onChange={(e) => setLayers({...layers, [key]: e.target.checked})}
                                className="rounded border-gray-300"
                              />
                              <span>{layer.name}</span>
                            </label>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Filters */}
            <div className="bg-white rounded-lg border border-gray-200 p-4">
              <h3 className="font-semibold text-gray-900 mb-3 flex items-center space-x-2">
                <Filter className="w-4 h-4" />
                <span>Filters</span>
              </h3>
              
              <div className="space-y-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Priority</label>
                  <select
                    value={filters.priority}
                    onChange={(e) => setFilters({...filters, priority: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  >
                    <option value="">All Priorities</option>
                    <option value="1">Priority 1</option>
                    <option value="2">Priority 2</option>
                    <option value="3">Priority 3</option>
                    <option value="4">Priority 4</option>
                    <option value="5">Priority 5</option>
                  </select>
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Status</label>
                  <select
                    value={filters.status}
                    onChange={(e) => setFilters({...filters, status: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  >
                    <option value="">All Status</option>
                    <option value="Pending">Pending</option>
                    <option value="Pending Assignment">Pending Assignment</option>
                    <option value="In Progress">In Progress</option>
                    <option value="Done">Done</option>
                    <option value="Cancelled">Cancelled</option>
                  </select>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Main Map Area */}
      <div className="flex-1 relative">
        {/* Map */}
        <MapContainer
          center={[viewState.latitude, viewState.longitude]}
          zoom={viewState.zoom}
          style={{ width: '100%', height: '100%' }}
          className="h-full"
        >
          <MapController 
            center={[viewState.latitude, viewState.longitude]} 
            zoom={viewState.zoom}
            onMove={setViewState}
          />
          
          <TileLayer
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          />

          {/* Disaster Analysis Layer */}
          <DisasterAreasLayer 
            floodData={floodData} 
            earthquakeData={earthquakeData}
            isVisible={layers.flood || layers.earthquake}
            layerVisibility={layers}
          />

          {/* SOS Markers */}
          {layers.sos && filteredSosData.map((sos) => (
            <Marker
              key={sos.id}
              position={[sos.latitude, sos.longitude]}
              icon={createCustomIcon(getPriorityColor(sos.priority), 20)}
              eventHandlers={{
                click: () => handleMarkerClick({ type: 'sos', data: sos })
              }}
            >
              <Popup>
                <div className="text-center">
                  <h3 className="font-semibold text-red-600">SOS Request</h3>
                  <p className="text-sm text-gray-600">{sos.category}</p>
                  <p className="text-sm text-gray-600">{sos.place}</p>
                  <p className="text-sm text-gray-600">Priority: {sos.priority}</p>
                  <p className="text-sm text-gray-600">Status: {sos.status}</p>
                </div>
              </Popup>
            </Marker>
          ))}

          {/* Shelter Markers */}
          {layers.shelters && filteredShelters.map((shelter) => (
            <Marker
              key={shelter.id}
              position={[shelter.latitude, shelter.longitude]}
              icon={createCustomIcon('#22c55e', 18)}
              eventHandlers={{
                click: () => handleMarkerClick({ type: 'shelter', data: shelter })
              }}
            >
              <Popup>
                <div className="text-center">
                  <h3 className="font-semibold text-green-600">Shelter</h3>
                  <p className="text-sm text-gray-600">{shelter.name}</p>
                  <p className="text-sm text-gray-600">{shelter.address}</p>
                  <p className="text-sm text-gray-600">Capacity: {shelter.capacity}</p>
                  <p className="text-sm text-gray-600">Available: {shelter.capacity - shelter.current_occupancy}</p>
                </div>
              </Popup>
            </Marker>
          ))}

          {/* Hospital Markers */}
          {layers.hospitals && filteredHospitals.map((hospital) => (
            <Marker
              key={hospital.id}
              position={[hospital.latitude, hospital.longitude]}
              icon={createCustomIcon('#3b82f6', 18)}
              eventHandlers={{
                click: () => handleMarkerClick({ type: 'hospital', data: hospital })
              }}
            >
              <Popup>
                <div className="text-center">
                  <h3 className="font-semibold text-blue-600">Hospital</h3>
                  <p className="text-sm text-gray-600">{hospital.name}</p>
                  <p className="text-sm text-gray-600">{hospital.address}</p>
                  <p className="text-sm text-gray-600">Available Beds: {hospital.available_beds}</p>
                  <p className="text-sm text-gray-600">ICU Beds: {hospital.available_icu}</p>
                </div>
              </Popup>
            </Marker>
          ))}
        </MapContainer>

        {/* Analysis Panel */}
        {canUseSatelliteAnalysis ? (
          <AnalysisPanel 
            onFloodDataUpdate={handleFloodDataUpdate}
            onEarthquakeDataUpdate={handleEarthquakeDataUpdate}
          />
        ) : (
          <div className="absolute top-4 right-4 z-10 bg-white/95 border border-amber-200 text-amber-800 px-3 py-2 rounded-lg shadow">
            Satellite analysis is admin-only.
          </div>
        )}

        {/* Analysis Status */}
        {(floodData || earthquakeData) && (
          <div className="absolute top-4 right-4 z-10 bg-white rounded-xl shadow-xl border border-gray-200 p-4 max-w-sm">
            <div className="flex items-start justify-between mb-3">
              <h4 className="font-semibold text-gray-900 flex items-center space-x-2">
                <Info className="w-4 h-4" />
                <span>Analysis Status</span>
              </h4>
              <button
                onClick={() => {
                  setFloodData(null);
                  setEarthquakeData(null);
                  // Reset layer visibility for analysis layers
                  setLayers(prevLayers => {
                    const newLayers = { ...prevLayers };
                    // Clear flood-related layers
                    newLayers.flood = false;
                    Object.keys(newLayers).forEach(key => {
                      if (key.startsWith('pre_flood_') || key.startsWith('post_flood_') || 
                          key.startsWith('vh_change') || key.startsWith('vv_change') || 
                          key === 'permanent_water' || key === 'flooded_areas') {
                        newLayers[key] = false;
                      }
                    });
                    // Clear earthquake-related layers
                    newLayers.earthquake = false;
                    Object.keys(newLayers).forEach(key => {
                      if (key.startsWith('pre_quake') || key.startsWith('post_quake') || 
                          key === 'ground_deformation') {
                        newLayers[key] = false;
                      }
                    });
                    return newLayers;
                  });
                }}
                className="text-gray-400 hover:text-gray-600 p-1 rounded-lg hover:bg-gray-100"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            
            <div className="space-y-3">
              {floodData && (
                <div className="bg-gradient-to-r from-blue-50 to-blue-100 p-3 rounded-lg border border-blue-200">
                  <h5 className="font-semibold text-blue-800 mb-2 flex items-center space-x-2">
                    <div className="w-2 h-2 rounded-full bg-blue-500"></div>
                    <span>🌊 Flood Analysis</span>
                  </h5>
                  <div className="text-sm text-blue-700 space-y-1">
                    <div><strong>Location:</strong> {floodData.location.latitude.toFixed(4)}, {floodData.location.longitude.toFixed(4)}</div>
                    <div><strong>Radius:</strong> {floodData.location.radius_km} km</div>
                    <div><strong>Date Range:</strong> {floodData.date_range.pre_flood} → {floodData.date_range.post_flood}</div>
                    <div><strong>Analysis Date:</strong> {new Date(floodData.analysis_date).toLocaleDateString()}</div>
                    <div className="font-semibold text-blue-800"><strong>Flood Area:</strong> {floodData.flood_statistics.flood_area_km2.toFixed(2)} km²</div>
                  </div>
                </div>
              )}
              
              {earthquakeData && (
                <div className="bg-gradient-to-r from-orange-50 to-orange-100 p-3 rounded-lg border border-orange-200">
                  <h5 className="font-semibold text-orange-800 mb-2 flex items-center space-x-2">
                    <div className="w-2 h-2 rounded-full bg-orange-500"></div>
                    <span>🌋 Earthquake Analysis</span>
                  </h5>
                  <div className="text-sm text-orange-700 space-y-1">
                    <div><strong>Location:</strong> {earthquakeData.location.latitude.toFixed(4)}, {earthquakeData.location.longitude.toFixed(4)}</div>
                    <div><strong>Radius:</strong> {earthquakeData.location.radius_km} km</div>
                    <div><strong>Date Range:</strong> {earthquakeData.date_range.pre_quake} → {earthquakeData.date_range.post_quake}</div>
                    <div><strong>Analysis Date:</strong> {new Date(earthquakeData.analysis_date).toLocaleDateString()}</div>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Marker Details Modal */}
        {selectedMarker && (
          <div className="absolute inset-0 bg-black bg-opacity-50 flex items-center justify-center z-20">
            <div className="bg-white rounded-xl shadow-2xl max-w-md w-full mx-4 max-h-[80vh] overflow-y-auto">
              <div className="p-6">
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center space-x-3">
                    {selectedMarker.type === 'sos' && <AlertTriangle className="w-6 h-6 text-red-500" />}
                    {selectedMarker.type === 'shelter' && <Home className="w-6 h-6 text-green-500" />}
                    {selectedMarker.type === 'hospital' && <Activity className="w-6 h-6 text-blue-500" />}
                    <h3 className="text-lg font-semibold text-gray-900">
                      {selectedMarker.type === 'sos' ? 'SOS Request' : 
                       selectedMarker.type === 'shelter' ? 'Shelter' : 'Hospital'}
                    </h3>
                  </div>
                  <button
                    onClick={closePopup}
                    className="text-gray-400 hover:text-gray-600 p-1 rounded-lg hover:bg-gray-100"
                  >
                    <X className="w-5 h-5" />
                  </button>
                </div>
                
                <div className="space-y-4">
                  <div className="bg-gray-50 p-4 rounded-lg">
                    <h4 className="font-medium text-gray-900 mb-2">{selectedMarker.data.name || selectedMarker.data.category}</h4>
                    <p className="text-gray-600">{selectedMarker.data.address || selectedMarker.data.place}</p>
                  </div>
                  
                  {selectedMarker.type === 'sos' && (
                    <div className="grid grid-cols-2 gap-4">
                      <div className="text-center p-3 bg-red-50 rounded-lg">
                        <div className="text-sm text-gray-600">Priority</div>
                        <div className="font-semibold text-red-600">{selectedMarker.data.priority}</div>
                      </div>
                      <div className="text-center p-3 bg-blue-50 rounded-lg">
                        <div className="text-sm text-gray-600">Status</div>
                        <div className="font-semibold text-blue-600">{selectedMarker.data.status}</div>
                      </div>
                    </div>
                  )}
                  
                  {(selectedMarker.type === 'shelter' || selectedMarker.type === 'hospital') && (
                    <div className="grid grid-cols-2 gap-4">
                      <div className="text-center p-3 bg-green-50 rounded-lg">
                        <div className="text-sm text-gray-600">Available</div>
                        <div className="font-semibold text-green-600">
                          {selectedMarker.type === 'shelter' 
                            ? selectedMarker.data.capacity - selectedMarker.data.current_occupancy
                            : selectedMarker.data.available_beds}
                        </div>
                      </div>
                      <div className="text-center p-3 bg-blue-50 rounded-lg">
                        <div className="text-sm text-gray-600">Total</div>
                        <div className="font-semibold text-blue-600">
                          {selectedMarker.type === 'shelter' 
                            ? selectedMarker.data.capacity
                            : selectedMarker.data.total_beds}
                        </div>
                      </div>
                    </div>
                  )}
                  
                  <div className="flex space-x-2">
                    <button
                      onClick={() => {
                        if (selectedMarker.type === 'sos') {
                          window.location.href = '/tickets';
                        } else {
                          closePopup();
                        }
                      }}
                      className="flex-1 bg-blue-600 text-white py-2 px-4 rounded-lg hover:bg-blue-700 transition-colors"
                    >
                      View Details
                    </button>
                    <button
                      onClick={() => {
                        const lat = selectedMarker.data.latitude;
                        const lon = selectedMarker.data.longitude;
                        window.open(`https://www.google.com/maps/dir/?api=1&destination=${lat},${lon}`, '_blank');
                      }}
                      className="flex-1 bg-gray-100 text-gray-700 py-2 px-4 rounded-lg hover:bg-gray-200 transition-colors"
                    >
                      Get Directions
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default MapViewPage;
