class DeviceContext {
  const DeviceContext({
    required this.deviceIdHash,
    required this.platform,
    required this.osVersion,
    required this.appVersion,
    required this.model,
    required this.networkType,
    required this.batteryLevel,
    required this.locale,
    required this.timezone,
  });

  final String deviceIdHash;
  final String platform;
  final String osVersion;
  final String appVersion;
  final String model;
  final String networkType;
  final double batteryLevel;
  final String locale;
  final String timezone;

  factory DeviceContext.fromJson(Map<String, dynamic> json) {
    return DeviceContext(
      deviceIdHash: (json['device_id_hash'] ?? '').toString(),
      platform: (json['platform'] ?? '').toString(),
      osVersion: (json['os_version'] ?? '').toString(),
      appVersion: (json['app_version'] ?? '').toString(),
      model: (json['model'] ?? '').toString(),
      networkType: (json['network_type'] ?? '').toString(),
      batteryLevel: double.tryParse((json['battery_level'] ?? '0').toString()) ?? 0,
      locale: (json['locale'] ?? '').toString(),
      timezone: (json['timezone'] ?? '').toString(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'device_id_hash': deviceIdHash,
      'platform': platform,
      'os_version': osVersion,
      'app_version': appVersion,
      'model': model,
      'network_type': networkType,
      'battery_level': batteryLevel,
      'locale': locale,
      'timezone': timezone,
    };
  }
}
