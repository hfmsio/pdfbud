"""Keeps a real-window test out of your way.

By default the test window has no Dock icon, never takes focus, and sits in a screen corner with only a small square
showing. (WebKit slows a fully hidden window down, which would break the checks, so a little of it stays on screen.)
Set PDFBUD_SHOW=1 to watch the window instead. The checks that need the real Mac full screen only run in that mode.
"""
import os

SHOW = bool(os.environ.get("PDFBUD_SHOW"))


def window_options():  # pass to app.make_window
    if SHOW:
        return {}
    import webview
    screen = webview.screens[0]
    return {"frameless": True, "x": screen.width - 48, "y": screen.height - 48}


def install():  # call once before webview.start
    if SHOW:
        return
    import AppKit
    from PyObjCTools import AppHelper
    from webview.platforms.cocoa import BrowserView

    BrowserView.app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)  # pywebview starts as a normal app
    before = AppKit.NSWorkspace.sharedWorkspace().frontmostApplication()  # the app you are working in

    def first_show(self):  # pywebview's own version also activates the app and makes the window the key window
        self.window.orderFrontRegardless()
        self.shown.set()
        if not BrowserView.app.isRunning():
            BrowserView.app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)
            for delay in (0.1, 0.4, 1.0):  # the window still ends up active for a moment: hand focus back to your app
                AppHelper.callLater(delay, before.activateWithOptions_, AppKit.NSApplicationActivateIgnoringOtherApps)
            AppHelper.installMachInterrupt()
            BrowserView.app.run()

    BrowserView.first_show = first_show
