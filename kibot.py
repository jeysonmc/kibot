from kivy.input import MotionEventFactory
from kivy.input.providers.mouse import MouseMotionEventProvider
from kivy.clock import Clock
from kivy.base import EventLoop
from kivy.config import Config
from functools import partial
import time
from kivy.factory import Factory
import unittest
from threading import Thread


class FakeMouseEventProvider(MouseMotionEventProvider):

    """A fake Mouse Motion Event Provider """

    instance = None

    def start(self):
        FakeMouseEventProvider.instance = self
        self.win = EventLoop.window

    def mouse_down(self, x, y, button='left', t=0):
        self.on_mouse_press(self.win, x, y, button, ())

    def mouse_up(self, x, y, button='left', t=0):
        self.on_mouse_release(self.win, x, y, button, ())

    def move(self, x, y, t=0):
        self.on_mouse_motion(self.win, x, y, ())


class Kibot(object):

    """Kibot is a basic GUI test automation tool for kivy."""

    app = None
    time_cnt = 0
    num_events = 0
    delta_time = 0.05  # Time to wait between events.
    errors = []
    _kibot_cmd = 'self'
    recorded_commands = []
    record_fname = ''

    def __init__(self, *args, **kwargs):
        self.app = args[0]
        self.time_cnt = 1
        self.win = EventLoop.window
        self.keyboard = self.win._system_keyboard

    def wait(self, t=0):
        """Waits specified time
        :param t: time in seconds
        """
        self.time_cnt += t

    def do_press(self, x=0, y=0, widget=None):
        """touch_down event
         :param widget: if widget is provided x and y are obtained from
        widget's position.
        """
        fmp = FakeMouseEventProvider.instance
        self.do(partial(self._do_input, fmp.mouse_down, x, y, widget))

    def do_release(self, x=0, y=0, widget=None):
        """touch_up event
         :param widget: if widget is provided x and y are obtained from
        widget's position.
        """
        fmp = FakeMouseEventProvider.instance
        self.do(partial(self._do_input, fmp.mouse_up, x, y, widget))

    def do_move(self, x=0, y=0, widget=None):
        """mouse move event"""
        fmp = FakeMouseEventProvider.instance
        self.do(partial(self._do_input, fmp.move, x, y, widget))

    def do_click(self, x=0, y=0, t=0.2, widget=None):
        """ Press a widget (press, wait, and release)
        :param widget: if widget is provided x abd y are obtained from
        widget's position.
        :param t: time to wait between press and release
        """
        self.do_press(x, y, widget)
        self.wait(t)
        self.do_release(x, y, widget)

    def _do_input(self, func, x, y, widget=None):
        fmp = FakeMouseEventProvider.instance
        if widget is not None:
            if round(x) - x == 0 and round(y) - y == 0:
                x, y = widget.center_x, widget.center_y
            else:
                # TODO pending document this
                pos = widget.pos
                size = widget.size
                x = pos[0] + size[0] * x
                y = pos[1] + size[1] * y

            y = self.win.height - y
        if func != fmp.move:
            func(x, y, 'left')
        else:
            func(x, y)

    def do_keystroke(self, key=None, text=None):
        """ Sends keystroke using active keyboard.
        Check kivy.core.window.KeyBoard.keycodes for keys
        :param key: key string (ex: 'a')
        :param text: optional, if specified, keyboard will send this text all
        at once.
        """
        # TODO pending modifiers (shift, ctrl, etc)
        self.do_keydown(key, text)
        self.do_keyup(key)

    def do_keyup(self, key):
        keycode = self.keyboard.string_to_keycode(key)
        self.do(partial(self.keyboard.dispatch, 'on_key_up', (keycode, key)))

    def do_keydown(self, key, text=None):
        if key is None:
            key = text[0]  # TODO is this ok?
        keycode = self.keyboard.string_to_keycode(key)
        if text is None and len(key) == 1:
            text = key
        if key == 'spacebar' or key == ' ':
            text = ' '
            key = 'spacebar'

        self.do(
            partial(self.keyboard.dispatch, 'on_key_down', (keycode, key), text, ''))

    def do(self, func):
        self.last = Clock.schedule_once(
            partial(self._event, func), self.time_cnt)
        self.wait(self.delta_time)
        self.num_events += 1

    def _event(self, func, t=0):
        try:
            func()
        except Exception as e:
            self.errors.append(e)
        self.num_events -= 1

    def wait_until(self):
        """Waits until all events have been executed in kivy EventLoop"""
        while self.num_events:  # Warning could result in infinite loop
            pass

    def find(self, root=None, *args, **kwargs):
        """ Find first widget in widget tree with specified properties values
        Ex: find(class_='Button', text='Text')
        :param root: Root widget, if None App.root is used.
        :returns: found widget or None
        """

        attrs, values = zip(*kwargs.items())
        root = self.app.root if root is None else root
        b = True
        prev_ids = args[0] if len(args) else {}
        ids = root.ids if len(root.ids) else prev_ids
        for wid in root.children:
            b = True
            for attr, value in kwargs.iteritems():
                if attr == 'class_':
                    if not isinstance(wid, getattr(Factory, value)):
                        b = False
                elif attr == 'id':
                    if not any([w == wid and value == id_
                                for id_, w in ids.iteritems()]):
                        b = False
                elif not hasattr(wid, attr):
                    b = False
                else:
                    val = getattr(wid, attr)
                    if val != value:
                        b = False
                if not b:
                    continue
            if b:
                return wid

        # Search inside children
        for wid in root.children:
            if len(wid.children):
                ret = self.find(wid, ids, **kwargs)
                if ret is not None:
                    return ret
        return None

    def reset(self, reset_app=False):
        self.time_cnt = 0
        self.errors = []
        if reset_app:
            self.do(self._reset_app)

    def _reset_app(self, *args):
        # More or less the same initializacion in App.run without RounTouchApp
        window = EventLoop.window
        window.remove_widget(self.app.root)
        # self.app.load_config()
        # self.app.load_kv(filename=self.app.kv_file)
        r = self.app.build()
        window.add_widget(r)
        self.app.root = r
        window.clear()
        # self.app._install_settings_keys(window)
        self.app.dispatch('on_start')

    def record(self, filename='test.kibot'):
        """Records input operations (touches, keystrokes) and saves it to a file"""
        self.record_fname = filename
        self._lasttime = time.time()
        self.recorded_commands = []
        self._last_pos = -100, 0
        self.keyboard.bind(on_key_down=self._record_on_key_down)
        self.keyboard.bind(on_key_up=self._record_on_key_up)
        self.win.bind(on_touch_down=self._record_on_touch_down)
        self.win.bind(on_touch_up=self._record_on_touch_up)
        self.win.bind(on_touch_move=self._record_on_touch_move)

    def _record_command(self, cmd):
        if len(self.recorded_commands):
            self.recorded_commands.append(
                "%s.wait(%s)" % (self._kibot_cmd, round(time.time() - self._lasttime, 2)))
        self.recorded_commands.append(cmd)
        self._lasttime = time.time()
        print "Recording command:", cmd

    def _record_on_key_down(self, *args):
        key, text = args[1][1], None
        print args
        cmd = "%s.do_keydown('%s', %s)" % (self._kibot_cmd, key, text)
        self._record_command(cmd)

    def _record_on_key_up(self, *args):
        key = args[1][1]
        cmd = "%s.do_keyup('%s')" % (self._kibot_cmd, key)
        self._record_command(cmd)

    def _record_on_touch_down(self, *args):
        event = args[1]
        w, h = self.win.width, self.win.height
        x, y = event.spos
        x, y = x * w, h - y * h
        cmd = "%s.do_press(x=%s, y=%s)" % (self._kibot_cmd, x, y)
        self._record_command(cmd)

    def _record_on_touch_up(self, *args):
        event = args[1]
        w, h = self.win.width, self.win.height
        x, y = event.spos
        x, y = x * w, h - y * h
        cmd = "%s.do_release(x=%s, y=%s)" % (self._kibot_cmd, x, y)
        self._record_command(cmd)

    def _record_on_touch_move(self, *args):
        event = args[1]
        w, h = self.win.width, self.win.height
        x, y = event.spos
        x, y = x * w, h - y * h
        # This allows not to record touch_move events that are too close
        if (abs(self._last_pos[0] - x) + abs(self._last_pos[1] - y)) < 5:
            return
        self._last_pos = x, y
        cmd = "%s.do_move(x=%s, y=%s)" % (self._kibot_cmd, x, y)
        self._record_command(cmd)

    def execute_record(self, filename='test.kibot'):
        """Executes kibot file"""
        self.do(partial(self._execute, filename))

    def _execute(self, name):
        with open(name, 'r') as f:
            data = f.read()
            commands = data.split('\n')
            for cmd in commands:
                exec(cmd)  # TODO is this dangerous?

    def __del__(self):
        if len(self.record_fname):
            with open(self.record_fname, 'w') as f:
                f.write('\n'.join(self.recorded_commands))


class WidgetNotFoundError(Exception):
    pass


class KibotTestCase(unittest.TestCase):

    """ Base kibot testcase. Your tests should inherit from this """
    app = None
    """App instance """

    reset_app = True
    """ If True app will be reseted before each test """

    @classmethod
    def setUpClass(cls):
        cls.kibot = Kibot(cls.app)

    def setUp(self):
        if self.reset_app:
            self.kibot.reset(True)
            self.kibot.wait_until()  # Wait until app reseted
            self.setUp_app(self.app)
        else:
            self.kibot.reset()

    def setUp_app(self, app):
        """Aditional initialization/reset for your app"""
        pass


def _runtests(app):
    time.sleep(1)  # TODO how much time to wait?
    try:
        unittest.main()
    finally:
        app.stop()


def run_kibot_tests(app):
    """ Performs the tests by calling app.run in the main thread and
    unittest.main in a daemon. """

    tl = Thread(target=_runtests, args=(app,))
    tl.daemon = True
    tl.start()
    KibotTestCase.app = app
    app.run()

Config.set("input", "fakemouseprovider", "fakemouseprovider")
MotionEventFactory.register('fakemouseprovider', FakeMouseEventProvider)
