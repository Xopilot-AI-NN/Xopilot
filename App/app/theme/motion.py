"""
Файл: /App/app/theme/motion.py
Разработчик: DenBroLiik
Версия: 2.0.12
Описание: Добавляю короткие нативные переходы и читаю системное ограничение движения через Flet.
"""
import asyncio
from weakref import WeakValueDictionary
import flet as ft


async def refresh_preferences(page):
    try:
        service=page.__dict__.get('_xopilot_motion_service')
        if service is None:
            service=ft.SemanticsService();page.__dict__['_xopilot_motion_service']=service
        features=await asyncio.wait_for(service.get_accessibility_features(),timeout=2)
        reduced=features.disable_animations or features.reduce_motion
        page.__dict__['_xopilot_reduce_motion']=bool(reduced)
        for host in list(page.__dict__.get('_xopilot_motion_hosts',{}).values()):
            host.duration=0 if reduced else 220;host.reverse_duration=0 if reduced else 120
        for panel in list(page.__dict__.get('_xopilot_motion_panels',{}).values()):
            panel.animate_opacity=ft.Animation(0 if reduced else 180,ft.AnimationCurve.EASE_OUT_CUBIC)
        page.theme_animation_style=ft.AnimationStyle(duration=0 if reduced else 220,curve=ft.AnimationCurve.EASE_IN_OUT_CUBIC)
        page.update()
        return True
    except Exception:
        return False


def switcher(page,content,*,height=None):
    reduced=page.__dict__.get('_xopilot_reduce_motion',False)
    host=ft.AnimatedSwitcher(content=content,height=height,duration=0 if reduced else 220,
        reverse_duration=0 if reduced else 120,transition=ft.AnimatedSwitcherTransition.FADE,
        switch_in_curve=ft.AnimationCurve.EASE_OUT_CUBIC,switch_out_curve=ft.AnimationCurve.EASE_IN)
    registry=page.__dict__.setdefault('_xopilot_motion_hosts',WeakValueDictionary());registry[id(host)]=host
    return host


def panel(page,**kwargs):
    reduced=page.__dict__.get('_xopilot_reduce_motion',False)
    result=ft.Container(animate_opacity=ft.Animation(0 if reduced else 180,ft.AnimationCurve.EASE_OUT_CUBIC),**kwargs)
    registry=page.__dict__.setdefault('_xopilot_motion_panels',WeakValueDictionary());registry[id(result)]=result
    return result
