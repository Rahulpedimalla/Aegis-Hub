import React, { useState, useEffect, useCallback } from 'react';
import { X, MapPin, Users, Clock, AlertTriangle, CheckCircle, Navigation, Building, Heart, ExternalLink } from 'lucide-react';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import axios from 'axios';

// Fix for default markers in Leaflet
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: require('leaflet/dist/images/marker-icon-2x.png'),
  iconUrl: require('leaflet/dist/images/marker-icon.png'),
  shadowUrl: require('leaflet/dist/images/marker-shadow.png'),
});

const TicketModal = ({ ticket, isOpen, onClose, onStatusUpdate, canEdit = true }) => {
  const [status, setStatus] = useState(ticket.status);
  const [notes, setNotes] = useState(ticket.notes || '');
  const [nearestFacilities, setNearestFacilities] = useState(null);
  const [loadingFacilities, setLoadingFacilities] = useState(false);

  const statusOptions = [
    { value: 'Pending', label: 'Pending', icon: Clock, color: 'bg-yellow-100 text-yellow-800' },
    { value: 'In Progress', label: 'In Progress', icon: AlertTriangle, color: 'bg-blue-100 text-blue-800' },
    { value: 'Done', label: 'Done', icon: CheckCircle, color: 'bg-green-100 text-green-800' },
    { value: 'Cancelled', label: 'Cancelled', icon: X, color: 'bg-gray-100 text-gray-800' }
  ];

  const getPriorityColor = (priority) => {
    const colors = {
      1: 'bg-gray-100 text-gray-700',
      2: 'bg-blue-100 text-blue-700',
      3: 'bg-yellow-100 text-yellow-700',
      4: 'bg-orange-100 text-orange-700',
      5: 'bg-red-100 text-red-700'
    };
    return colors[priority] || colors[1];
  };

  const handleStatusUpdate = () => {
    if (!canEdit) return;
    onStatusUpdate(ticket.id, status, notes);
  };

  const openInMaps = () => {
    const url = `https://www.google.com/maps?q=${ticket.latitude},${ticket.longitude}`;
    window.open(url, '_blank');
  };

  const fetchNearestFacilities = useCallback(async () => {
    if (!ticket?.id) return;
    try {
      setLoadingFacilities(true);
      const response = await axios.get(`/api/sos/${ticket.id}/nearest-facilities`);
      setNearestFacilities(response.data);
    } catch (error) {
      console.error('Error fetching nearest facilities:', error);
      // Don't show error toast as this is not critical
    } finally {
      setLoadingFacilities(false);
    }
  }, [ticket?.id]);

  useEffect(() => {
    if (isOpen && ticket) {
      fetchNearestFacilities();
    }
  }, [isOpen, ticket, fetchNearestFacilities]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 bg-red-100 rounded-lg flex items-center justify-center">
              <AlertTriangle className="w-6 h-6 text-red-600" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-gray-900">SOS Request Details</h2>
              <p className="text-sm text-gray-500">ID: {ticket.external_id}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex h-[calc(90vh-120px)]">
          {/* Left Panel - Details */}
          <div className="w-1/2 p-6 overflow-y-auto">
            <div className="space-y-6">
              {/* Priority and Status */}
              <div className="flex items-center space-x-3">
                <span className={`px-3 py-1 rounded-full text-sm font-medium ${getPriorityColor(ticket.priority)}`}>
                  Priority {ticket.priority}
                </span>
                <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                  statusOptions.find(s => s.value === ticket.status)?.color || 'bg-gray-100 text-gray-800'
                }`}>
                  {ticket.status}
                </span>
              </div>

              {/* Basic Info */}
              <div className="space-y-4">
                <div>
                  <h3 className="text-lg font-semibold text-gray-900 mb-2">Emergency Details</h3>
                  <div className="space-y-3">
                    <div className="flex items-center space-x-2">
                      <AlertTriangle className="w-4 h-4 text-red-500" />
                      <span className="font-medium">{ticket.category}</span>
                    </div>
                    <div className="flex items-center space-x-2">
                      <MapPin className="w-4 h-4 text-gray-500" />
                      <span>{ticket.place}</span>
                    </div>
                    <div className="flex items-center space-x-2">
                      <Users className="w-4 h-4 text-gray-500" />
                      <span>{ticket.people} people affected</span>
                    </div>
                    <div className="flex items-center space-x-2">
                      <Clock className="w-4 h-4 text-gray-500" />
                      <span>Reported: {new Date(ticket.created_at).toLocaleString()}</span>
                    </div>
                  </div>
                </div>

                {/* Description */}
                {ticket.text && (
                  <div>
                    <h4 className="font-medium text-gray-900 mb-2">Description</h4>
                    <div className="bg-gray-50 p-3 rounded-lg">
                      <p className="text-sm text-gray-600">{ticket.text}</p>
                    </div>
                  </div>
                )}

                {/* Location */}
                <div>
                  <h4 className="font-medium text-gray-900 mb-2">Location Coordinates</h4>
                  <div className="bg-gray-50 p-3 rounded-lg">
                    <p className="text-sm text-gray-600">
                      Latitude: {ticket.latitude.toFixed(6)}
                    </p>
                    <p className="text-sm text-gray-600">
                      Longitude: {ticket.longitude.toFixed(6)}
                    </p>
                    <button
                      onClick={openInMaps}
                      className="mt-2 flex items-center space-x-2 text-blue-600 hover:text-blue-700 text-sm"
                    >
                      <Navigation className="w-4 h-4" />
                      <span>Open in Google Maps</span>
                    </button>
                  </div>
                </div>

                {/* Status Update */}
                <div>
                  <h4 className="font-medium text-gray-900 mb-3">Update Status</h4>
                  <div className="space-y-3">
                    <select
                      value={status}
                      onChange={(e) => setStatus(e.target.value)}
                      disabled={!canEdit}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    >
                      {statusOptions.map(option => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                    
                    <textarea
                      placeholder="Add notes or comments..."
                      value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                      rows={3}
                      disabled={!canEdit}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                    
                    <button
                      onClick={handleStatusUpdate}
                      disabled={!canEdit}
                      className="w-full bg-blue-600 text-white py-2 px-4 rounded-lg hover:bg-blue-700 transition-colors duration-200 disabled:bg-gray-400 disabled:cursor-not-allowed"
                    >
                      {canEdit ? 'Update Status' : 'Read-Only'}
                    </button>
                  </div>
                </div>

                {/* Assignment */}
                {ticket.assigned_to && (
                  <div>
                    <h4 className="font-medium text-gray-900 mb-2">Assigned To</h4>
                    <div className="bg-blue-50 p-3 rounded-lg">
                      <p className="text-blue-800">{ticket.assigned_to}</p>
                    </div>
                  </div>
                )}

                {/* Nearest Facilities */}
                <div>
                  <h4 className="font-medium text-gray-900 mb-3">Nearest Available Facilities</h4>
                  
                  {loadingFacilities ? (
                    <div className="bg-gray-50 p-3 rounded-lg">
                      <p className="text-sm text-gray-600">Finding nearest facilities...</p>
                    </div>
                  ) : nearestFacilities ? (
                    <div className="space-y-3">
                      {/* Nearest Shelter */}
                      {nearestFacilities.nearest_shelter && (
                        <div className="bg-green-50 p-3 rounded-lg border border-green-200">
                          <div className="flex items-start justify-between">
                            <div className="flex-1">
                              <div className="flex items-center space-x-2 mb-2">
                                <Building className="w-4 h-4 text-green-600" />
                                <h5 className="font-medium text-green-800">Nearest Shelter</h5>
                              </div>
                              <p className="text-sm font-medium text-green-700 mb-1">
                                {nearestFacilities.nearest_shelter.name}
                              </p>
                              <p className="text-xs text-green-600 mb-2">
                                {nearestFacilities.nearest_shelter.address}
                              </p>
                              <div className="flex items-center space-x-4 text-xs text-green-600 mb-2">
                                <span>📏 {nearestFacilities.nearest_shelter.distance_km} km away</span>
                                <span>🛏️ {nearestFacilities.nearest_shelter.available_capacity} beds available</span>
                              </div>
                              {nearestFacilities.nearest_shelter.contact_phone && (
                                <p className="text-xs text-green-600">
                                  📞 {nearestFacilities.nearest_shelter.contact_phone}
                                </p>
                              )}
                            </div>
                            <a
                              href={nearestFacilities.nearest_shelter.google_maps_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="flex items-center space-x-1 text-green-600 hover:text-green-700 text-xs font-medium"
                            >
                              <ExternalLink className="w-3 h-3" />
                              <span>Navigate</span>
                            </a>
                          </div>
                        </div>
                      )}

                      {/* Nearest Hospital */}
                      {nearestFacilities.nearest_hospital && (
                        <div className="bg-red-50 p-3 rounded-lg border border-red-200">
                          <div className="flex items-start justify-between">
                            <div className="flex-1">
                              <div className="flex items-center space-x-2 mb-2">
                                <Heart className="w-4 h-4 text-red-600" />
                                <h5 className="font-medium text-red-800">Nearest Hospital</h5>
                              </div>
                              <p className="text-sm font-medium text-red-700 mb-1">
                                {nearestFacilities.nearest_hospital.name}
                              </p>
                              <p className="text-xs text-red-600 mb-2">
                                {nearestFacilities.nearest_hospital.address}
                              </p>
                              <div className="flex items-center space-x-4 text-xs text-red-600 mb-2">
                                <span>📏 {nearestFacilities.nearest_hospital.distance_km} km away</span>
                                <span>🛏️ {nearestFacilities.nearest_hospital.available_beds} beds available</span>
                                {nearestFacilities.nearest_hospital.available_icu > 0 && (
                                  <span>🏥 {nearestFacilities.nearest_hospital.available_icu} ICU available</span>
                                )}
                              </div>
                              {nearestFacilities.nearest_hospital.contact_phone && (
                                <p className="text-xs text-red-600">
                                  📞 {nearestFacilities.nearest_hospital.contact_phone}
                                </p>
                              )}
                            </div>
                            <a
                              href={nearestFacilities.nearest_hospital.google_maps_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="flex items-center space-x-1 text-red-600 hover:text-red-700 text-xs font-medium"
                            >
                              <ExternalLink className="w-3 h-3" />
                              <span>Navigate</span>
                            </a>
                          </div>
                        </div>
                      )}

                      {!nearestFacilities.nearest_shelter && !nearestFacilities.nearest_hospital && (
                        <div className="bg-yellow-50 p-3 rounded-lg border border-yellow-200">
                          <p className="text-sm text-yellow-700">
                            ⚠️ No available facilities found within search radius. 
                            Consider expanding search area or checking facility status.
                          </p>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="bg-gray-50 p-3 rounded-lg">
                      <p className="text-sm text-gray-600">
                        Unable to load facility information at this time.
                      </p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Right Panel - Map */}
          <div className="w-1/2 border-l border-gray-200">
            <div className="h-full">
              <MapContainer
                center={[ticket.latitude, ticket.longitude]}
                zoom={12}
                style={{ width: '100%', height: '100%' }}
                className="h-full"
              >
                <TileLayer
                  url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                  attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                />
                
                {/* SOS Location Marker */}
                <Marker position={[ticket.latitude, ticket.longitude]}>
                  <Popup>
                    <div className="text-center">
                      <h3 className="font-semibold text-red-600">🚨 SOS Request</h3>
                      <p className="text-sm text-gray-600">{ticket.category}</p>
                      <p className="text-sm text-gray-600">{ticket.place}</p>
                      <p className="text-sm text-gray-600">{ticket.people} people affected</p>
                    </div>
                  </Popup>
                </Marker>

                {/* Nearest Shelter Marker */}
                {nearestFacilities?.nearest_shelter && (
                  <Marker 
                    position={[nearestFacilities.nearest_shelter.latitude, nearestFacilities.nearest_shelter.longitude]}
                    icon={L.divIcon({
                      className: 'custom-div-icon',
                      html: '<div style="background-color: #10B981; width: 20px; height: 20px; border-radius: 50%; border: 3px solid white; box-shadow: 0 0 4px rgba(0,0,0,0.5);"></div>',
                      iconSize: [20, 20],
                      iconAnchor: [10, 10]
                    })}
                  >
                    <Popup>
                      <div className="text-center">
                        <h3 className="font-semibold text-green-600">🏠 Nearest Shelter</h3>
                        <p className="text-sm text-gray-600">{nearestFacilities.nearest_shelter.name}</p>
                        <p className="text-sm text-gray-600">{nearestFacilities.nearest_shelter.distance_km} km away</p>
                        <p className="text-sm text-gray-600">{nearestFacilities.nearest_shelter.available_capacity} beds available</p>
                        <a 
                          href={nearestFacilities.nearest_shelter.google_maps_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-blue-600 hover:text-blue-700 text-sm font-medium"
                        >
                          🗺️ Get Directions
                        </a>
                      </div>
                    </Popup>
                  </Marker>
                )}

                {/* Nearest Hospital Marker */}
                {nearestFacilities?.nearest_hospital && (
                  <Marker 
                    position={[nearestFacilities.nearest_hospital.latitude, nearestFacilities.nearest_hospital.longitude]}
                    icon={L.divIcon({
                      className: 'custom-div-icon',
                      html: '<div style="background-color: #EF4444; width: 20px; height: 20px; border-radius: 50%; border: 3px solid white; box-shadow: 0 0 4px rgba(0,0,0,0.5);"></div>',
                      iconSize: [20, 20],
                      iconAnchor: [10, 10]
                    })}
                  >
                    <Popup>
                      <div className="text-center">
                        <h3 className="font-semibold text-red-600">🏥 Nearest Hospital</h3>
                        <p className="text-sm text-gray-600">{nearestFacilities.nearest_hospital.name}</p>
                        <p className="text-sm text-gray-600">{nearestFacilities.nearest_hospital.distance_km} km away</p>
                        <p className="text-sm text-gray-600">{nearestFacilities.nearest_hospital.available_beds} beds available</p>
                        {nearestFacilities.nearest_hospital.available_icu > 0 && (
                          <p className="text-sm text-gray-600">{nearestFacilities.nearest_hospital.available_icu} ICU available</p>
                        )}
                        <a 
                          href={nearestFacilities.nearest_hospital.google_maps_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-blue-600 hover:text-blue-700 text-sm font-medium"
                        >
                          🗺️ Get Directions
                        </a>
                      </div>
                    </Popup>
                  </Marker>
                )}
              </MapContainer>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TicketModal;
