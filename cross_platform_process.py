import sublime
import subprocess
import signal
import os
from threading import Thread

is_sublime_text_3 = int(sublime.version()) >= 3000

if is_sublime_text_3:
    from .settings import Settings
    from .dir_context import Dir
    from .cross_platform_codecs import CrossPlatformCodecs
    from .caches import ProcessCache, CacheFile
else:
    from settings import Settings
    from dir_context import Dir
    from cross_platform_codecs import CrossPlatformCodecs
    from caches import ProcessCache, CacheFile


class CrossPlatformProcess():
    def __init__(self, working_dir="", last_command="", pid=None):
        self.working_dir = working_dir
        self.last_command = last_command
        self.pid = pid
        
        settings = Settings()
        self.nonblocking = settings.get("nonblocking", True)
        self.path = Env.get_path(settings.get('exec_args', False))

        self.process = None
        self.failed = False

    def run(self, command):
        with Dir.cd(self.working_dir):
            self.process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=self.path, shell=True, preexec_fn=self._preexec_val())
            self.pid = self.process.pid

        self.last_command = command.rstrip()
        ProcessCache.add(self)
        return self

    def run_sync(self, command):
        command = CrossPlatformCodecs.encode_process_command(command)

        with Dir.cd(self.working_dir):
            self.process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=self.path, shell=True)
            self.pid = self.process.pid
            (stdout, stderr) = self.process.communicate()
            self.failed = self.process.returncode == 127 or stderr

        return (CrossPlatformCodecs.force_decode(stdout), CrossPlatformCodecs.force_decode(stderr))

    def _preexec_val(self):
        return os.setsid if sublime.platform() != "windows" else None

    def communicate(self, fn=lambda x: None):
        stdout, stderr = self.pipe(fn)
        self.process.communicate()
        self.terminate()
        return (stdout, stderr)

    def pipe(self, fn):
        streams = [self.process.stdout, self.process.stderr]
        streams_text = []
        if self.nonblocking:
            threads = [ThreadWithResult(target=self._pipe_stream, args=(stream, fn)) for stream in streams]
            [t.join() for t in threads]
            streams_text = [t.result for t in threads]
        else:
            streams_text = [self._pipe_stream(stream, fn) for stream in streams]
        return streams_text

    def _pipe_stream(self, stream, fn):
        output_text = ""
        while True:
            line = stream.readline()
            if not line:
                break
            output_line = CrossPlatformCodecs.decode_line(line)
            output_text += output_line
            fn(output_line)
        return output_text

    def terminate(self):
        if self.is_alive():
            self.process.terminate()
        ProcessCache.remove(self)

    def is_alive(self):
        return (self.process is None and self.pid is not None) or self.process.poll() is None

    def returncode(self):
        return self.process.returncode

    def kill(self):
        if sublime.platform() == "windows":
            kill_process = subprocess.Popen(['C:\\Windows\\system32\\taskkill.exe', '/F', '/T', '/PID', str(self.pid)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
            kill_process.communicate()
        else:
            os.killpg(self.pid, signal.SIGTERM)
        ProcessCache.remove(self)

    def to_json(self):
        return {
            'workding_dir': self.working_dir,
            'last_command': self.last_command,
            'pid': self.pid
        }


class Env():
    @classmethod
    def get_path(self, exec_args=False):
        env = os.environ.copy()
        if exec_args:
            path = str(exec_args.get('path', ''))
            if path:
                env['PATH'] = path
        return env


class ThreadWithResult(Thread):
    def __init__(self, target, args):
        self.result = None
        self.target = target
        self.args = args
        Thread.__init__(self)
        self.start()

    def run(self):
        self.result = self.target(*self.args)
