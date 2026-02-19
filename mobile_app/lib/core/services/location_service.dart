import 'package:geolocator/geolocator.dart';

import '../../shared/models/location_point.dart';

class LocationService {
  Future<LocationPoint> getCurrentLocation() async {
    try {
      final serviceEnabled = await Geolocator.isLocationServiceEnabled();
      if (!serviceEnabled) {
        return const LocationPoint(latitude: 0, longitude: 0, accuracyMeters: 0);
      }

      var permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
      }
      if (permission == LocationPermission.denied || permission == LocationPermission.deniedForever) {
        return const LocationPoint(latitude: 0, longitude: 0, accuracyMeters: 0);
      }

      final position = await Geolocator.getCurrentPosition(
        desiredAccuracy: LocationAccuracy.high,
        timeLimit: const Duration(seconds: 8),
      );
      return LocationPoint(
        latitude: position.latitude,
        longitude: position.longitude,
        accuracyMeters: position.accuracy,
      );
    } catch (_) {
      return const LocationPoint(latitude: 0, longitude: 0, accuracyMeters: 0);
    }
  }
}
