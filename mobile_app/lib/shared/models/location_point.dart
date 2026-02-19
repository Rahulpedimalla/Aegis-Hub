class LocationPoint {
  const LocationPoint({
    required this.latitude,
    required this.longitude,
    required this.accuracyMeters,
  });

  final double latitude;
  final double longitude;
  final double accuracyMeters;

  factory LocationPoint.fromJson(Map<String, dynamic> json) {
    return LocationPoint(
      latitude: double.tryParse((json['latitude'] ?? json['lat'] ?? '0').toString()) ?? 0,
      longitude: double.tryParse((json['longitude'] ?? json['lng'] ?? '0').toString()) ?? 0,
      accuracyMeters: double.tryParse((json['location_accuracy_m'] ?? '0').toString()) ?? 0,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'latitude': latitude,
      'longitude': longitude,
      'location_accuracy_m': accuracyMeters,
    };
  }
}
