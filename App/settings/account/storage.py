"""
Файл: /App/settings/account/storage.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Хранилище Material 3 / Xopilot: материалы, копии и освобождение места.
"""
import asyncio
import json
from datetime import datetime
from pathlib import Path
import flet as ft
try:
    from ...services import storage,cloud_account,profile,cloud_sync,navigation
    from ...app.theme.palette import color, modern_input, apply_palette
    from ...app.materials.material_viewer import open_material, export_material
    from ...services.platforms import compact_layout, fit_dialog
    from ...app.menu.buttons.actions import action_button
except ImportError:
    from services import storage,cloud_account,profile,cloud_sync,navigation
    from app.theme.palette import color, modern_input, apply_palette
    from app.materials.material_viewer import open_material, export_material
    from services.platforms import compact_layout, fit_dialog
    from app.menu.buttons.actions import action_button


def open_storage(page, initial_mode='local'):
    content=ft.ListView(expand=True,spacing=10,padding=ft.Padding.only(right=6),
        animate_opacity=ft.Animation(180,ft.AnimationCurve.EASE_OUT_CUBIC),
        animate_offset=ft.Animation(220,ft.AnimationCurve.EASE_OUT_CUBIC))
    status=ft.Text('',size=12,color=color('#47747a'))
    refresh_lock=asyncio.Lock()
    mode=initial_mode if initial_mode in ('local','cloud') else 'local'
    if mode=='cloud' and not cloud_account.state():mode='local'
    navigation.save(storage=mode)
    last_snapshot=None
    block_limit=0
    compact=compact_layout(getattr(page,'width',None))
    search=modern_input(ft.TextField(hint_text='Найти материал',prefix_icon=ft.Icons.SEARCH,
        expand=not compact,width=None))
    order=modern_input(ft.Dropdown(label='Сортировка',value='size',width=None if compact else 170,
        options=[ft.DropdownOption(key='size',text='По размеру'),ft.DropdownOption(key='name',text='По имени')]))

    def metric(title,value,icon,subtitle=None):
        return ft.Container(padding=20,border_radius=26,bgcolor=color('#dff8f3'),
            animate=ft.Animation(240,ft.AnimationCurve.EASE_OUT_CUBIC),content=ft.Column(spacing=8,controls=[
                ft.Row(controls=[ft.Icon(icon,size=21,color=color('#087f8c')),ft.Text(title,size=13,color=color('#47747a'),expand=True)]),
                ft.Text(value,size=30,weight=ft.FontWeight.W_600,color=color('#123b43')),
                *([ft.Text(subtitle,size=12,color=color('#47747a'))] if subtitle else [])]))

    def usage_line(label,size,icon):
        return ft.Container(padding=ft.Padding.symmetric(horizontal=14,vertical=10),border_radius=18,
            bgcolor=color('#f3fffc'),content=ft.Row(spacing=10,controls=[
                ft.Icon(icon,size=19,color=color('#087f8c')),ft.Text(label,expand=True,size=13,color=color('#123b43')),
                ft.Text(storage.format_bytes(size),size=13,weight=ft.FontWeight.W_600,color=color('#123b43'))]))

    def selected(items):
        query=(search.value or '').strip().casefold()
        result=[item for item in items if query in item['name'].casefold() or any(query in reference.casefold() for reference in item.get('references',[]))]
        return sorted(result,key=lambda item: -item['bytes'] if order.value=='size' else item['name'].casefold())

    async def view(_,item):
        try:
            path=item['path']
            if not Path(path).is_file():
                status.value='Скачиваю копию из облака…';page.update()
                await asyncio.to_thread(storage.restore_local_material,path)
            await open_material(page,path,item['name'],references=item.get('references'))
        except Exception as exc:status.value=str(exc);page.update()

    async def export(_,item):
        try:
            path=item['path']
            if not Path(path).is_file():
                status.value='Скачиваю копию из облака…';page.update()
                await asyncio.to_thread(storage.restore_local_material,path)
            saved=await export_material(page,path,item['name'])
            status.value='Копия сохранена' if saved else 'Сохранение отменено'
        except Exception as exc:status.value=str(exc)
        page.update()

    async def recover_materials(_):
        recovery_button.disabled=True;status.value='Читаю зашифрованные описания прежних вложений…';page.update()
        try:
            result=await asyncio.to_thread(storage.recover_cloud_materials)
            await refresh()
            status.value='Найдено описаний материалов: '+str(result['found'])+'. Сами файлы не скачивались.'
        except Exception as exc:status.value=str(exc)
        finally:
            recovery_button.disabled=False
            if dialog.open:page.update()

    recovery_button=action_button('Найти прежние вложения',icon=ft.Icons.MANAGE_SEARCH,
        secondary=True,on_click=recover_materials)

    def menu(item,extra):
        return ft.PopupMenuButton(icon=ft.Icons.MORE_VERT,tooltip='Действия с материалом: '+item['name'],
            items=[ft.PopupMenuItem(content=ft.Text('Просмотреть'),icon=ft.Icons.VISIBILITY_OUTLINED,on_click=lambda e,item=item: page.run_task(view,e,item)),
                   ft.PopupMenuItem(content=ft.Text('Скачать / сохранить'),icon=ft.Icons.DOWNLOAD_OUTLINED,on_click=lambda e,item=item: page.run_task(export,e,item)),*extra])

    def card(item,extra):
        details=storage.format_bytes(item['bytes'])+' · '+(Path(item['name']).suffix.lstrip('.').upper() or 'Файл')
        references=item.get('references',[])
        return ft.Container(data={'material_path':item['path']},padding=14,border_radius=22,bgcolor=color('#f3fffc'),
            content=ft.Row(spacing=12,controls=[ft.Container(width=40,height=40,border_radius=14,bgcolor=color('#dff8f3'),
                alignment=ft.Alignment.CENTER,content=ft.Icon(ft.Icons.INSERT_DRIVE_FILE_OUTLINED,color=color('#087f8c'),size=22)),
                ft.Container(expand=True,ink=True,on_click=lambda e,item=item: page.run_task(view,e,item),
                    content=ft.Column(spacing=4,controls=[ft.Text(item['name'],color=color('#123b43'),size=14,max_lines=2,overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Text(details,size=12,color=color('#47747a')),
                        *([ft.Text(' · '.join(references),size=11,color=color('#47747a'),max_lines=2,overflow=ft.TextOverflow.ELLIPSIS)] if references else [])])),menu(item,extra)]))

    async def refresh(_=None):
        async with refresh_lock:await render_inventory()

    async def render_inventory():
        nonlocal last_snapshot
        if not dialog.open:return
        try:
            if mode=='local':
                inventory=await asyncio.to_thread(storage.local_inventory)
                private_versions=await asyncio.to_thread(storage.private_recoveries)
                profile_versions=profile.recoveries()
            else:inventory=await asyncio.to_thread(storage.cloud_inventory);private_versions=[];profile_versions=[]
            snapshot=json.dumps([mode,search.value,order.value,inventory,private_versions,profile_versions,block_limit],sort_keys=True,ensure_ascii=False)
            if snapshot==last_snapshot:return
            if mode=='local':
                rows=[ft.Text('На этом устройстве',size=18,weight=ft.FontWeight.BOLD)]
                labels={'db_bytes':'База и журналы','materials_bytes':'Материалы','private_bytes':'Защищённые чаты','cache_bytes':'Кэш отправки','trash_bytes':'Корзина','recovery_bytes':'Копии восстановления','models_bytes':'Модели ИИ'}
                total=sum(inventory[key] for key in labels)
                rows.append(metric('Занято на устройстве',storage.format_bytes(total),ft.Icons.PHONE_ANDROID,'Локальные копии и данные приложения'))
                rows.append(ft.ExpansionTile(title=ft.Text('Использование места'),controls=[
                    ft.Row(controls=[ft.Text(label,expand=True),ft.Text(storage.format_bytes(inventory[key]))]) for key,label in labels.items()]))
                rows += [ft.Text('В базе хранятся текст и ссылки. Материалы лежат отдельно: их локальные копии можно удалить или перенести в корзину. Корзина занимает место до очистки.',size=11,color=color('#47747a'))]
                unused=[f for f in inventory['files'] if not f['references']]
                if unused:
                    def cleanup(_):
                        async def remove(_):
                            try:
                                flush=getattr(page,'_xopilot_flush_draft',None)
                                if callable(flush):flush()
                                result=await asyncio.to_thread(storage.remove_unused_materials)
                                page.pop_dialog();await refresh()
                                status.value=f"Удалено копий: {result['count']} · освобождено: {storage.format_bytes(result['bytes'])}";page.update()
                            except Exception as exc:status.value=str(exc);page.update()
                        page.show_dialog(ft.AlertDialog(modal=True,bgcolor=color('#eafffa'),title=ft.Text('Удалить неиспользуемые копии?'),
                            content=ft.Column(width=440,height=260,scroll=ft.ScrollMode.AUTO,controls=[
                                ft.Text('Эти файлы не используются в чатах, черновиках и библиотеках проектов. Удаляются только копии Xopilot. Исходники и облако сохраняются.'),
                                *[ft.Text(f['name']+' · '+storage.format_bytes(f['bytes']),size=12) for f in unused]]),
                            actions=[ft.TextButton(content='Отмена',on_click=lambda _:page.pop_dialog()),ft.FilledButton(content='Удалить копии',on_click=remove)]))
                    rows.append(ft.OutlinedButton(content=f'Освободить место · неиспользуемых копий: {len(unused)}',icon=ft.Icons.CLEANING_SERVICES_OUTLINED,on_click=cleanup))
                rows.append(ft.Text('Материалы · '+str(len(inventory['files'])),size=16,weight=ft.FontWeight.BOLD))
                for item in selected(inventory['files']):
                    def confirm_delete(_,path=item['path'],name=item['name']):
                        async def remove(_):
                            try:await asyncio.to_thread(storage.delete_local_material,path);page.pop_dialog();await refresh()
                            except Exception as exc:status.value=str(exc);page.update()
                        page.show_dialog(ft.AlertDialog(bgcolor=color('#eafffa'),title=ft.Text('Удалить локальную копию?'),
                            content=ft.Text(name+' освободит место на устройстве. Вложение станет недоступно здесь до повторного скачивания или добавления исходного файла. Исходный файл и облачная копия сохраняются.'),
                            actions=[ft.TextButton(content='Отмена',on_click=lambda _:page.pop_dialog()),ft.FilledButton(content='Удалить копию',on_click=remove)]))
                    def confirm(_,path=item['path'],name=item['name']):
                        async def move(_):
                            try:
                                await asyncio.to_thread(storage.trash_material,path);page.pop_dialog();await refresh()
                            except Exception as exc:status.value=str(exc);page.update()
                        page.show_dialog(ft.AlertDialog(bgcolor=color('#eafffa'),title=ft.Text('Переместить в корзину?'),
                            content=ft.Text(name+' станет недоступен в чатах на этом устройстве до восстановления. Исходный файл не удаляется.'),
                            actions=[ft.TextButton(content='Отмена',on_click=lambda _:page.pop_dialog()),ft.FilledButton(content='В корзину',on_click=move)]))
                    rows.append(card(item,[
                        ft.PopupMenuItem(content=ft.Text('Переместить в корзину'),icon=ft.Icons.ARCHIVE_OUTLINED,on_click=confirm),
                        ft.PopupMenuItem(content=ft.Text('Удалить локальную копию'),icon=ft.Icons.DELETE_OUTLINE,on_click=confirm_delete)]))
                if not inventory['files']:rows.append(ft.Text('Локальных копий материалов нет. Добавленные в чат или проект файлы появятся здесь.',size=12,color=color('#47747a')))
                elif not selected(inventory['files']):rows.append(ft.Text('Материалы по вашему запросу не найдены',size=12,color=color('#47747a')))
                cloud_assets=cloud_sync.read_ledger(cloud_sync.owner()).get('assets',{}) if cloud_account.state() else {}
                for path,item in inventory['removed'].items():
                    if Path(path).is_file():continue
                    async def download(_,path=path):
                        try:await asyncio.to_thread(storage.restore_local_material,path);await refresh()
                        except Exception as exc:status.value=str(exc);page.update()
                    asset=cloud_assets.get(path)
                    downloadable=asset and not asset.get('excluded') and not asset['manifest'].get('missing')
                    rows.append(ft.Row(controls=[ft.Column(expand=True,spacing=3,controls=[ft.Text('Локальная копия удалена: '+item['name']),
                        *([] if downloadable else [ft.Text('Облачной копии нет — прикрепите исходный файл заново',size=11,color=color('#47747a'))])]),
                        *([ft.TextButton(content='Скачать из облака',disabled=not cloud_sync.options()['enabled'],on_click=download)] if downloadable else [])]))
                for recovery in private_versions:
                    async def restore_private(_,path=recovery['path']):
                        try:await asyncio.to_thread(storage.restore_private_recovery,path);await refresh()
                        except Exception as exc:status.value=str(exc);page.update()
                    rows.append(ft.Row(controls=[ft.Text(recovery['label'],expand=True),ft.OutlinedButton(content='Восстановить версию',on_click=restore_private)]))
                for index,item in reversed(profile_versions):
                    async def restore_profile(_,index=index):
                        try:
                            await asyncio.to_thread(profile.restore_recovery,index)
                            callback=getattr(page,'_xopilot_profile_refresh',None)
                            if callback:callback()
                            await refresh()
                        except Exception as exc:status.value=str(exc);page.update()
                    label='Профиль: '+item['profile']['name']+' · '+datetime.fromtimestamp(item['time']).strftime('%d.%m.%Y %H:%M')
                    rows.append(ft.Row(controls=[ft.Text(label,expand=True),ft.TextButton(content='Восстановить профиль',on_click=restore_profile)]))
                if inventory['trash']:rows.append(ft.Text('Корзина',size=16,weight=ft.FontWeight.BOLD))
                for identifier,item in inventory['trash'].items():
                    async def restore(_,identifier=identifier):
                        try:await asyncio.to_thread(storage.restore_material,identifier);await refresh()
                        except Exception as exc:status.value=str(exc);page.update()
                    def confirm_purge(_,identifier=identifier,name=item['name']):
                        async def purge(_):
                            try:await asyncio.to_thread(storage.purge_material,identifier);page.pop_dialog();await refresh()
                            except Exception as exc:status.value=str(exc);page.update()
                        page.show_dialog(ft.AlertDialog(bgcolor=color('#eafffa'),title=ft.Text('Удалить из корзины навсегда?'),
                            content=ft.Text(name+' будет удалён с этого устройства. Исходный файл вне Xopilot сохраняется.'),
                            actions=[ft.TextButton(content='Отмена',on_click=lambda _:page.pop_dialog()),ft.FilledButton(content='Удалить навсегда',on_click=purge)]))
                    trash_item={**item,'path':str(storage.app_data_dir()/'material-trash'/identifier)}
                    rows.append(card(trash_item,[ft.PopupMenuItem(content=ft.Text('Восстановить'),icon=ft.Icons.RESTORE,on_click=restore),
                        ft.PopupMenuItem(content=ft.Text('Удалить навсегда'),icon=ft.Icons.DELETE_FOREVER_OUTLINED,on_click=confirm_purge)]))
            else:
                used,quota=inventory['used_bytes'],inventory['quota_bytes']
                remaining=max(0,quota-used)
                rows=[metric('Облачное хранилище',storage.format_bytes(used),ft.Icons.CLOUD_OUTLINED,
                    'из '+storage.format_bytes(quota)+' · свободно '+storage.format_bytes(remaining)),
                    ft.Container(padding=ft.Padding.symmetric(horizontal=6),content=ft.ProgressBar(
                        value=min(1,used/max(1,quota)),height=8,border_radius=4,color=color('#087f8c'),bgcolor=color('#dff8f3'))),
                    ft.Text('Из чего складывается объём',size=16,weight=ft.FontWeight.W_600,color=color('#123b43')),
                    usage_line('Известные материалы',inventory['material_bytes'],ft.Icons.ATTACH_FILE),
                    usage_line('Чаты, Canvas и профиль · блоки',inventory['sync_payload_bytes'],ft.Icons.CHAT_BUBBLE_OUTLINE),
                    usage_line('Другие зашифрованные блоки',inventory['unmapped_bytes'],ft.Icons.LOCK_OUTLINE),
                    usage_line('Данные и история синхронизации',inventory['metadata_bytes'],ft.Icons.HISTORY),
                    ft.Text('Общий объём включает все устройства и прежние версии. Список ниже содержит материалы, имена которых известны этому устройству. Сервер не может прочитать зашифрованные имена и содержимое.',size=12,color=color('#47747a')),
                    recovery_button,
                    ft.Text('Материалы · '+str(len(inventory['materials'])),size=16,weight=ft.FontWeight.W_600,color=color('#123b43'))]
                if not inventory['materials']:
                    rows.append(ft.Text('На этом устройстве пока нет описаний облачных материалов. Проверьте синхронизацию чатов, пространств и материалов.',size=12,color=color('#47747a')))
                elif not selected(inventory['materials']):
                    rows.append(ft.Text('Ничего не найдено',size=12,color=color('#47747a')))
                for item in selected(inventory['materials']):
                    def confirm(_,path=item['path'],name=item['name']):
                        async def remove(_):
                            try:await asyncio.to_thread(storage.remove_cloud_material,path);page.pop_dialog();await refresh()
                            except Exception as exc:status.value=str(exc);page.update()
                        page.show_dialog(ft.AlertDialog(bgcolor=color('#eafffa'),title=ft.Text('Убрать материал из облака?'),
                            content=ft.Text(name+' останется на устройстве. Облачная копия будет удалена и исключена из автоматической отправки. Копии других материалов с тем же содержимым тоже могут стать недоступны.'),
                            actions=[ft.TextButton(content='Отмена',on_click=lambda _:page.pop_dialog()),ft.FilledButton(content='Удалить копию из облака',on_click=remove)]))
                    rows.append(card(item,[ft.PopupMenuItem(content=ft.Text('Удалить облачную копию'),icon=ft.Icons.CLOUD_OFF_OUTLINED,on_click=confirm)]))
                for excluded in inventory['excluded_materials']:
                    async def include(_,path=excluded['path']):
                        try:await asyncio.to_thread(storage.include_cloud_material,path);await refresh()
                        except Exception as exc:status.value=str(exc);page.update()
                    rows.append(ft.Row(controls=[ft.Text('Исключён: '+excluded['name'],expand=True),ft.OutlinedButton(content='Снова включить',on_click=include)]))
                unknown=sorted(inventory['unmapped_files'],key=lambda row:-row['bytes'])
                if unknown:
                    rows.append(ft.Container(padding=16,border_radius=22,bgcolor=color('#dff8f3'),content=ft.Column(spacing=8,controls=[
                        ft.Text('Почему файлов меньше, чем занято места?',weight=ft.FontWeight.W_600,color=color('#123b43')),
                        ft.Text('Эти блоки могут относиться к защищённым чатам, прежним вложениям или версиям с другого устройства. Без описания нельзя безопасно считать их лишними. Они учтены в объёме выше.',size=12,color=color('#47747a'))])))
                    for block in unknown[:block_limit]:
                        created=datetime.fromtimestamp(block['created_at']).strftime('%d.%m.%Y') if block.get('created_at') else ''
                        rows.append(usage_line('Блок '+block['id'][:8]+(' · '+created if created else ''),block['bytes'],ft.Icons.LOCK_OUTLINE))
                    if block_limit<len(unknown):
                        async def show_blocks(_):
                            nonlocal block_limit
                            block_limit+=20
                            await refresh()
                        rows.append(action_button('Показать блоки · '+str(len(unknown)-block_limit),icon=ft.Icons.EXPAND_MORE,secondary=True,on_click=show_blocks))
                counts=inventory.get('object_counts',{})
                if counts:
                    labels={'chat':'Чаты','workspace':'Пространства','canvas':'Canvas','profile':'Профиль','material':'Материалы'}
                    rows.append(ft.Row(wrap=True,spacing=8,run_spacing=8,controls=[
                        ft.Container(padding=ft.Padding.symmetric(horizontal=12,vertical=8),border_radius=16,bgcolor=color('#dff8f3'),
                            content=ft.Text(labels.get(key,key)+': '+str(count),size=12,color=color('#123b43'))) for key,count in counts.items() if count]))

            content.controls=[filters,*rows];apply_palette(content)
            if not recovery_button.disabled:status.value=''
            last_snapshot=snapshot
        except Exception as exc:status.value=str(exc)
        finally:
            if dialog.open:page.update()

    async def choose(_,selected):
        nonlocal mode,block_limit
        if mode==selected:return
        tabs.disabled=True;content.opacity=0;content.offset=(0,0.015);page.update()
        await asyncio.sleep(.12)
        mode=selected;block_limit=0;navigation.save(storage=mode)
        try:await refresh()
        finally:
            content.opacity=1;content.offset=(0,0);tabs.disabled=False
            if dialog.open:page.update()
    async def switch_tab(e):await choose(e,e.control.selected[0])
    tabs=ft.SegmentedButton(expand=True,selected=[mode],show_selected_icon=False,on_change=switch_tab,
        segments=[ft.Segment(value='local',label='На устройстве',icon=ft.Icons.COMPUTER),
                  ft.Segment(value='cloud',label='В облаке',icon=ft.Icons.CLOUD_OUTLINED,disabled=cloud_account.state() is None)],
        style=ft.ButtonStyle(color=color('#123b43'),bgcolor={ft.ControlState.SELECTED:color('#c9f1e9'),ft.ControlState.DEFAULT:color('#f3fffc')},
            padding=ft.Padding.symmetric(horizontal=12,vertical=10),
            side=ft.BorderSide(1,color('#b9eee4')),shape=ft.RoundedRectangleBorder(radius=18)))
    filters=ft.Column(spacing=8,controls=[search,order]) if compact else ft.Row(controls=[search,order])
    content.controls=[filters]
    task=None
    def close(_):
        navigation.save(storage=None)
        page.pop_dialog()
        if task:task.cancel()
    search.on_change=refresh
    order.on_select=refresh
    dialog=ft.AlertDialog(bgcolor=color('#eafffa'),title=ft.Text('Хранилище'),shape=ft.RoundedRectangleBorder(radius=28),
        content=ft.Column(width=550,height=560,spacing=12,controls=[ft.Row(controls=[tabs]),content,status]),
        actions=[action_button('Готово',on_click=close,icon=ft.Icons.CHECK)],
        on_dismiss=lambda _:navigation.save(storage=None))
    fit_dialog(page,dialog);apply_palette(dialog)
    page.show_dialog(dialog)
    async def watch():
        while dialog.open and getattr(page,'_xopilot_connected',True):
            if page._dialogs.controls and page._dialogs.controls[-1] is dialog:await refresh()
            await asyncio.sleep(4 if mode=='local' else 60)
    task=page.run_task(watch)
