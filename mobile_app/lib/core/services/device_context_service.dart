import 'package:battery_plus/battery_plus.dart';
import 'package:device_info_plus/device_info_plus.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:universal_io/io.dart';

import '../../shared/models/device_context.dart';
import '../../shared/models/media_attachment.dart';
import 'connectivity_service.dart';

class DeviceContextService {
  DeviceContextService({
    DeviceInfoPlugin? deviceInfoPlugin,
    PackageInfo? packageInfo,
    ConnectivityService? connectivityService,
    Battery? battery,
  })  : _deviceInfoPlugin = deviceInfoPlugin ?? DeviceInfoPlugin(),
        _packageInfo = packageInfo,
        _connectivityService = connectivityService ?? ConnectivityService(),
        _battery = battery ?? Battery();

  final DeviceInfoPlugin _deviceInfoPlugin;
  final PackageInfo? _packageInfo;
  final ConnectivityService _connectivityService;
  final Battery _battery;

  Future<DeviceContext> collect() async {
    final pkg = _packageInfo ?? await PackageInfo.fromPlatform();
    final networkType = await _connectivityService.currentNetworkType();
    final batteryLevel = await _safeBatteryLevel();
    final locale = WidgetsBinding.instance.platformDispatcher.locale.toLanguageTag();
    final timezone = DateTime.now().timeZoneName;

    if (kIsWeb) {
      final info = await _deviceInfoPlugin.webBrowserInfo;
      return DeviceContext(
        deviceIdHash: sha256Text('${info.vendor}-${info.userAgent}'),
        platform: 'web',
        osVersion: info.appVersion ?? 'web',
        appVersion: '${pkg.version}+${pkg.buildNumber}',
        model: info.browserName.name,
        networkType: networkType,
        batteryLevel: batteryLevel,
        locale: locale,
        timezone: timezone,
      );
    }

    if (Platform.isAndroid) {
      final info = await _deviceInfoPlugin.androidInfo;
      return DeviceContext(
        deviceIdHash: sha256Text(info.id),
        platform: 'android',
        osVersion: info.version.release,
        appVersion: '${pkg.version}+${pkg.buildNumber}',
        model: info.model,
        networkType: networkType,
        batteryLevel: batteryLevel,
        locale: locale,
        timezone: timezone,
      );
    }

    if (Platform.isIOS) {
      final info = await _deviceInfoPlugin.iosInfo;
      return DeviceContext(
        deviceIdHash: sha256Text(info.identifierForVendor ?? 'ios-device'),
        platform: 'ios',
        osVersion: info.systemVersion,
        appVersion: '${pkg.version}+${pkg.buildNumber}',
        model: info.utsname.machine,
        networkType: networkType,
        batteryLevel: batteryLevel,
        locale: locale,
        timezone: timezone,
      );
    }

    return DeviceContext(
      deviceIdHash: sha256Text('unsupported-device'),
      platform: Platform.operatingSystem,
      osVersion: Platform.operatingSystemVersion,
      appVersion: '${pkg.version}+${pkg.buildNumber}',
      model: 'unknown',
      networkType: networkType,
      batteryLevel: batteryLevel,
      locale: locale,
      timezone: timezone,
    );
  }

  Future<double> _safeBatteryLevel() async {
    try {
      return (await _battery.batteryLevel).toDouble() / 100;
    } catch (_) {
      return 0.0;
    }
  }
}
