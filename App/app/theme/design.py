"""
Файл: /App/app/theme/design.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Единая тема Material 3 / Xopilot для навигации, форм и действий.
"""
import flet as ft


def material_theme():
    from .palette import color, is_dark_theme
    accent=color('#087f8c');ink=color('#123b43');muted=color('#47747a')
    surface=color('#eafffa');raised=color('#f3fffc');edge=color('#b9eee4')
    dark=is_dark_theme()
    on_accent='#00363c' if dark else '#ffffff'
    scheme=ft.ColorScheme(primary=accent,on_primary=on_accent,
        primary_container=color('#dff8f3'),on_primary_container=ink,
        secondary=muted,on_secondary=on_accent,secondary_container=color('#c9f1e9'),on_secondary_container=ink,
        tertiary='#b9b0ff' if dark else '#65558f',on_tertiary='#302755' if dark else '#ffffff',
        tertiary_container='#363250' if dark else '#eee7ff',on_tertiary_container='#e9ddff' if dark else '#302755',
        surface=surface,on_surface=ink,on_surface_variant=muted,surface_tint=accent,
        surface_container_low=surface,surface_container=raised,surface_container_high=color('#dff8f3'),
        surface_container_highest=color('#c9f1e9'),surface_container_lowest=color('#ffffff'),
        outline=color('#a8ddd7'),outline_variant=edge,
        error=color('#b3261e'),on_error='#581b19' if dark else '#ffffff',error_container=color('#ffe9e9'),on_error_container=color('#b3261e'))
    return ft.Theme(use_material3=True,color_scheme_seed='#008b98',color_scheme=scheme,font_family='Google Sans',
        scaffold_bgcolor=color('#b3f2ff'),canvas_color=surface,divider_color=edge,
        disabled_color=ft.Colors.with_opacity(.45,muted),
        hover_color=ft.Colors.with_opacity(.08,accent),
        focus_color=ft.Colors.with_opacity(.12,accent),
        scrollbar_theme=ft.ScrollbarTheme(thickness=6,radius=8,min_thumb_length=36,
            interactive=True,cross_axis_margin=3,
            thumb_color={ft.ControlState.DEFAULT:ft.Colors.with_opacity(.45,muted),
                         ft.ControlState.HOVERED:accent,ft.ControlState.DRAGGED:accent}),
        slider_theme=ft.SliderTheme(active_track_color=accent,inactive_track_color=edge,
            thumb_color=accent,overlay_color=ft.Colors.with_opacity(.12,accent),
            value_indicator_color=accent,value_indicator_text_style=ft.TextStyle(color=on_accent),
            track_height=6,track_gap=4,year_2023=False),
        progress_indicator_theme=ft.ProgressIndicatorTheme(color=accent,
            circular_track_color=edge,linear_track_color=edge,linear_min_height=6,
            border_radius=6,track_gap=4,year_2023=False),
        tooltip_theme=ft.TooltipTheme(wait_duration=500,show_duration=3500,
            padding=ft.Padding.symmetric(horizontal=12,vertical=8),
            decoration=ft.BoxDecoration(bgcolor=ink,border_radius=12),
            text_style=ft.TextStyle(size=12,color=surface)),
        card_theme=ft.CardTheme(color=raised,elevation=0,
            shape=ft.RoundedRectangleBorder(radius=24),margin=0),
        bottom_sheet_theme=ft.BottomSheetTheme(bgcolor=surface,elevation=0,
            shape=ft.RoundedRectangleBorder(radius=28),show_drag_handle=True,
            drag_handle_color=muted,clip_behavior=ft.ClipBehavior.ANTI_ALIAS),
        list_tile_theme=ft.ListTileTheme(icon_color=accent,text_color=ink,
            selected_color=ink,selected_tile_color=color('#dff8f3'),min_height=56,
            shape=ft.RoundedRectangleBorder(radius=16),
            content_padding=ft.Padding.symmetric(horizontal=16,vertical=6),
            title_text_style=ft.TextStyle(size=14,weight=ft.FontWeight.W_500,color=ink),
            subtitle_text_style=ft.TextStyle(size=12,color=muted)),
        chip_theme=ft.ChipTheme(bgcolor=raised,selected_color=color('#c9f1e9'),
            check_color=accent,delete_icon_color=muted,elevation=0,
            shape=ft.RoundedRectangleBorder(radius=12),border_side=ft.BorderSide(1,edge),
            label_text_style=ft.TextStyle(size=13,color=ink),
            padding=ft.Padding.symmetric(horizontal=10,vertical=8)),
        segmented_button_theme=ft.SegmentedButtonTheme(style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=18),side=ft.BorderSide(1,edge),
            padding=ft.Padding.symmetric(horizontal=14,vertical=12),
            color={ft.ControlState.DEFAULT:muted,ft.ControlState.SELECTED:ink},
            bgcolor={ft.ControlState.DEFAULT:raised,ft.ControlState.SELECTED:color('#c9f1e9')},
            overlay_color=ft.Colors.with_opacity(.08,accent),animation_duration=180)),
        radio_theme=ft.RadioTheme(fill_color={ft.ControlState.SELECTED:accent,
            ft.ControlState.DEFAULT:muted},overlay_color=ft.Colors.with_opacity(.10,accent)),
        text_theme=ft.TextTheme(
            title_large=ft.TextStyle(size=22,weight=ft.FontWeight.W_600,color=ink),
            title_medium=ft.TextStyle(size=16,weight=ft.FontWeight.W_600,color=ink),
            body_large=ft.TextStyle(size=15,color=ink),body_medium=ft.TextStyle(size=14,color=ink),
            body_small=ft.TextStyle(size=12,color=muted),label_large=ft.TextStyle(size=14,weight=ft.FontWeight.W_500)),
        dialog_theme=ft.DialogTheme(bgcolor=surface,elevation=0,
            shape=ft.RoundedRectangleBorder(radius=28),
            title_text_style=ft.TextStyle(size=22,weight=ft.FontWeight.W_600,color=ink),
            content_text_style=ft.TextStyle(size=14,color=ink)),
        icon_button_theme=ft.IconButtonTheme(style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=16),
            overlay_color=ft.Colors.with_opacity(.10,accent))),
        switch_theme=ft.SwitchTheme(
            thumb_color={ft.ControlState.SELECTED:on_accent,ft.ControlState.DEFAULT:muted},
            track_color={ft.ControlState.SELECTED:accent,ft.ControlState.DEFAULT:color('#dff8f3')},
            track_outline_color={ft.ControlState.SELECTED:ft.Colors.TRANSPARENT,ft.ControlState.DEFAULT:edge}),
        checkbox_theme=ft.CheckboxTheme(shape=ft.RoundedRectangleBorder(radius=5),
            fill_color={ft.ControlState.SELECTED:accent},check_color=on_accent,
            border_side=ft.BorderSide(1.5,muted)))
