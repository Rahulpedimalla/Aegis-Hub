import React, { useState, useEffect, useRef } from 'react';
import { 
  Satellite, 
  CheckCircle, 
  Clock, 
  Globe,
  X,
  Zap
} from 'lucide-react';
import axios from 'axios';
import { toast } from 'react-hot-toast';

const AnalysisPanel = ({ onFloodDataUpdate, onEarthquakeDataUpdate }) => {
  const [isVisible, setIsVisible] = useState(false);
  const [analysisType, setAnalysisType] = useState('flood'); // 'flood' or 'earthquake'
  const [analysisParams, setAnalysisParams] = useState({
    latitude: 17.3850,  // Default to Hyderabad
    longitude: 78.4867,
    radius_km: 10.0,
    pre_flood_start: '2024-07-01',
    pre_flood_end: '2024-07-15',
    post_flood_start: '2024-07-16',
    post_flood_end: '2024-07-31',
    threshold: 1.5
  });

  const [earthquakeParams, setEarthquakeParams] = useState({
    latitude: 27.7,  // Default to Nepal earthquake region
    longitude: 86.5,
    radius_km: 50.0,
    pre_quake_start: '2015-04-10',
    pre_quake_end: '2015-04-24',
    post_quake_start: '2015-04-27',
    post_quake_end: '2015-05-10'
  });

  const [locationName, setLocationName] = useState('Hyderabad');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisProgress, setAnalysisProgress] = useState(0);
  const [floodData, setFloodData] = useState(null);
  const [earthquakeData, setEarthquakeData] = useState(null);
  const [satelliteStatus, setSatelliteStatus] = useState(null);
  const [availableRegions, setAvailableRegions] = useState([]);
  
  const progressIntervalRef = useRef(null);

  useEffect(() => {
    const fetchSatelliteStatus = async () => {
      try {
        const response = await axios.get('/api/flood-detection/satellite-status');
        setSatelliteStatus(response.data);
      } catch (error) {
        console.error('Error fetching satellite status:', error);
        setSatelliteStatus({ satellite_available: false, error: 'Failed to fetch status' });
      }
    };

    fetchSatelliteStatus();
    fetchAvailableRegions();
  }, []);

  const fetchAvailableRegions = async () => {
    try {
      const response = await axios.get('/api/flood-detection/regions');
      setAvailableRegions(response.data.regions);
    } catch (error) {
      console.error('Error fetching regions:', error);
    }
  };

  const startProgressSimulation = () => {
    setAnalysisProgress(0);
    progressIntervalRef.current = setInterval(() => {
      setAnalysisProgress(prev => {
        if (prev >= 100) {
          clearInterval(progressIntervalRef.current);
          return 100;
        }
        return prev + Math.random() * 15;
      });
    }, 500);
  };

  const stopProgressSimulation = () => {
    if (progressIntervalRef.current) {
      clearInterval(progressIntervalRef.current);
      progressIntervalRef.current = null;
    }
  };

  const runAnalysis = async () => {
    if (isAnalyzing) return;
    
    setIsAnalyzing(true);
    setAnalysisProgress(0);
    startProgressSimulation();
    
    try {
      if (analysisType === 'flood') {
        const response = await axios.get('/api/flood-detection/analyze', {
          params: {
            latitude: analysisParams.latitude,
            longitude: analysisParams.longitude,
            radius_km: analysisParams.radius_km,
            pre_flood_start: analysisParams.pre_flood_start,
            pre_flood_end: analysisParams.pre_flood_end,
            post_flood_start: analysisParams.post_flood_start,
            post_flood_end: analysisParams.post_flood_end,
            threshold: analysisParams.threshold
          }
        });
        
        stopProgressSimulation();
        setAnalysisProgress(100);
        
        const data = response.data;
        setFloodData(data);
        
        // Update parent component
        if (onFloodDataUpdate) {
          onFloodDataUpdate(data);
        }
        
        toast.success(`Flood analysis completed for ${locationName}!`);
      } else {
        // Earthquake analysis
        const response = await axios.get('/api/flood-detection/earthquake-analyze', {
          params: {
            latitude: earthquakeParams.latitude,
            longitude: earthquakeParams.longitude,
            radius_km: earthquakeParams.radius_km,
            pre_quake_start: earthquakeParams.pre_quake_start,
            pre_quake_end: earthquakeParams.pre_quake_end,
            post_quake_start: earthquakeParams.post_quake_start,
            post_quake_end: earthquakeParams.post_quake_end
          }
        });
        
        stopProgressSimulation();
        setAnalysisProgress(100);
        
        const data = response.data;
        setEarthquakeData(data);
        
        // Update parent component
        if (onEarthquakeDataUpdate) {
          onEarthquakeDataUpdate(data);
        }
        
        toast.success(`Earthquake analysis completed for ${locationName}!`);
      }
      
    } catch (error) {
      stopProgressSimulation();
      console.error('Analysis error:', error);
      toast.error(`Failed to run ${analysisType} analysis. Please try again.`);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const getProgressText = () => {
    if (analysisType === 'flood') {
      if (analysisProgress < 20) return "Initializing flood analysis...";
      if (analysisProgress < 40) return "Loading satellite data...";
      if (analysisProgress < 60) return "Processing VH polarization...";
      if (analysisProgress < 80) return "Processing VV polarization...";
      if (analysisProgress < 100) return "Finalizing flood detection...";
      return "Flood analysis completed!";
    } else {
      if (analysisProgress < 20) return "Initializing earthquake analysis...";
      if (analysisProgress < 40) return "Loading Sentinel-1 data...";
      if (analysisProgress < 60) return "Processing ground deformation...";
      if (analysisProgress < 80) return "Calculating displacement...";
      if (analysisProgress < 100) return "Finalizing earthquake analysis...";
      return "Earthquake analysis completed!";
    }
  };

  if (!isVisible) {
    return (
      <button
        onClick={() => setIsVisible(true)}
        className="fixed top-4 right-4 z-[9999] bg-blue-600 text-white px-4 py-2 rounded-lg shadow-lg hover:bg-blue-700 transition-colors duration-200 flex items-center space-x-2 border-2 border-white"
        style={{ 
          position: 'fixed', 
          zIndex: 9999,
          boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.3)',
          backdropFilter: 'blur(10px)'
        }}
      >
        <Satellite className="w-5 h-5" />
        <span className="font-medium">Satellite Analysis</span>
      </button>
    );
  }

  return (
    <>
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-black bg-opacity-25 z-[9998]" 
        onClick={() => setIsVisible(false)}
        style={{ position: 'fixed', zIndex: 9998 }}
      />
      
      {/* Main Component */}
      <div 
        className="fixed top-4 right-4 z-[9999] bg-white rounded-xl shadow-2xl border-2 border-blue-200 w-96 max-h-[90vh] overflow-y-auto" 
        style={{ 
          position: 'fixed', 
          zIndex: 9999,
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
          backdropFilter: 'blur(10px)',
          backgroundColor: 'rgba(255, 255, 255, 0.95)'
        }}
      >
        {/* Header */}
        <div className="p-4 border-b border-gray-200 bg-gradient-to-r from-blue-50 to-green-50">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Satellite className="w-6 h-6 text-blue-600" />
              <div>
                <h3 className="text-lg font-semibold text-gray-900">Satellite Analysis</h3>
                <p className="text-sm text-gray-600">Real-time disaster detection</p>
              </div>
            </div>
            <button
              onClick={() => setIsVisible(false)}
              className="p-2 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100 transition-colors duration-200"
              style={{ position: 'relative', zIndex: 10000 }}
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Analysis Type Selection */}
        <div className="p-4 border-b border-gray-200">
          <h4 className="font-medium text-gray-800 mb-3 flex items-center space-x-2">
            <Zap className="w-4 h-4" />
            <span>Analysis Type</span>
          </h4>
          
          <div className="grid grid-cols-2 gap-2">
            <button
              onClick={() => {
                setAnalysisType('flood');
                setFloodData(null);
                setEarthquakeData(null);
                // Clear parent component data
                if (onFloodDataUpdate) onFloodDataUpdate(null);
                if (onEarthquakeDataUpdate) onEarthquakeDataUpdate(null);
              }}
              className={`p-3 rounded-lg border-2 transition-all duration-200 flex items-center space-x-2 ${
                analysisType === 'flood'
                  ? 'border-blue-500 bg-blue-50 text-blue-700'
                  : 'border-gray-200 bg-gray-50 text-gray-600 hover:border-blue-300'
              }`}
            >
              <div className="w-3 h-3 rounded-full bg-blue-500"></div>
              <span className="font-medium">Flood Detection</span>
            </button>
            
            <button
              onClick={() => {
                setAnalysisType('earthquake');
                setFloodData(null);
                setEarthquakeData(null);
                // Clear parent component data
                if (onFloodDataUpdate) onFloodDataUpdate(null);
                if (onEarthquakeDataUpdate) onEarthquakeDataUpdate(null);
              }}
              className={`p-3 rounded-lg border-2 transition-all duration-200 flex items-center space-x-2 ${
                analysisType === 'earthquake'
                  ? 'border-orange-500 bg-orange-50 text-orange-700'
                  : 'border-gray-200 bg-gray-50 text-gray-600 hover:border-orange-300'
              }`}
            >
              <div className="w-3 h-3 rounded-full bg-orange-500"></div>
              <span className="font-medium">Earthquake</span>
            </button>
          </div>
        </div>

      {/* Satellite Status */}
      <div className="p-4 border-b border-gray-200">
        <h4 className="font-medium text-gray-800 mb-3 flex items-center space-x-2">
          <Satellite className="w-4 h-4" />
          <span>Satellite Status</span>
        </h4>
        
        {satelliteStatus ? (
          <div className={`p-3 rounded-lg ${
            satelliteStatus.satellite_available 
              ? 'bg-green-50 border border-green-200' 
              : 'bg-red-50 border border-red-200'
          }`}>
            <div className="flex items-center space-x-2 mb-2">
              {satelliteStatus.satellite_available ? (
                <CheckCircle className="w-4 h-4 text-green-600" />
              ) : (
                <X className="w-4 h-4 text-red-600" />
              )}
              <span className={`font-medium ${
                satelliteStatus.satellite_available ? 'text-green-800' : 'text-red-800'
              }`}>
                {satelliteStatus.satellite_available ? 'Operational' : 'Not Available'}
              </span>
            </div>
            
            <div className="text-sm space-y-1">
              <div className={satelliteStatus.satellite_available ? 'text-green-700' : 'text-red-700'}>
                {satelliteStatus.message || 'Status information'}
              </div>
              {satelliteStatus.data_source && (
                <div className="text-gray-600">
                  <strong>Data Source:</strong> {satelliteStatus.data_source}
                </div>
              )}
              {satelliteStatus.coverage && (
                <div className="text-gray-600">
                  <strong>Coverage:</strong> {satelliteStatus.coverage}
                </div>
              )}
              {satelliteStatus.update_frequency && (
                <div className="text-gray-600">
                  <strong>Update Frequency:</strong> {satelliteStatus.update_frequency}
                </div>
              )}
              {satelliteStatus.error && (
                <div className="text-red-600 text-xs mt-2">
                  <strong>Error:</strong> {satelliteStatus.error}
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="p-3 rounded-lg bg-yellow-50 border border-yellow-200">
            <div className="flex items-center space-x-2">
              <Clock className="w-4 h-4 text-yellow-600" />
              <span className="font-medium text-yellow-800">Checking satellite status...</span>
            </div>
          </div>
        )}
      </div>

      {/* Location Input */}
      <div className="p-4 border-b border-gray-200">
        <h4 className="font-medium text-gray-800 mb-3">📍 Analysis Location</h4>
        {analysisType === 'flood' && availableRegions.length > 0 && (
          <p className="text-xs text-gray-500 mb-2">
            Telangana regions loaded: {availableRegions.length}
          </p>
        )}
        
        {/* Location Name */}
        <div className="mb-3">
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Location Name
          </label>
          <input
            type="text"
            value={locationName}
            onChange={(e) => setLocationName(e.target.value)}
            placeholder={analysisType === 'flood' ? "Enter location name (e.g., Hyderabad, Warangal)" : "Enter location name (e.g., Nepal, Kathmandu)"}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        {/* Coordinates */}
        <div className="grid grid-cols-2 gap-3 mb-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Latitude
            </label>
            <input
              type="number"
              step="0.0001"
              value={analysisType === 'flood' ? analysisParams.latitude : earthquakeParams.latitude}
              onChange={(e) => {
                if (analysisType === 'flood') {
                  setAnalysisParams({
                    ...analysisParams,
                    latitude: parseFloat(e.target.value)
                  });
                } else {
                  setEarthquakeParams({
                    ...earthquakeParams,
                    latitude: parseFloat(e.target.value)
                  });
                }
              }}
              placeholder={analysisType === 'flood' ? "17.3850" : "27.7"}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Longitude
            </label>
            <input
              type="number"
              step="0.0001"
              value={analysisType === 'flood' ? analysisParams.longitude : earthquakeParams.longitude}
              onChange={(e) => {
                if (analysisType === 'flood') {
                  setAnalysisParams({
                    ...analysisParams,
                    longitude: parseFloat(e.target.value)
                  });
                } else {
                  setEarthquakeParams({
                    ...earthquakeParams,
                    longitude: parseFloat(e.target.value)
                  });
                }
              }}
              placeholder={analysisType === 'flood' ? "78.4867" : "86.5"}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>

        {/* Analysis Radius */}
        <div className="mb-3">
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Analysis Radius: {analysisType === 'flood' ? analysisParams.radius_km : earthquakeParams.radius_km} km
          </label>
          <input
            type="range"
            min="1"
            max={analysisType === 'flood' ? "50" : "100"}
            step="0.5"
            value={analysisType === 'flood' ? analysisParams.radius_km : earthquakeParams.radius_km}
            onChange={(e) => {
              if (analysisType === 'flood') {
                setAnalysisParams({
                  ...analysisParams,
                  radius_km: parseFloat(e.target.value)
                });
              } else {
                setEarthquakeParams({
                  ...earthquakeParams,
                  radius_km: parseFloat(e.target.value)
                });
              }
            }}
            className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
          />
        </div>

        {/* Quick Presets */}
        <div className="mb-3">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Quick Presets
          </label>
          <div className="grid grid-cols-2 gap-2">
            {analysisType === 'flood' ? (
              <>
                <button
                  onClick={() => {
                    setAnalysisParams({
                      ...analysisParams,
                      latitude: 17.3850,
                      longitude: 78.4867
                    });
                    setLocationName('Hyderabad');
                  }}
                  className="px-3 py-1 text-xs bg-blue-100 text-blue-700 rounded hover:bg-blue-200 transition-colors"
                >
                  Hyderabad
                </button>
                <button
                  onClick={() => {
                    setAnalysisParams({
                      ...analysisParams,
                      latitude: 17.9689,
                      longitude: 79.5941
                    });
                    setLocationName('Warangal');
                  }}
                  className="px-3 py-1 text-xs bg-green-100 text-green-700 rounded hover:bg-green-200 transition-colors"
                >
                  Warangal
                </button>
                <button
                  onClick={() => {
                    setAnalysisParams({
                      ...analysisParams,
                      latitude: 18.6725,
                      longitude: 78.0941
                    });
                    setLocationName('Nizamabad');
                  }}
                  className="px-3 py-1 text-xs bg-purple-100 text-purple-700 rounded hover:bg-purple-200 transition-colors"
                >
                  Nizamabad
                </button>
                <button
                  onClick={() => {
                    setAnalysisParams({
                      ...analysisParams,
                      latitude: 17.2473,
                      longitude: 80.1514
                    });
                    setLocationName('Khammam');
                  }}
                  className="px-3 py-1 text-xs bg-orange-100 text-orange-700 rounded hover:bg-orange-200 transition-colors"
                >
                  Khammam
                </button>
              </>
            ) : (
              <>
                <button
                  onClick={() => {
                    setEarthquakeParams({
                      ...earthquakeParams,
                      latitude: 27.7,
                      longitude: 86.5
                    });
                    setLocationName('Nepal Earthquake 2015');
                  }}
                  className="px-3 py-1 text-xs bg-orange-100 text-orange-700 rounded hover:bg-orange-200 transition-colors"
                >
                  Nepal 2015
                </button>
                <button
                  onClick={() => {
                    setEarthquakeParams({
                      ...earthquakeParams,
                      latitude: 30.0,
                      longitude: 78.0
                    });
                    setLocationName('Uttarakhand Region');
                  }}
                  className="px-3 py-1 text-xs bg-red-100 text-red-700 rounded hover:bg-red-200 transition-colors"
                >
                  Uttarakhand
                </button>
                <button
                  onClick={() => {
                    setEarthquakeParams({
                      ...earthquakeParams,
                      latitude: 34.0,
                      longitude: 74.0
                    });
                    setLocationName('Kashmir Region');
                  }}
                  className="px-3 py-1 text-xs bg-yellow-100 text-yellow-700 rounded hover:bg-yellow-200 transition-colors"
                >
                  Kashmir
                </button>
                <button
                  onClick={() => {
                    setEarthquakeParams({
                      ...earthquakeParams,
                      latitude: 23.0,
                      longitude: 80.0
                    });
                    setLocationName('Central India');
                  }}
                  className="px-3 py-1 text-xs bg-indigo-100 text-indigo-700 rounded hover:bg-indigo-200 transition-colors"
                >
                  Central India
                </button>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Date Range */}
      <div className="p-4 space-y-4">
        <h4 className="font-medium text-gray-900 flex items-center space-x-2">
          <Globe className="w-4 h-4" />
          <span>Analysis Parameters</span>
        </h4>

        {/* Date Range */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {analysisType === 'flood' ? 'Pre-flood Start' : 'Pre-quake Start'}
            </label>
            <input
              type="date"
              value={analysisType === 'flood' ? analysisParams.pre_flood_start : earthquakeParams.pre_quake_start}
              onChange={(e) => {
                if (analysisType === 'flood') {
                  setAnalysisParams({
                    ...analysisParams,
                    pre_flood_start: e.target.value
                  });
                } else {
                  setEarthquakeParams({
                    ...earthquakeParams,
                    pre_quake_start: e.target.value
                  });
                }
              }}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={isAnalyzing}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {analysisType === 'flood' ? 'Pre-flood End' : 'Pre-quake End'}
            </label>
            <input
              type="date"
              value={analysisType === 'flood' ? analysisParams.pre_flood_end : earthquakeParams.pre_quake_end}
              onChange={(e) => {
                if (analysisType === 'flood') {
                  setAnalysisParams({
                    ...analysisParams,
                    pre_flood_end: e.target.value
                  });
                } else {
                  setEarthquakeParams({
                    ...earthquakeParams,
                    pre_quake_end: e.target.value
                  });
                }
              }}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={isAnalyzing}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {analysisType === 'flood' ? 'Post-flood Start' : 'Post-quake Start'}
            </label>
            <input
              type="date"
              value={analysisType === 'flood' ? analysisParams.post_flood_start : earthquakeParams.post_quake_start}
              onChange={(e) => {
                if (analysisType === 'flood') {
                  setAnalysisParams({
                    ...analysisParams,
                    post_flood_start: e.target.value
                  });
                } else {
                  setEarthquakeParams({
                    ...earthquakeParams,
                    post_quake_start: e.target.value
                  });
                }
              }}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={isAnalyzing}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {analysisType === 'flood' ? 'Post-flood End' : 'Post-quake End'}
            </label>
            <input
              type="date"
              value={analysisType === 'flood' ? analysisParams.post_flood_end : earthquakeParams.post_quake_end}
              onChange={(e) => {
                if (analysisType === 'flood') {
                  setAnalysisParams({
                    ...analysisParams,
                    post_flood_end: e.target.value
                  });
                } else {
                  setEarthquakeParams({
                    ...earthquakeParams,
                    post_quake_end: e.target.value
                  });
                }
              }}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={isAnalyzing}
            />
          </div>
        </div>

        {/* Threshold (only for flood analysis) */}
        {analysisType === 'flood' && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Flood Detection Threshold: {analysisParams.threshold} dB
            </label>
            <input
              type="range"
              min="0.5"
              max="3.0"
              step="0.1"
              value={analysisParams.threshold}
              onChange={(e) => setAnalysisParams({
                ...analysisParams,
                threshold: parseFloat(e.target.value)
              })}
              className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
              disabled={isAnalyzing}
            />
            <div className="flex justify-between text-xs text-gray-500 mt-1">
              <span>Less Sensitive</span>
              <span>More Sensitive</span>
            </div>
          </div>
        )}
      </div>

      {/* Run Analysis Button */}
      <button
        onClick={runAnalysis}
        disabled={isAnalyzing || satelliteStatus?.status === 'error'}
        className={`w-full py-3 px-4 rounded-lg font-medium transition-colors duration-200 flex items-center justify-center space-x-2 ${
          isAnalyzing || satelliteStatus?.status === 'error'
            ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
            : 'bg-blue-600 text-white hover:bg-blue-700'
        }`}
      >
        {isAnalyzing ? (
          <>
            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
            <span>Analyzing...</span>
          </>
        ) : (
          <>
            <Satellite className="w-4 h-4" />
            <span>Run {analysisType} Analysis</span>
          </>
        )}
      </button>

        {/* Progress Bar */}
        {isAnalyzing && (
          <div className="p-4 space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-gray-600">{getProgressText()}</span>
              <span className="text-gray-600">{Math.round(analysisProgress)}%</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                style={{ width: `${analysisProgress}%` }}
              ></div>
            </div>
          </div>
        )}

        {/* Results */}
        {(floodData || earthquakeData) && (
          <div className="p-4 border-t border-gray-200">
            <h4 className="font-medium text-gray-800 mb-3 flex items-center space-x-2">
              <CheckCircle className="w-4 h-4 text-green-600" />
              <span>Analysis Results</span>
            </h4>
            
            <div className="space-y-3 text-sm">
              {floodData && analysisType === 'flood' && (
                <>
                  <div className="bg-blue-50 p-3 rounded-lg">
                    <div className="font-medium text-blue-800 mb-2">📍 Location</div>
                    <div className="text-blue-700">
                      <div><strong>Name:</strong> {locationName}</div>
                      <div><strong>Coordinates:</strong> {floodData.location.latitude.toFixed(4)}, {floodData.location.longitude.toFixed(4)}</div>
                      <div><strong>Analysis Radius:</strong> {floodData.location.radius_km} km</div>
                    </div>
                  </div>
                  
                  <div className="bg-green-50 p-3 rounded-lg">
                    <div className="font-medium text-green-800 mb-2">📊 Flood Statistics</div>
                    <div className="text-green-700">
                      <div><strong>Flood Area:</strong> {floodData.flood_statistics.flood_area_km2.toFixed(2)} km²</div>
                      <div><strong>Analysis Date:</strong> {new Date(floodData.analysis_date).toLocaleDateString()}</div>
                    </div>
                  </div>
                  
                  <div className="bg-purple-50 p-3 rounded-lg">
                    <div className="font-medium text-purple-800 mb-2">📅 Date Range</div>
                    <div className="text-purple-700">
                      <div><strong>Pre-flood:</strong> {floodData.date_range.pre_flood}</div>
                      <div><strong>Post-flood:</strong> {floodData.date_range.post_flood}</div>
                    </div>
                  </div>
                  
                  <div className="bg-orange-50 p-3 rounded-lg">
                    <div className="font-medium text-orange-800 mb-2">⚙️ Parameters</div>
                    <div className="text-orange-700">
                      <div><strong>Threshold:</strong> {floodData.threshold_used} dB</div>
                      <div><strong>Satellite:</strong> {floodData.data_source.satellite}</div>
                      <div><strong>Resolution:</strong> {floodData.data_source.resolution}</div>
                    </div>
                  </div>
                </>
              )}
              
              {earthquakeData && analysisType === 'earthquake' && (
                <>
                  <div className="bg-blue-50 p-3 rounded-lg">
                    <div className="font-medium text-blue-800 mb-2">📍 Location</div>
                    <div className="text-blue-700">
                      <div><strong>Name:</strong> {locationName}</div>
                      <div><strong>Coordinates:</strong> {earthquakeData.location.latitude.toFixed(4)}, {earthquakeData.location.longitude.toFixed(4)}</div>
                      <div><strong>Analysis Radius:</strong> {earthquakeData.location.radius_km} km</div>
                    </div>
                  </div>
                  
                  <div className="bg-orange-50 p-3 rounded-lg">
                    <div className="font-medium text-orange-800 mb-2">🌋 Earthquake Statistics</div>
                    <div className="text-orange-700">
                      <div><strong>Max Deformation:</strong> {earthquakeData.deformation_statistics.max_deformation.toFixed(2)} cm</div>
                      <div><strong>Affected Area:</strong> {earthquakeData.deformation_statistics.affected_area_km2.toFixed(2)} km²</div>
                      <div><strong>Analysis Date:</strong> {new Date(earthquakeData.analysis_date).toLocaleDateString()}</div>
                    </div>
                  </div>
                  
                  <div className="bg-purple-50 p-3 rounded-lg">
                    <div className="font-medium text-purple-800 mb-2">📅 Date Range</div>
                    <div className="text-purple-700">
                      <div><strong>Pre-quake:</strong> {earthquakeData.date_range.pre_quake}</div>
                      <div><strong>Post-quake:</strong> {earthquakeData.date_range.post_quake}</div>
                    </div>
                  </div>
                  
                  <div className="bg-red-50 p-3 rounded-lg">
                    <div className="font-medium text-red-800 mb-2">⚙️ Parameters</div>
                    <div className="text-red-700">
                      <div><strong>Satellite:</strong> {earthquakeData.data_source.satellite}</div>
                      <div><strong>Resolution:</strong> {earthquakeData.data_source.resolution}</div>
                      <div><strong>Analysis Method:</strong> {earthquakeData.data_source.analysis_method}</div>
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>
        )}
      </div>
    </>
  );
};

export default AnalysisPanel;
