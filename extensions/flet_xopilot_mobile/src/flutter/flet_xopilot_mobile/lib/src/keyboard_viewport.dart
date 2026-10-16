/*
Файл: /extensions/flet_xopilot_mobile/lib/src/keyboard_viewport.dart
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Плавная высота чата на стороне Flutter при открытии и закрытии IME.
*/
import 'package:flet/flet.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter/physics.dart';

class XopilotKeyboardViewport extends StatelessWidget {
  final Control control;
  const XopilotKeyboardViewport({super.key, required this.control});

  @override
  Widget build(BuildContext context) {
    final child=control.buildWidget('content') ?? const SizedBox.shrink();
    return LayoutControl(control:control,child:LayoutBuilder(builder:(context, constraints) {
      if(!constraints.hasBoundedHeight || !constraints.hasBoundedWidth) return child;
      return _KeyboardSurface(height:constraints.maxHeight,
        width:constraints.maxWidth,
        reducedMotion:MediaQuery.disableAnimationsOf(context),child:child);
    }));
  }
}

class _KeyboardSurface extends StatefulWidget {
  final double height;
  final double width;
  final bool reducedMotion;
  final Widget child;
  const _KeyboardSurface({required this.height,required this.width,
    required this.reducedMotion,required this.child});

  @override
  State<_KeyboardSurface> createState()=>_KeyboardSurfaceState();
}

class _KeyboardSurfaceState extends State<_KeyboardSurface>
    with SingleTickerProviderStateMixin {
  late final AnimationController _height;
  // Critically damped: follow bursty IME metrics without bouncing or resetting
  // the movement to zero velocity on every Android animation frame.
  static const _spring=SpringDescription(mass:1,stiffness:1600,damping:80);

  @override
  void initState() {
    super.initState();
    _height=AnimationController.unbounded(vsync:this,value:widget.height);
  }

  @override
  void didUpdateWidget(covariant _KeyboardSurface oldWidget) {
    super.didUpdateWidget(oldWidget);
    if(widget.height==oldWidget.height && widget.reducedMotion==oldWidget.reducedMotion) return;
    if(widget.reducedMotion || widget.width!=oldWidget.width) {
      _height.value=widget.height;
    } else {
      _height.animateWith(SpringSimulation(_spring,_height.value,widget.height,
        _height.velocity,tolerance:const Tolerance(distance:.1,velocity:.1)));
    }
  }

  @override
  void dispose() {
    _height.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context)=>OverflowBox(
    alignment:Alignment.topCenter,minHeight:0,maxHeight:double.infinity,
    child:AnimatedBuilder(animation:_height,child:widget.child,
      builder:(context,child)=>SizedBox(width:widget.width,
        height:_height.value.clamp(0,double.infinity),child:child)));
}
