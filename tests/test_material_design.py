"""
Файл: /tests/test_material_design.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Контраст общих тем и работа поиска пространств. Исполнитель: Codex.
"""
import unittest
from unittest.mock import Mock,patch
from App.app.theme import palette
from App.app.workspace import workspace_browser


def luminance(value):
    rgb=[int(value[i:i+2],16)/255 for i in (1,3,5)]
    linear=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in rgb]
    return sum(v*w for v,w in zip(linear,(.2126,.7152,.0722)))


class MaterialDesignTests(unittest.TestCase):
    def test_primary_and_body_text_contrast_in_every_theme(self):
        page=Mock(controls=[],overlay=[])
        self.addCleanup(palette.set_theme,page,'light')
        for name in palette.THEMES:
            palette.set_theme(page,name);scheme=page.theme.color_scheme
            for foreground,background in [(scheme.on_primary,scheme.primary),(scheme.on_surface,scheme.surface),
                                           (scheme.on_surface_variant,scheme.surface_container)]:
                low,high=sorted([luminance(foreground),luminance(background)])
                self.assertGreaterEqual((high+.05)/(low+.05),4.5,(name,foreground,background))

    def test_workspace_search_filters_case_insensitively_and_can_be_cleared(self):
        items=[{'id':'all','name':'Все чаты'},{'id':'a','name':'Разработка'},{'id':'b','name':'Учёба'}]
        page=Mock(width=420,height=850)
        with patch.object(workspace_browser.workspaces,'list_workspaces',return_value=items),\
             patch.object(workspace_browser.workspaces,'selected_workspace',return_value='all'),\
             patch.object(workspace_browser.workspaces,'filter_chats',return_value=[]),\
             patch.object(workspace_browser,'list_chat_items',return_value=[]):
            dialog=workspace_browser.build_workspaces_dialog(page)
            search=dialog.content.controls[2];cards=dialog.content.controls[3].controls[0]
            self.assertEqual(len(cards.controls),3)
            search.value='РАЗРАБОТКА';search.on_change(None)
            self.assertEqual(len(cards.controls),1)
            self.assertEqual(cards.controls[0].content.controls[1].content.controls[0].value,'Разработка')
            search.value='';search.on_change(None);self.assertEqual(len(cards.controls),3)

    def test_shared_widgets_use_material3_roles_and_native_motion(self):
        page=Mock(controls=[],overlay=[])
        self.addCleanup(palette.set_theme,page,'light')
        for name in palette.THEMES:
            palette.set_theme(page,name);theme=page.theme
            self.assertTrue(theme.use_material3)
            self.assertEqual(theme.slider_theme.active_track_color,theme.color_scheme.primary)
            self.assertEqual(theme.progress_indicator_theme.color,theme.color_scheme.primary)
            self.assertEqual(theme.tooltip_theme.text_style.color,theme.color_scheme.surface)
            self.assertEqual(theme.scrollbar_theme.thickness,6)
            self.assertTrue(theme.scrollbar_theme.interactive)
            self.assertEqual(page.theme_animation_style.duration,220)
            self.assertFalse(theme.slider_theme.year_2023)
