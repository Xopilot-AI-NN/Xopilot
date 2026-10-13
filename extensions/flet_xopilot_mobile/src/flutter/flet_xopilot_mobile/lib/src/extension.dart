import 'package:flet/flet.dart';
import 'flet_xopilot_mobile.dart';

class Extension extends FletExtension {
  @override
  FletService? createService(Control control) {
    return control.type == "XopilotMobile"
        ? XopilotMobileService(control: control)
        : null;
  }
}
