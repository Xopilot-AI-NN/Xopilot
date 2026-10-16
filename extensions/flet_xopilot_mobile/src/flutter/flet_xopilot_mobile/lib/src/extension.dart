import 'package:flet/flet.dart';
import 'flet_xopilot_mobile.dart';
import 'keyboard_viewport.dart';
import 'package:flutter/widgets.dart';

class Extension extends FletExtension {
  @override
  Widget? createWidget(Key? key,Control control) {
    return control.type=='XopilotKeyboardViewport' ? XopilotKeyboardViewport(key:key,control:control) : null;
  }

  @override
  FletService? createService(Control control) {
    return control.type == "XopilotMobile"
        ? XopilotMobileService(control: control)
        : null;
  }
}
