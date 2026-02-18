import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
    AlertTriangle, 
    Clock, 
    CheckCircle, 
    XCircle, 
    Users,
    RefreshCw
} from 'lucide-react';
import toast from 'react-hot-toast';
import SmartAssignment from '../components/SmartAssignment';

const EmergencyResponse = () => {
    const [emergencies, setEmergencies] = useState([]);
    const [loading, setLoading] = useState(true);
    const [selectedEmergency, setSelectedEmergency] = useState(null);
    const [showAssignment, setShowAssignment] = useState(false);

    useEffect(() => {
        fetchEmergencySummary();
        const interval = setInterval(fetchEmergencySummary, 30000); // Refresh every 30 seconds
        return () => clearInterval(interval);
    }, []);

    const fetchEmergencySummary = async () => {
        try {
            setLoading(true);
            const response = await axios.get('/api/emergency/emergency-summary');
            setEmergencies(response.data.emergencies);
        } catch (error) {
            console.error('Error fetching emergency summary:', error);
            toast.error('Failed to fetch emergency summary');
        } finally {
            setLoading(false);
        }
    };

    const getStatusColor = (status) => {
        switch (status) {
            case 'Pending':
                return 'bg-yellow-100 text-yellow-800';
            case 'Pending Assignment':
                return 'bg-orange-100 text-orange-800';
            case 'In Progress':
                return 'bg-blue-100 text-blue-800';
            case 'Done':
                return 'bg-green-100 text-green-800';
            default:
                return 'bg-gray-100 text-gray-800';
        }
    };

    const getPriorityColor = (priority) => {
        switch (priority) {
            case 5:
                return 'bg-red-100 text-red-800';
            case 4:
                return 'bg-orange-100 text-orange-800';
            case 3:
                return 'bg-yellow-100 text-yellow-800';
            default:
                return 'bg-gray-100 text-gray-800';
        }
    };

    const handleEmergencyClick = (emergency) => {
        setSelectedEmergency(emergency);
        setShowAssignment(true);
    };

    const handleAssignmentUpdate = () => {
        fetchEmergencySummary();
        setShowAssignment(false);
        setSelectedEmergency(null);
    };

    const formatTime = (seconds) => {
        if (!seconds) return 'N/A';
        const minutes = Math.floor(seconds / 60);
        const remainingSeconds = seconds % 60;
        return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center p-8">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                <span className="ml-2">Loading emergency response data...</span>
            </div>
        );
    }

    return (
        <div className="p-6">
            <div className="flex items-center justify-between mb-6">
                <h1 className="text-2xl font-bold text-gray-800">Emergency Response Dashboard</h1>
                <button
                    onClick={fetchEmergencySummary}
                    className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
                >
                    <RefreshCw className="h-4 w-4" />
                    <span>Refresh</span>
                </button>
            </div>

            {/* Summary Cards */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
                <div className="bg-white p-6 rounded-lg shadow-md">
                    <div className="flex items-center">
                        <AlertTriangle className="h-8 w-8 text-red-600" />
                        <div className="ml-4">
                            <p className="text-sm font-medium text-gray-600">Total Active</p>
                            <p className="text-2xl font-bold text-gray-900">{emergencies.length}</p>
                        </div>
                    </div>
                </div>

                <div className="bg-white p-6 rounded-lg shadow-md">
                    <div className="flex items-center">
                        <Clock className="h-8 w-8 text-orange-600" />
                        <div className="ml-4">
                            <p className="text-sm font-medium text-gray-600">Pending Assignment</p>
                            <p className="text-2xl font-bold text-gray-900">
                                {emergencies.filter(e => e.status === 'Pending Assignment').length}
                            </p>
                        </div>
                    </div>
                </div>

                <div className="bg-white p-6 rounded-lg shadow-md">
                    <div className="flex items-center">
                        <CheckCircle className="h-8 w-8 text-blue-600" />
                        <div className="ml-4">
                            <p className="text-sm font-medium text-gray-600">In Progress</p>
                            <p className="text-2xl font-bold text-gray-900">
                                {emergencies.filter(e => e.status === 'In Progress').length}
                            </p>
                        </div>
                    </div>
                </div>

                <div className="bg-white p-6 rounded-lg shadow-md">
                    <div className="flex items-center">
                        <XCircle className="h-8 w-8 text-red-600" />
                        <div className="ml-4">
                            <p className="text-sm font-medium text-gray-600">Overdue</p>
                            <p className="text-2xl font-bold text-gray-900">
                                {emergencies.filter(e => e.is_overdue).length}
                            </p>
                        </div>
                    </div>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Emergency List */}
                <div className="lg:col-span-2">
                    <div className="bg-white rounded-lg shadow-md">
                        <div className="p-6 border-b border-gray-200">
                            <h2 className="text-lg font-semibold text-gray-800">Active Emergencies</h2>
                        </div>
                        <div className="divide-y divide-gray-200">
                            {emergencies.length === 0 ? (
                                <div className="p-6 text-center text-gray-500">
                                    No active emergencies
                                </div>
                            ) : (
                                emergencies.map((emergency) => (
                                    <div
                                        key={emergency.id}
                                        className={`p-6 cursor-pointer hover:bg-gray-50 transition-colors ${
                                            selectedEmergency?.id === emergency.id ? 'bg-blue-50 border-l-4 border-blue-500' : ''
                                        }`}
                                        onClick={() => handleEmergencyClick(emergency)}
                                    >
                                        <div className="flex items-start justify-between">
                                            <div className="flex-1">
                                                <div className="flex items-center space-x-3 mb-2">
                                                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(emergency.status)}`}>
                                                        {emergency.status}
                                                    </span>
                                                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${getPriorityColor(emergency.priority)}`}>
                                                        Priority {emergency.priority}
                                                    </span>
                                                </div>
                                                
                                                <h3 className="font-medium text-gray-800 mb-1">
                                                    {emergency.category}
                                                </h3>
                                                
                                                <p className="text-sm text-gray-600 mb-2">
                                                    {emergency.place}
                                                </p>
                                                
                                                <div className="flex items-center space-x-4 text-sm text-gray-500">
                                                    <div className="flex items-center space-x-1">
                                                        <Users className="h-4 w-4" />
                                                        <span>{emergency.people} people</span>
                                                    </div>
                                                    <div className="flex items-center space-x-1">
                                                        <Clock className="h-4 w-4" />
                                                        <span>{emergency.age_hours}h ago</span>
                                                    </div>
                                                </div>
                                            </div>
                                            
                                            <div className="text-right">
                                                {emergency.acceptance_time_remaining && (
                                                    <div className="text-sm text-orange-600 font-medium">
                                                        {formatTime(emergency.acceptance_time_remaining)}
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                        
                                        <div className="mt-4 pt-4 border-t border-gray-100">
                                            <div className="grid grid-cols-2 gap-4 text-sm">
                                                <div>
                                                    <span className="text-gray-500">Organization:</span>
                                                    <span className="ml-2 font-medium text-gray-700">
                                                        {emergency.assigned_organization}
                                                    </span>
                                                </div>
                                                <div>
                                                    <span className="text-gray-500">Staff:</span>
                                                    <span className="ml-2 font-medium text-gray-700">
                                                        {emergency.assigned_staff}
                                                    </span>
                                                </div>
                                                <div>
                                                    <span className="text-gray-500">Division:</span>
                                                    <span className="ml-2 font-medium text-gray-700">
                                                        {emergency.assigned_division}
                                                    </span>
                                                </div>
                                                <div>
                                                    <span className="text-gray-500">Overdue:</span>
                                                    <span className={`ml-2 font-medium ${
                                                        emergency.is_overdue ? 'text-red-600' : 'text-green-600'
                                                    }`}>
                                                        {emergency.is_overdue ? 'Yes' : 'No'}
                                                    </span>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                ))
                            )}
                        </div>
                    </div>
                </div>

                {/* Assignment Panel */}
                <div className="lg:col-span-1">
                    {showAssignment && selectedEmergency ? (
                        <div className="sticky top-6">
                            <SmartAssignment 
                                sosId={selectedEmergency.id} 
                                onAssignmentUpdate={handleAssignmentUpdate}
                            />
                        </div>
                    ) : (
                        <div className="bg-white rounded-lg shadow-md p-6">
                            <div className="text-center text-gray-500">
                                <AlertTriangle className="h-12 w-12 mx-auto mb-4 text-gray-300" />
                                <h3 className="text-lg font-medium text-gray-600 mb-2">
                                    No Emergency Selected
                                </h3>
                                <p className="text-sm text-gray-500">
                                    Click on an emergency from the list to view assignment details and manage response teams.
                                </p>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default EmergencyResponse;
