import 'package:connectivity_plus/connectivity_plus.dart';

class ConnectivityService {
  ConnectivityService({Connectivity? connectivity})
      : _connectivity = connectivity ?? Connectivity();

  final Connectivity _connectivity;

  Future<bool> hasNetwork() async {
    final result = await _connectivity.checkConnectivity();
    return !result.contains(ConnectivityResult.none);
  }

  Future<String> currentNetworkType() async {
    final result = await _connectivity.checkConnectivity();
    if (result.isEmpty) {
      return 'unknown';
    }
    if (result.contains(ConnectivityResult.wifi)) {
      return 'wifi';
    }
    if (result.contains(ConnectivityResult.mobile)) {
      return 'cellular';
    }
    if (result.contains(ConnectivityResult.ethernet)) {
      return 'ethernet';
    }
    return result.first.name;
  }
}
