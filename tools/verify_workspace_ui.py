"""Render all workspace pages without game input or writing user settings."""
import hashlib
import sys
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication, QPushButton, QTableWidget, QLabel
from PySide6.QtCore import QTimer
from src.ui.ui import MainWindow


class Controller:
    auto_bot = SimpleNamespace(cfg={}, thread_auto_bot=None,
                               is_terminated=True, video_writer=None)

    def enable_bot_viz(self):
        pass

    def disable_bot_viz(self):
        pass


def main():
    paths = list(Path('config').glob('*.yaml'))
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    app = QApplication.instance() or QApplication([])
    with patch.object(MainWindow, 'load_ui_state'), patch.object(MainWindow, 'save_ui_state'):
        win = MainWindow(Controller())
        for timer in win.findChildren(QTimer):
            timer.stop()
        win.resize(1280, 880)
        win.show()
        assert [win.tabs.tabText(i) for i in range(win.tabs.count())] == ['总览', '地图', '数据', '记录', '设置', '诊断']
        for i, name in enumerate(('overview', 'maps', 'data', 'records', 'settings', 'diagnostics')):
            win.navigation.setCurrentRow(i)
            app.processEvents()
            assert win.tabs.currentIndex() == i
            assert win.tabs.widget(i).findChild(QLabel,'pageTitle').toolTip()
            assert win.width() == 1280 and win.height() == 880
            assert not win.findChildren(QPushButton, 'auto_capture')
            win.grab().save(str(Path('debug')/f'redesign_{name}.png'))
        win.tabs.setCurrentIndex(1); app.processEvents()
        assert win.tab_map_debug.isVisibleTo(win.tab_maps)
        assert win.tab_map_debug.height() >= 280
        win.tabs.setCurrentIndex(0); app.processEvents()
        assert win.button_start_pause.isVisibleTo(win.tab_main)
        win.tabs.setCurrentIndex(4); app.processEvents()
        assert win.button_nametag.isVisibleTo(win.tab_settings)
        assert win.button_template.isVisibleTo(win.tab_diagnostics)
        assert win.tab_statistics.pick_region_button.isVisibleTo(win.tab_diagnostics)
        assert win.tab_statistics.reset_region_button.isVisibleTo(win.tab_diagnostics)
        assert not win.tab_statistics.pick_region_button.isVisibleTo(win.tabs.widget(2))
        assert not win.control_gbox.isVisibleTo(win.tab_settings)
        toggle=win.findChild(QPushButton,'settingsManagerToggle')
        toggle.click();app.processEvents()
        assert win.config_combo.isVisibleTo(win.tab_settings)
        toggle.click();app.processEvents()
        assert not win.attack_gbox.isVisibleTo(win.tab_settings)
        assert win.key_binding_gbox.isVisibleTo(win.tab_settings)
        original_inputs=list(win.buff_inputs)
        was_visible=not win.buff_section_container.isHidden()
        buff_scroll=win.findChild(__import__('PySide6.QtWidgets',fromlist=['QScrollArea']).QScrollArea,'buffScroll')
        scroll_visible=not buff_scroll.isHidden()
        buff_scroll.show()
        win.buff_section_container.show()
        win.add_buff_row('F6','60')
        app.processEvents()
        key,interval=win.buff_inputs[-1]
        row=key.parentWidget()
        delete=row.findChild(QPushButton,'deleteBuffRow')
        buff_theme=win.property('theme')
        win.apply_theme('parchment',persist=False);app.processEvents()
        assert row.height()>=key.height()+20
        assert delete.width()>=66
        win.grab().save(str(Path('debug')/'redesign_settings_buff.png'))
        delete.click();app.processEvents()
        assert win.buff_inputs==original_inputs
        # Growing the list must not grow the card.
        fixed_height=win.buff_skill_gbox.height()
        for _ in range(6):win.add_buff_row('F7','30')
        app.processEvents()
        assert win.buff_skill_gbox.height()==fixed_height
        assert buff_scroll.verticalScrollBar().maximum()>0
        for key,_ in list(win.buff_inputs[len(original_inputs):]):
            key.parentWidget().findChild(QPushButton,'deleteBuffRow').click()
        from PySide6.QtCore import QSignalBlocker
        jump=win.jump_key;original_jump=jump.get_key()
        with QSignalBlocker(jump):jump.set_key(win.basic_attack_key.get_key() or 'F8')
        original_attack=win.basic_attack_key.get_key()
        if not original_attack:
            with QSignalBlocker(win.basic_attack_key):win.basic_attack_key.set_key('F8')
        win.refresh_key_conflicts()
        assert jump.property('keyConflict') is True
        with QSignalBlocker(jump):jump.set_key(original_jump)
        with QSignalBlocker(win.basic_attack_key):win.basic_attack_key.set_key(original_attack)
        win.refresh_key_conflicts()
        win.buff_section_container.setVisible(was_visible)
        buff_scroll.setVisible(scroll_visible)
        win.apply_theme(buff_theme,persist=False)
        win.settings_scroll.verticalScrollBar().setValue(win.settings_scroll.verticalScrollBar().maximum())
        app.processEvents()
        win.grab().save(str(Path('debug')/'redesign_settings_bottom.png'))
        win.settings_scroll.verticalScrollBar().setValue(0)
        # Inspect a real saved map without selecting it through config-writing signals.
        win.selected_map='死亡森林1'
        win.navigation.setCurrentRow(1);app.processEvents();win.tab_map_debug.refresh();app.processEvents()
        win.grab().save(str(Path('debug')/'redesign_maps_loaded.png'))
        assert win.tab_map_debug.graph is not None
        original_theme=win.property('theme')
        for theme in ('dark','light','parchment'):
            win.apply_theme(theme,persist=False)
            for i,name in enumerate(('overview','maps','data','records','settings','diagnostics')):
                win.navigation.setCurrentRow(i);app.processEvents()
                win.grab().save(str(Path('debug')/f'redesign_{name}_{theme}.png'))
            assert win.property('theme')==theme
        win.apply_theme(original_theme,persist=False)
        # Every theme exposes the same dropdown, and brand text clears the icon.
        from PySide6.QtWidgets import QComboBox
        from PySide6.QtGui import QImage
        from src.ui.parchment import ASSETS, asset_icon
        for asset in ('maple','maple-muted','target','hp','mp','swords','avatar','frame-v2','button-v2','paper-v2'):
            image=QImage(str(ASSETS/f'{asset}.png'))
            assert not image.isNull(),asset
            assert max(image.width(),image.height())<=627,asset
        assert asset_icon('maple') is asset_icon('maple')
        selector=win.findChild(QComboBox,'themeSelector')
        apply_theme=win.apply_theme
        # Disconnect persistence callback while exercising selection semantics.
        selector.currentIndexChanged.disconnect()
        selector.currentIndexChanged.connect(lambda i:apply_theme(('light','dark','parchment')[i],persist=False))
        for i,mode in enumerate(('light','dark','parchment')):
            selector.setCurrentIndex(i);app.processEvents()
            assert selector.isVisibleTo(win)
            assert win.property('theme')==mode
        icon=win.findChild(QLabel,'brandIcon');title=win.findChild(QLabel,'brand')
        assert icon.geometry().right()<title.parentWidget().width()
        assert icon.mapTo(win,icon.rect().topRight()).x()<title.mapTo(win,title.rect().topLeft()).x()
        win.potion_test_result.setText('血量 52%  ·  魔法 68%')
        assert 'hp.png' in win.potion_test_result.text() and 'mp.png' in win.potion_test_result.text()
        win.potion_test_result.setText('血量 —  ·  魔法 —')
        win.apply_theme(original_theme,persist=False)
        for width,height in [(1080,760),(1440,960)]:
            win.resize(width,height)
            for i,name in enumerate(('overview','maps','data','records','settings','diagnostics')):
                win.navigation.setCurrentRow(i);app.processEvents()
                assert win.width()==width and win.height()==height, (name,win.size())
                win.grab().save(str(Path('debug')/f'redesign_{name}_{width}.png'))
        win.navigation.setCurrentRow(2);app.processEvents()
        assert win.tab_statistics.isVisibleTo(win)
        assert win.tab_statistics.table.height()>=190
        charts=win.tab_statistics.charts
        charts.maps.setCurrentText('死亡森林1')
        charts.levels.setCurrentIndex(charts.levels.findData(52))
        app.processEvents()
        if charts.bars.isVisibleTo(win):
            win.resize(1360,940);app.processEvents()
            win.grab().save(str(Path('debug')/'redesign_data_populated.png'))
            from PySide6.QtTest import QTest
            from PySide6.QtCore import Qt
            QTest.mouseClick(charts.bars.viewport(),Qt.LeftButton)
            app.processEvents()
            assert not hasattr(charts,'zoom_dialog')
            assert len(charts.bars.chart().axes(Qt.Horizontal)[0].categoriesLabels())<=5
        win.tab_statistics.data_splitter.setSizes([300,300]);app.processEvents()
        assert win.tab_statistics.table.height()>=190
        # Session fixtures live only in a temporary directory, never in user archives.
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);manual=root/'sessions'/'manual';manual.mkdir(parents=True)
            original_path=win.path_cfg_custom
            (root/'config').mkdir()
            with patch('src.ui.ui.APP_ROOT',str(root)), patch.object(win,'_flush_settings'), patch.object(win,'save_ui_state'):
                with patch('src.ui.ui.QInputDialog.getText',return_value=('复制测试',True)):
                    win._copy_current_settings()
                copied=root/'config'/'复制测试.yaml'
                assert copied.exists()
                import yaml
                from src.utils.common import get_cfg_diff
                assert yaml.safe_load(copied.read_text(encoding='utf-8'))==get_cfg_diff(win.cfg_base,win.cfg)
                with patch('src.ui.ui.QInputDialog.getText',return_value=('重命名测试',True)):
                    win._rename_settings_dialog()
                assert not copied.exists()
                assert (root/'config'/'重命名测试.yaml').exists()
                assert win.config_combo.currentData()==str(root/'config'/'重命名测试.yaml')
            win.path_cfg_custom=original_path;win._refresh_config_combo()
            assert win._config_display_name('config/config_custom.yaml')=='我的设置'
            (manual/'manifest.json').write_text(json.dumps(dict(map_name='fixture-map',status='finished',duration_actual=600,provenance={'automation_version':'manual-version'})),encoding='utf-8')
            video=root/'video'/'run.mp4';video.parent.mkdir();video.touch()
            evidence=Path(str(video)+'.session');evidence.mkdir()
            (evidence/'provenance.json').write_text(json.dumps({'automation_version':'auto-version'}),encoding='utf-8')
            (evidence/'events.jsonl').write_text(json.dumps({'kind':'session','cfg':{'bot':{'map':'fixture-map'}}})+'\n',encoding='utf-8')
            with patch('src.ui.workspace_shell.APP_ROOT',root):
                win.reload_record_list()
                records=win.tab_records.findChild(QTableWidget)
                assert records.rowCount()==2
                assert {records.item(i,3).text() for i in range(2)}=={'manual-versi','auto-version'}
                assert all(records.item(i,2).text()=='fixture-map' for i in range(2))
        win.tab_statistics.pool.shutdown(wait=True)
    assert before == {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}, [str(p) for p in paths if before[p]!=hashlib.sha256(p.read_bytes()).hexdigest()]
    print('PASS: six pages, navigation, resizing, preserved controls, unchanged configurations')


if __name__ == '__main__':
    main()
