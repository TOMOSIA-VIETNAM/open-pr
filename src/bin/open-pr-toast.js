// macOS toast for open-pr-watch.sh notify: our own panel, so no Notifications permission (the
// system centre would ask, and file it under "Script Editor"); mouse state is polled from NSEvent
// class methods, which need no Accessibility permission either.
//   click → focus (below) · ✕ → close · 1h → write the snooze file · hover → countdown pauses
// argv: title, summary, detail, event, slot (0 = top), seconds, url, snooze file (the one
// `open-pr-watch.sh snooze` writes, one ISO-8601 UTC line), focus, open command, and the
// watcher.json fields term, term_session, tty, session_id.
// focus: pr → open url · watcher → the watcher's terminal tab, or `claude attach` of its session
// when that tab is gone · session → the open command in the watcher's terminal app (no valid
// command ⇒ watcher). A watcher in a terminal not in TERMS and with no session ⇒ url. The focus
// code mirrors open-pr-menubar.js (goToTab, openIn).
// Every string arrives as argv; nothing here is spliced into source: the open command reaches a
// .command file or osascript argv only after matching OPEN_CMD, a tab id reaches osascript as argv
// only after matching TAB_ID, a session id becomes `claude attach` only after matching SESSION_ID.
ObjC.import('Cocoa');

var OPEN_CMD = /^[a-z-]+ (attach|resume|-r|--resume|--conversation) [A-Za-z0-9._-]+$/;
var TAB_ID = /^[A-Za-z0-9\/._-]{1,128}$/;
var SESSION_ID = /^[0-9a-f-]{8,64}$/;
var TERMS = {   // by TERM_PROGRAM: bundle id
    'iTerm.app': 'com.googlecode.iterm2', 'Apple_Terminal': 'com.apple.Terminal',
    'ghostty': 'com.mitchellh.ghostty', 'WezTerm': 'com.github.wez.wezterm', 'WarpTerminal': 'dev.warp.Warp-Stable'
};
// `on run argv`: the tab id or command is an argument, never source. FOCUS returns "found" so a
// closed tab can be told apart from a found one.
var FOCUS = {
    'iTerm.app': ['on run argv', 'tell application id "com.googlecode.iterm2"',
        'repeat with w in windows', 'repeat with t in tabs of w', 'repeat with s in sessions of t',
        'if (unique id of s) is (item 1 of argv) then', 'select w', 'select t', 'select s', 'activate', 'return "found"',
        'end if', 'end repeat', 'end repeat', 'end repeat', 'end tell', 'end run'],
    'Apple_Terminal': ['on run argv', 'tell application id "com.apple.Terminal"',
        'repeat with w in windows', 'repeat with t in tabs of w', 'if (tty of t) is (item 1 of argv) then',
        'set selected of t to true', 'set index of w to 1', 'activate', 'return "found"',
        'end if', 'end repeat', 'end repeat', 'end tell', 'end run']
};
// `write text` types into the user's login shell, so PATH has `claude`.
var ITERM_NEW_TAB = ['on run argv', 'tell application id "com.googlecode.iterm2"', 'activate',
    'if (count of windows) > 0 then', 'tell current window to create tab with default profile',
    'else', 'create window with default profile', 'end if',
    'tell current session of current window to write text (item 1 of argv)', 'end tell', 'end run'];

var ACCENT = {   // sRGB, by event
    review_started: [0.35, 0.53, 0.95], re_review: [0.35, 0.53, 0.95],
    posted: [0.22, 0.7, 0.45], draft_ready: [0.93, 0.68, 0.16],
    question: [0.91, 0.27, 0.06], error: [0.86, 0.15, 0.15]
};

function run(argv) {
    var title = argv[0] || 'open-pr', summary = argv[1] || '', detail = argv[2] || '';
    var accent = ACCENT[argv[3]] || [0.91, 0.27, 0.06];
    var slot = Number(argv[4] || 0), secs = Number(argv[5] || 8);
    var snoozeFile = argv[7] || '';
    var where = clickTarget(argv);

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
    // FullScreenAuxiliary: shown over a full-screen app, where the user usually is.
    win.setCollectionBehavior($.NSWindowCollectionBehaviorFullScreenAuxiliary | $.NSWindowCollectionBehaviorCanJoinAllSpaces |
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
        if (wasDown && !down && inside) {
            var top = p.y >= y + H - 30;
            var onClose = top && p.x >= x + W - 30;
            var onSnooze = snoozeFile && top && !onClose && p.x >= x + W - 62;
            if (onSnooze) snoozeHour(snoozeFile);
            else if (!onClose) focus(where);
            break;
        }
        wasDown = down;
        if (!inside) left -= TICK;
        pause(TICK);
    }
    for (i = 9; i >= 0; i--) { win.setAlphaValue(i / 10); pause(0.03); }
    win.orderOut(null);
}

function clickTarget(argv) {
    return { focus: argv[8] || 'pr', url: argv[6] || '', open: argv[9] || '', snoozeFile: argv[7] || '',
             term: argv[10] || '', term_session: argv[11] || '', tty: argv[12] || '', session_id: argv[13] || '' };
}
function focus(o) {
    if (o.focus === 'session' && openIn(o.term, o.open, o.snoozeFile)) return;
    if ((o.focus === 'session' || o.focus === 'watcher') && goToTab(o)) return;
    if (/^https?:\/\/\S+$/.test(o.url)) $.NSWorkspace.sharedWorkspace.openURL($.NSURL.URLWithString(o.url));
}
// Runs cmd in a new tab of the terminal `term` names. iTerm does not run a .command file handed to
// it (LaunchServices then falls back to Terminal), so it gets the command over AppleScript;
// Terminal opens the file via LaunchServices, which needs no Automation permission; Ghostty and
// WezTerm take it as a program; any other terminal ⇒ Terminal.
function openIn(term, cmd, snooze) {
    if (!OPEN_CMD.test(cmd)) return false;
    if (term === 'iTerm.app') return spawn('/usr/bin/osascript', script(ITERM_NEW_TAB).concat([cmd]));
    if (!snooze) return false;
    var dir = snooze.replace(/\/[^\/]*$/, '') + '/sessions', fm = $.NSFileManager.defaultManager;
    fm.createDirectoryAtPathWithIntermediateDirectoriesAttributesError(dir, true, $({}), null);
    var path = dir + '/' + cmd.split(' ').pop() + '.command';
    if (!$('#!/bin/sh\n' + cmd + '\n').writeToFileAtomicallyEncodingError(path, true, $.NSUTF8StringEncoding, null)) return false;
    fm.setAttributesOfItemAtPathError($({ NSFilePosixPermissions: 493 }), path, null);   // 0755
    if (term === 'ghostty') return spawn('/usr/bin/open', ['-na', 'Ghostty', '--args', '-e', '/bin/sh', path]);
    if (term === 'WezTerm') return spawn('/usr/bin/open', ['-na', 'WezTerm', '--args', 'start', '--', '/bin/sh', path]);
    return $.NSWorkspace.sharedWorkspace.openFileWithApplication(path, 'Terminal');
}
function script(lines) { var a = []; lines.forEach(function (l) { a.push('-e', l); }); return a; }
// A tab that is gone (the user quit `claude`, which keeps the watcher's session running in the
// background) is reopened with `claude attach`.
function goToTab(o) {
    var t = TERMS[o.term], sid = SESSION_ID.test(o.session_id) ? o.session_id : '';
    if (!t && !sid) return false;
    // Needs no permission, so the app comes forward even when the tab lookup is refused. Via
    // LaunchServices: an accessory app's own activate request is ignored by macOS.
    if (t) spawn('/usr/bin/open', ['-b', t]);
    var id = o.term === 'iTerm.app' ? o.term_session.split(':').pop()
           : o.term === 'Apple_Terminal' && o.tty ? (o.tty.charAt(0) === '/' ? o.tty : '/dev/' + o.tty) : '';
    var found = FOCUS[o.term] && TAB_ID.test(id) ? output('/usr/bin/osascript', script(FOCUS[o.term]).concat([id])) : '';
    // null: the lookup failed (no permission) — the tab may be there.
    if (found === '' && sid) openIn(o.term, 'claude attach ' + sid.slice(0, 8), o.snoozeFile);
    return true;
}
function newTask(path, args) {
    var task = $.NSTask.alloc.init;
    task.setLaunchPath(path);
    task.setArguments($(args));
    task.setStandardError($.NSFileHandle.fileHandleWithNullDevice);
    return task;
}
function spawn(path, args) {
    var task = newTask(path, args);
    task.setStandardOutput($.NSFileHandle.fileHandleWithNullDevice);
    task.launch;
    return true;
}
function output(path, args) {   // trimmed stdout once the task exits 0, else null
    var task = newTask(path, args), pipe = $.NSPipe.pipe;
    task.setStandardOutput(pipe);
    task.launch;
    task.waitUntilExit;
    if (task.terminationStatus !== 0) return null;
    var out = $.NSString.alloc.initWithDataEncoding(pipe.fileHandleForReading.readDataToEndOfFile, $.NSUTF8StringEncoding);
    return ObjC.unwrap(out).trim();
}

function snoozeHour(file) {   // atomic write: a reader never sees half a line
    var until = new Date(Date.now() + 3600 * 1000).toISOString().replace(/\.\d+Z$/, 'Z');
    $(until + '\n').writeToFileAtomicallyEncodingError(file, true, $.NSUTF8StringEncoding, null);
}

function pause(s) {
    $.NSRunLoop.currentRunLoop.runUntilDate($.NSDate.dateWithTimeIntervalSinceNow(s));
}
