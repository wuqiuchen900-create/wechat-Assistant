import py_compile
files = [
    'app/main_window.py',
    'app/reminder_popup.py',
    'app/tray_icon.py',
    'app/settings_dialog.py',
    'app/widgets/daily_brief.py',
    'app/widgets/history_search.py',
    'app/widgets/detail_panel.py',
    'app/widgets/stats_bar.py',
    'app/delegates/avatar.py',
    'core/reminder_manager.py',
    'core/ai_search.py',
]
for f in files:
    try:
        py_compile.compile(f, doraise=True)
        print(f'{f} OK')
    except py_compile.PyCompileError as e:
        print(f'{f} FAIL: {e}')
