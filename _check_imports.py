import sys
sys.path.insert(0, '.')

modules = [
    ('app.widgets.daily_brief', 'DailyBriefPanel'),
    ('app.widgets.history_search', 'HistorySearchPanel'),
    ('core.reminder_manager', 'init_reminders_table'),
    ('core.ai_search', 'AISearchEngine'),
    ('app.reminder_popup', 'ReminderPopup'),
    ('app.main_window', 'MainWindow'),
    ('app.tray_icon', 'WeChatAssistantTray'),
    ('app.settings_dialog', 'SettingsDialog'),
]

for mod_name, attr in modules:
    try:
        mod = __import__(mod_name, fromlist=[attr])
        getattr(mod, attr)
        print(f'{mod_name} -> {attr} OK')
    except Exception as e:
        print(f'{mod_name} -> {attr} FAIL: {e}')
