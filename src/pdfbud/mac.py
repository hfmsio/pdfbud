"""Mac only: Finder, the window's own full screen, and open-file requests from Finder."""
import subprocess
import sys
import threading


def reveal(path):  # show a file in Finder
    subprocess.run(["open", "-R", str(path)])


def name_app(name):  # when started with uv run, the menu bar would say "python3"
    import Foundation

    Foundation.NSProcessInfo.processInfo().setProcessName_(name)
    info = Foundation.NSBundle.mainBundle().infoDictionary()
    info["CFBundleName"] = info["CFBundleDisplayName"] = name


def confirm(message, yes, no):  # a native question; safe on the main thread, where closing and quitting run
    import AppKit

    alert = AppKit.NSAlert.alloc().init()
    alert.setMessageText_(message)
    alert.addButtonWithTitle_(yes)
    alert.addButtonWithTitle_(no)
    return alert.runModal() == AppKit.NSAlertFirstButtonReturn


def copy(text):  # put text on the clipboard
    import AppKit

    pasteboard = AppKit.NSPasteboard.generalPasteboard()
    pasteboard.clearContents()
    pasteboard.setString_forType_(text, AppKit.NSPasteboardTypeString)


def on_open_files(callback):
    """Dock-icon drops and Open With reach a running app through the Mac app delegate.
    callback(path) runs on the Mac main thread and returns whether it took the file."""
    import objc
    from webview.platforms.cocoa import BrowserView

    def open_file(self, app, name):
        return bool(callback(name))

    handler = objc.selector(open_file, selector=b"application:openFile:", signature=b"c@:@@")
    objc.classAddMethods(BrowserView.AppDelegate, [handler])


class Screen:
    """The window's own full screen. Asking for the state it is already in does nothing.
    pywebview's own toggle gets stuck on the way out, and the Mac ignores a request made while the window is still
    moving, so this reads the real state, asks again if needed, and keeps the latest request in `want`."""

    def __init__(self, window, tell):
        self.window, self.tell = window, tell  # tell(full): send the real state to the page
        self.want = None
        self.fs = False

    def set(self, on):
        self.want = bool(on)
        if sys.platform != "darwin":
            if self.want != self.fs:
                self.fs = self.want
                self.window.toggle_fullscreen()
            return
        from PyObjCTools import AppHelper
        from webview.platforms.cocoa import BrowserView

        ns = BrowserView.get_instance("pywebview_window", self.window).window

        def apply(tries=3):
            if self.want != bool(on):  # a newer request took over
                return
            ns.setCollectionBehavior_(1 << 7)  # allow full screen
            if bool(ns.styleMask() & (1 << 14)) == bool(on):  # 1 << 14 is the "is full screen" flag
                return
            if not tries:  # the Mac would not do it: tell the page what is really going on
                threading.Thread(target=self.tell, args=(not on,), daemon=True).start()
                return
            ns.toggleFullScreen_(None)
            AppHelper.callLater(1.5, apply, tries - 1)

        AppHelper.callAfter(apply)

    def changed(self, full):  # the move is over (also when the green button was used); True if the page should hear it
        self.fs = full
        if self.want is not None and self.want != full:  # the opposite was asked for while the window was still moving
            self.set(self.want)
            return False
        self.want = None
        return True
