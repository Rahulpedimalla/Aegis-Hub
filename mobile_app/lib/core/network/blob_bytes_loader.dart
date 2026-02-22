import 'blob_bytes_loader_stub.dart'
    if (dart.library.html) 'blob_bytes_loader_web.dart';

Future<List<int>?> readBlobBytes(String url) => readBlobBytesImpl(url);
