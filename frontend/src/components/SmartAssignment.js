import React, { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import {
    MapPin,
    Clock,
    CheckCircle,
    XCircle,
    AlertTriangle,
    Building2,
    User,
    Layers
} from 'lucide-react';
import toast from 'react-hot-toast';
import { useAuth } from '../contexts/AuthContext';

const SmartAssignment = ({ sosId, onAssignmentUpdate }) => {
    const { user } = useAuth();
    const isResponder = user?.role === 'responder';
    const [assignment, setAssignment] = useState(null);
    const [loading, setLoading] = useState(true);
    const [accepting, setAccepting] = useState(false);
    const [rejecting, setRejecting] = useState(false);
    const [assigning, setAssigning] = useState(false);
    const [completing, setCompleting] = useState(false);
    const [timeRemaining, setTimeRemaining] = useState(null);
    const [estimatedCompletion, setEstimatedCompletion] = useState('');
    const [resolutionNotes, setResolutionNotes] = useState('');

    const fetchSmartAssignment = useCallback(async () => {
        if (!sosId) return;
        try {
            setLoading(true);
            const response = await axios.get(`/api/emergency/smart-assignment?sos_id=${sosId}`);
            setAssignment(response.data);
            const initialRemaining = response.data?.response_metrics?.acceptance_time_remaining;
            setTimeRemaining(initialRemaining ?? null);
        } catch (error) {
            console.error('Error fetching smart assignment:', error);
            toast.error('Failed to fetch assignment recommendations');
        } finally {
            setLoading(false);
        }
    }, [sosId]);

    useEffect(() => {
        fetchSmartAssignment();
    }, [fetchSmartAssignment]);

    useEffect(() => {
        if (!assignment || assignment?.sos_request?.status !== 'Pending Assignment' || timeRemaining == null) {
            return;
        }
        const timer = setInterval(() => {
            setTimeRemaining((prev) => {
                if (prev == null) return prev;
                if (prev <= 1) return 0;
                return prev - 1;
            });
        }, 1000);
        return () => clearInterval(timer);
    }, [assignment, timeRemaining]);

    const recommendedOrganization = assignment?.recommended_assignment?.organization;
    const recommendedStaff = assignment?.recommended_assignment?.staff;
    const recommendedDivision = assignment?.recommended_assignment?.division;
    const canRespondToTicket = Boolean(assignment?.user_permissions?.can_accept_reject_complete);
    const status = assignment?.sos_request?.status;
    const isPending = status === 'Pending';
    const isPendingAssignment = status === 'Pending Assignment';
    const isInProgress = status === 'In Progress';

    const scoreBadgeClass = useMemo(() => {
        const score = assignment?.assignment_score || 0;
        if (score >= 80) return 'bg-green-100 text-green-800';
        if (score >= 60) return 'bg-yellow-100 text-yellow-800';
        return 'bg-red-100 text-red-800';
    }, [assignment]);

    const formatTime = (seconds) => {
        const sec = Math.max(0, Math.floor(seconds || 0));
        const minutes = Math.floor(sec / 60);
        const remainingSeconds = sec % 60;
        return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
    };

    const prepareAssignmentWindow = async () => {
        if (!recommendedOrganization) {
            toast.error('No recommended organization available');
            return false;
        }
        if (!isPending) return true;

        try {
            setAssigning(true);
            await axios.post('/api/emergency/assign-emergency', {
                sos_id: sosId,
                organization_id: recommendedOrganization.id,
                staff_id: recommendedStaff?.id || null,
                division_id: recommendedDivision?.id || null
            });
            await fetchSmartAssignment();
            return true;
        } catch (error) {
            console.error('Error assigning emergency:', error);
            toast.error(error.response?.data?.detail || 'Failed to start assignment window');
            return false;
        } finally {
            setAssigning(false);
        }
    };

    const acceptAssignment = async () => {
        if (!estimatedCompletion) {
            toast.error('Please provide estimated completion time');
            return;
        }
        const ready = await prepareAssignmentWindow();
        if (!ready) return;

        try {
            setAccepting(true);
            await axios.post('/api/emergency/accept-assignment', {
                sos_id: sosId,
                organization_id: recommendedOrganization.id,
                estimated_completion: estimatedCompletion
            });
            toast.success('Assignment accepted successfully');
            await fetchSmartAssignment();
            onAssignmentUpdate && onAssignmentUpdate();
        } catch (error) {
            console.error('Error accepting assignment:', error);
            toast.error(error.response?.data?.detail || 'Failed to accept assignment');
        } finally {
            setAccepting(false);
        }
    };

    const rejectAssignment = async () => {
        const ready = await prepareAssignmentWindow();
        if (!ready) return;

        try {
            setRejecting(true);
            await axios.post('/api/emergency/reject-assignment', {
                sos_id: sosId,
                organization_id: recommendedOrganization.id,
                reason: 'Organization unavailable'
            });
            toast.success('Assignment rejected. Finding next best team...');
            await fetchSmartAssignment();
            onAssignmentUpdate && onAssignmentUpdate();
        } catch (error) {
            console.error('Error rejecting assignment:', error);
            toast.error(error.response?.data?.detail || 'Failed to reject assignment');
        } finally {
            setRejecting(false);
        }
    };

    const completeEmergency = async () => {
        try {
            setCompleting(true);
            await axios.post('/api/emergency/complete-emergency', {
                sos_id: sosId,
                resolution_notes: resolutionNotes || 'Resolved by response team'
            });
            toast.success('Emergency marked as completed');
            setResolutionNotes('');
            await fetchSmartAssignment();
            onAssignmentUpdate && onAssignmentUpdate();
        } catch (error) {
            console.error('Error completing emergency:', error);
            toast.error(error.response?.data?.detail || 'Failed to complete emergency');
        } finally {
            setCompleting(false);
        }
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center p-8">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                <span className="ml-2">Loading assignment recommendations...</span>
            </div>
        );
    }

    if (!assignment) {
        return <div className="text-center p-8 text-gray-500">No assignment recommendations available</div>;
    }

    return (
        <div className="bg-white rounded-lg shadow-lg p-6">
            <div className="flex items-center justify-between mb-6">
                <h3 className="text-xl font-semibold text-gray-800">Smart Assignment Recommendations</h3>
                <div className="flex items-center space-x-2">
                    <span className="text-sm text-gray-600">Score:</span>
                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${scoreBadgeClass}`}>
                        {assignment.assignment_score || 0}/100
                    </span>
                </div>
            </div>

            {recommendedOrganization && (
                <div className="mb-6 p-4 border border-gray-200 rounded-lg">
                    <div className="flex items-center justify-between mb-4">
                        <div className="flex items-center space-x-3">
                            <Building2 className="h-6 w-6 text-blue-600" />
                            <div>
                                <h4 className="font-medium text-gray-800">{recommendedOrganization.name}</h4>
                                <p className="text-sm text-gray-600">
                                    {recommendedOrganization.type} - {recommendedOrganization.category}
                                </p>
                            </div>
                        </div>
                        <div className="text-right">
                            <div className="text-sm text-gray-600">Score</div>
                            <div className="text-lg font-semibold text-blue-600">{recommendedOrganization.score}</div>
                        </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4 mb-4">
                        <div className="flex items-center space-x-2">
                            <MapPin className="h-4 w-4 text-gray-500" />
                            <span className="text-sm text-gray-600">{recommendedOrganization.contact_person || 'N/A'}</span>
                        </div>
                        <div className="flex items-center space-x-2">
                            <Clock className="h-4 w-4 text-gray-500" />
                            <span className="text-sm text-gray-600">
                                {recommendedOrganization.estimated_response_time || 'N/A'} min
                            </span>
                        </div>
                    </div>

                    {(isPendingAssignment || isPending) && (
                        <div className="border-t pt-4">
                            <div className="flex items-center justify-between mb-4">
                                <div className="flex items-center space-x-2 text-orange-600">
                                    <AlertTriangle className="h-4 w-4" />
                                    <span className="text-sm font-medium">
                                        {isPendingAssignment
                                            ? `Time remaining: ${formatTime(timeRemaining || 0)}`
                                            : 'Assignment not started'}
                                    </span>
                                </div>
                                {isPending && (
                                    <button
                                        onClick={prepareAssignmentWindow}
                                        disabled={assigning}
                                        className="px-3 py-1 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
                                    >
                                        {assigning ? 'Starting...' : 'Start Window'}
                                    </button>
                                )}
                            </div>

                            <div className="flex items-center space-x-4 mb-4">
                                <input
                                    type="datetime-local"
                                    value={estimatedCompletion}
                                    onChange={(e) => setEstimatedCompletion(e.target.value)}
                                    className="px-3 py-2 border border-gray-300 rounded-md text-sm w-full"
                                    placeholder="Estimated completion time"
                                />
                            </div>

                            {canRespondToTicket ? (
                                <div className="flex space-x-3">
                                    <button
                                        onClick={acceptAssignment}
                                        disabled={accepting || assigning || !estimatedCompletion}
                                        className="flex items-center space-x-2 px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
                                    >
                                        <CheckCircle className="h-4 w-4" />
                                        <span>{accepting ? 'Accepting...' : 'Accept Assignment'}</span>
                                    </button>
                                    <button
                                        onClick={rejectAssignment}
                                        disabled={rejecting || assigning}
                                        className="flex items-center space-x-2 px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed"
                                    >
                                        <XCircle className="h-4 w-4" />
                                        <span>{rejecting ? 'Rejecting...' : 'Reject Assignment'}</span>
                                    </button>
                                </div>
                            ) : (
                                <div className="text-sm text-amber-700 bg-amber-50 border border-amber-200 px-3 py-2 rounded-md">
                                    {isResponder
                                        ? 'Only the assigned responder staff can accept or reject this emergency.'
                                        : 'Admin can assign and monitor. Only assigned responder staff can accept or reject.'}
                                </div>
                            )}
                        </div>
                    )}

                    {isInProgress && (
                        <div className="border-t pt-4">
                            {canRespondToTicket ? (
                                <div className="space-y-3">
                                    <textarea
                                        value={resolutionNotes}
                                        onChange={(e) => setResolutionNotes(e.target.value)}
                                        placeholder="Resolution notes"
                                        rows={2}
                                        className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                                    />
                                    <button
                                        onClick={completeEmergency}
                                        disabled={completing}
                                        className="flex items-center space-x-2 px-4 py-2 bg-emerald-600 text-white rounded-md hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed"
                                    >
                                        <CheckCircle className="h-4 w-4" />
                                        <span>{completing ? 'Completing...' : 'Mark as Completed'}</span>
                                    </button>
                                </div>
                            ) : (
                                <div className="text-sm text-amber-700 bg-amber-50 border border-amber-200 px-3 py-2 rounded-md">
                                    {isResponder
                                        ? 'Only the assigned responder staff can mark this emergency as completed.'
                                        : 'Mark as completed is available only to the assigned responder staff.'}
                                </div>
                            )}
                        </div>
                    )}
                </div>
            )}

            {recommendedStaff && (
                <div className="mb-6 p-4 border border-gray-200 rounded-lg">
                    <div className="flex items-center justify-between mb-4">
                        <div className="flex items-center space-x-3">
                            <User className="h-6 w-6 text-green-600" />
                            <div>
                                <h4 className="font-medium text-gray-800">{recommendedStaff.name}</h4>
                                <p className="text-sm text-gray-600">
                                    {recommendedStaff.role} - {recommendedStaff.skills}
                                </p>
                            </div>
                        </div>
                        <div className="text-right">
                            <div className="text-sm text-gray-600">Score</div>
                            <div className="text-lg font-semibold text-green-600">{recommendedStaff.score}</div>
                        </div>
                    </div>
                </div>
            )}

            {recommendedDivision && (
                <div className="mb-6 p-4 border border-gray-200 rounded-lg">
                    <div className="flex items-center justify-between mb-4">
                        <div className="flex items-center space-x-3">
                            <Layers className="h-6 w-6 text-purple-600" />
                            <div>
                                <h4 className="font-medium text-gray-800">{recommendedDivision.name}</h4>
                                <p className="text-sm text-gray-600">{recommendedDivision.type}</p>
                            </div>
                        </div>
                        <div className="text-right">
                            <div className="text-sm text-gray-600">Score</div>
                            <div className="text-lg font-semibold text-purple-600">{recommendedDivision.score}</div>
                        </div>
                    </div>
                </div>
            )}

            <div className="mt-6 p-4 bg-gray-50 rounded-lg">
                <h4 className="font-medium text-gray-800 mb-2">Assignment Status</h4>
                <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                        <span className="text-gray-600">Current Status:</span>
                        <span className={`ml-2 px-2 py-1 rounded-full text-xs font-medium ${
                            status === 'In Progress'
                                ? 'bg-green-100 text-green-800'
                                : status === 'Pending Assignment'
                                ? 'bg-orange-100 text-orange-800'
                                : 'bg-gray-100 text-gray-800'
                        }`}>
                            {status}
                        </span>
                    </div>
                    <div>
                        <span className="text-gray-600">Priority:</span>
                        <span className="ml-2 font-medium text-gray-800">{assignment.sos_request.priority}</span>
                    </div>
                    <div>
                        <span className="text-gray-600">People Affected:</span>
                        <span className="ml-2 font-medium text-gray-800">{assignment.sos_request.people}</span>
                    </div>
                    <div>
                        <span className="text-gray-600">Category:</span>
                        <span className="ml-2 font-medium text-gray-800">{assignment.sos_request.category}</span>
                    </div>
                    <div>
                        <span className="text-gray-600">AI Division Focus:</span>
                        <span className="ml-2 font-medium text-gray-800">
                            {assignment?.ai_assignment_context?.desired_division_type || 'N/A'}
                        </span>
                    </div>
                    <div>
                        <span className="text-gray-600">Assignment Basis:</span>
                        <span className="ml-2 font-medium text-gray-800">
                            {assignment?.ai_assignment_context?.basis || 'rules'}
                        </span>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default SmartAssignment;
