import sublime

is_sublime_text_3 = int(sublime.version()) >= 3000

if is_sublime_text_3:
    from .settings import Settings
    from .caches import ProcessCache
    from .timeout import defer_sync
else:
    from settings import Settings
    from caches import ProcessCache
    from timeout import defer_sync


class StatusBar():
    def __init__(self, window):
        self.window = window
        self.settings = Settings()

    def update(self):
        if ProcessCache.empty():
            return self.erase()

        status_bar_tasks = self.settings.get('status_bar_tasks', False)

        if status_bar_tasks:
            task_names = set([process.get_task_name() for process in ProcessCache.get()])

            if status_bar_tasks == True:
                status_task_names = task_names
            else:
                status_task_names = task_names.intersection(set(status_bar_tasks))

            defer_sync(lambda: self.set(', '.join(status_task_names)))

    def set(self, text):
        text_format = self.settings.get('status_bar_format', '{0}')
        status = text_format.format(text)
        self.window.active_view().set_status(Settings.PACKAGE_NAME, status)

    def erase(self):
        self.window.active_view().erase_status(Settings.PACKAGE_NAME)
