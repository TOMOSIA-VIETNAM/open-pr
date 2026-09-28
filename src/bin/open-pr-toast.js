// A toast drawn by open-pr-watch.sh itself on macOS: a borderless panel in the top-right corner.
// Drawing our own window needs no Notifications permission — the system notification centre would
// ask for one, and file it under "Script Editor". Mouse state is read by polling NSEvent's class
// methods, which need no Accessibility permission either.
//   click       → open `url` in the browser, then close
//   ✕ (corner)  → close
//   1h (by ✕)   → no toasts for an hour on this machine (writes the snooze file), then close
//   hover       → the countdown pauses until the pointer leaves
// argv: title, summary, detail (may be empty), event, slot (0 = top), seconds, url (may be empty),
// snooze file (${XDG_CONFIG_HOME:-~/.config}/open-pr/watch/snooze_until, one ISO-8601 UTC line — the
// same file `snooze` writes).
// Every string arrives as argv; nothing here is spliced into source.
ObjC.import('Cocoa');

var ACCENT = {   // sRGB, by event
    review_started: [0.35, 0.53, 0.95], re_review: [0.35, 0.53, 0.95],
    posted: [0.22, 0.7, 0.45], draft_ready: [0.93, 0.68, 0.16],
    question: [0.91, 0.27, 0.06]
};

function run(argv) {
    var title = argv[0] || 'open-pr', summary = argv[1] || '', detail = argv[2] || '';
    var accent = ACCENT[argv[3]] || [0.91, 0.27, 0.06];
    var slot = Number(argv[4] || 0), secs = Number(argv[5] || 8), url = argv[6] || '';
    var snoozeFile = argv[7] || '';

    var app = $.NSApplication.sharedApplication;
    app.setActivationPolicy($.NSApplicationActivationPolicyAccessory);

    var W = 380, H = detail ? 90 : 70, M = 16, GAP = 8, SLOT_H = 90;
    var scr = $.NSScreen.mainScreen.visibleFrame;
    var x = scr.origin.x + scr.size.width - W - M;
    var y = scr.origin.y + scr.size.height - M - slot * (SLOT_H + GAP) - H;
    var win = $.NSPanel.alloc.initWithContentRectStyleMaskBackingDefer(
        $.NSMakeRect(x, y, W, H), $.NSWindowStyleMaskBorderless | $.NSWindowStyleMaskNonactivatingPanel,
        $.NSBackingStoreBuffered, false);
    win.setLevel($.NSStatusWindowLevel);
    win.setOpaque(false);
    win.setBackgroundColor($.NSColor.clearColor);
    win.setHasShadow(true);
    win.setCollectionBehavior($.NSWindowCollectionBehaviorCanJoinAllSpaces |
                              $.NSWindowCollectionBehaviorStationary);

    var view = $.NSView.alloc.initWithFrame($.NSMakeRect(0, 0, W, H));
    view.setWantsLayer(true);
    view.layer.setCornerRadius(10);
    view.layer.setMasksToBounds(true);
    function paint(hover) {
        var g = hover ? 0.25 : 0.19;
        view.layer.setBackgroundColor($.NSColor.colorWithSRGBRedGreenBlueAlpha(g, g + 0.01, g + 0.04, 0.97).CGColor);
    }
    paint(false);

    var bar = $.NSView.alloc.initWithFrame($.NSMakeRect(0, 0, 5, H));
    bar.setWantsLayer(true);
    bar.layer.setBackgroundColor(
        $.NSColor.colorWithSRGBRedGreenBlueAlpha(accent[0], accent[1], accent[2], 1).CGColor);
    view.addSubview(bar);

    function label(text, left, top, width, size, bold, alpha) {
        var t = $.NSTextField.labelWithString(text);
        t.setFrame($.NSMakeRect(left, H - top - size - 6, width, size + 6));
        t.setFont(bold ? $.NSFont.boldSystemFontOfSize(size) : $.NSFont.systemFontOfSize(size));
        t.setTextColor($.NSColor.colorWithSRGBRedGreenBlueAlpha(1, 1, 1, alpha));
        t.setLineBreakMode($.NSLineBreakByTruncatingTail);
        view.addSubview(t);
    }
    label(title, 18, 12, W - 90, 12, true, 0.7);
    if (snoozeFile) label('1h', W - 56, 10, 22, 12, false, 0.55);
    label('✕', W - 26, 10, 16, 12, false, 0.55);
    label(summary, 18, 32, W - 30, 14, true, 1);
    if (detail) label(detail, 18, 56, W - 30, 12, false, 0.75);

    win.setContentView(view);
    win.setAlphaValue(0);
    win.orderFrontRegardless;
    var i;
    for (i = 1; i <= 10; i++) { win.setAlphaValue(i / 10); pause(0.015); }

    var TICK = 0.05, left = secs, wasDown = false, hovering = false;
    while (left > 0) {
        var p = $.NSEvent.mouseLocation;
        var inside = p.x >= x && p.x <= x + W && p.y >= y && p.y <= y + H;
        if (inside !== hovering) { hovering = inside; paint(inside); }
        var down = ($.NSEvent.pressedMouseButtons & 1) === 1;
        if (wasDown && !down && inside) {           // a click released on the toast
            var top = p.y >= y + H - 30;
            var onClose = top && p.x >= x + W - 30;
            var onSnooze = snoozeFile && top && !onClose && p.x >= x + W - 62;
            if (onSnooze) snoozeHour(snoozeFile);
            else if (!onClose && url) $.NSWorkspace.sharedWorkspace.openURL($.NSURL.URLWithString(url));
            break;
        }
        wasDown = down;
        if (!inside) left -= TICK;
        pause(TICK);
    }
    for (i = 9; i >= 0; i--) { win.setAlphaValue(i / 10); pause(0.03); }
    win.orderOut(null);
}

function snoozeHour(file) {   // atomic write: a reader never sees half a line
    var until = new Date(Date.now() + 3600 * 1000).toISOString().replace(/\.\d+Z$/, 'Z');
    $(until + '\n').writeToFileAtomicallyEncodingError(file, true, $.NSUTF8StringEncoding, null);
}

function pause(s) {
    $.NSRunLoop.currentRunLoop.runUntilDate($.NSDate.dateWithTimeIntervalSinceNow(s));
}
