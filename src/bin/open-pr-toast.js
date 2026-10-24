// macOS toast for open-pr-watch.sh notify: our own panel, so no Notifications permission (the
// system centre would ask, and file it under "Script Editor"); mouse state is polled from NSEvent
// class methods, which need no Accessibility permission either.
//   click → focus (below) · hover → countdown pauses and shows ✕ (close), 1h (write the snooze file)
//   and, on a findings toast, Fix now (run fix-now)
// argv: title, summary, detail, event, slot (0 = top), seconds, url, snooze file (the one
// `open-pr-watch.sh snooze` writes, one ISO-8601 UTC line), focus, open command, the
// watcher record fields term, term_session, tty, session_id, pid, host_pid, then — a findings toast only — the
// absolute open-pr-watch.sh, the repo dir, its remote and the PR number "Fix now" passes to
// `open-pr-watch.sh fix-now` (each "" on any other toast), then the file to create once the toast
// is on screen (`notify` waits for it). A leading --probe (`open-pr.sh selftest`): the toast is drawn
// fully transparent, creates that file, and quits.
// Colours are NSBox fills and borders: a layer colour handed through the bridge crashes osascript on an Intel Mac.
// focus: pr → open url · watcher → the watcher's terminal tab, or its session reopened (reopen)
// when that tab is gone · session → the open command in the watcher's terminal app (no valid
// command ⇒ watcher). A watcher in a terminal not in TERMS and with no session ⇒ url. The focus
// code mirrors open-pr-menubar.js (goToTab, tabId, hostTty, liveTab, reopen, openSession, termApp,
// attachedTab, openIn, FOCUS): a session already running in a tab is brought forward, not opened again.
// Every string arrives as argv; nothing here is spliced into source: the open command reaches a
// .command file or osascript argv only after matching OPEN_CMD, and is compared with `ps` args only
// then; a tab id and tty (one `ps` lists among them) reach osascript as argv only after matching
// TAB_ID, the pids are only compared with ps output, a session id becomes `claude attach`/`--resume`
// only after matching SESSION_ID,
// the fix-now values reach /bin/sh argv only after their own checks (fixArgs).
ObjC.import('Cocoa');

var OPEN_CMD = /^[a-z-]+ (attach|resume|-r|--resume|--conversation) [A-Za-z0-9._-]+$/;
var TAB_ID = /^[A-Za-z0-9\/._-]{1,128}$/;
var SESSION_ID = /^[0-9a-f-]{8,64}$/;
var REMOTE = /^[A-Za-z0-9._-]+$/;
var TERMS = {   // by TERM_PROGRAM: bundle id
    'iTerm.app': 'com.googlecode.iterm2', 'Apple_Terminal': 'com.apple.Terminal',
    'ghostty': 'com.mitchellh.ghostty', 'WezTerm': 'com.github.wez.wezterm', 'WarpTerminal': 'dev.warp.Warp-Stable'
};
// `on run argv`: the tab id or command is an argument, never source. FOCUS returns "found" so a
// closed tab can be told apart from a found one. argv: the tab id and the tty the watcher runs on
// (liveTab), or a session's tty (attachedTab; iTerm: id ""). w, t and s are positional references
// ("item 1 of every window"): `select w` moves the window to the front, so it comes last or t and s
// resolve in another window.
var FOCUS = {
    'iTerm.app': ['on run argv', 'tell application id "com.googlecode.iterm2"',
        'repeat with w in windows', 'repeat with t in tabs of w', 'repeat with s in sessions of t',
        'if ((item 1 of argv) is "" or (unique id of s) is (item 1 of argv)) and (tty of s) is (item 2 of argv) then',
        'select t', 'select s', 'select w', 'activate', 'return "found"',
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

// The event shows as a badge on the app icon, as a macOS banner shows its sender: SF Symbol, sRGB.
var BADGE = {
    review_started: ['eye.circle.fill', [0.04, 0.52, 1]], re_review: ['eye.circle.fill', [0.04, 0.52, 1]],
    posted: ['checkmark.circle.fill', [0.2, 0.78, 0.35]], draft_ready: ['pencil.circle.fill', [1, 0.62, 0.04]],
    findings: ['hammer.circle.fill', [1, 0.62, 0.04]],
    question: ['questionmark.circle.fill', [1, 0.42, 0.04]], error: ['exclamationmark.circle.fill', [1, 0.23, 0.19]]
};
// docs/images/logo/favicon.svg (viewBox 128×128), as open-pr-menubar.js draws it.
var MOTH = [
    ['#FFC49E', [54,36, 6,12, 2,54, 24,90, 50,84]], ['#FFC49E', [78,84, 104,90, 126,54, 122,12, 74,36]],
    ['#FF8A50', [54,40, 14,28, 10,52, 50,76]],      ['#FF8A50', [78,76, 118,52, 114,28, 74,40]],
    ['#FF8A50', [56,32, 64,27, 30,6, 21,16]],       ['#FF8A50', [107,16, 98,6, 64,27, 72,32]],
    ['#A32C06', [55,26, 73,26, 71,94, 64,110, 57,94]]
];
var EYESPOTS = [[26,32, 38,44, 26,56, 14,44], [114,44, 102,56, 90,44, 102,32]];

// Geometry of a macOS notification banner. The window is wider than the card by OUT on the left
// and top, so the hover close button can sit on the card's corner as the system one does.
var W = 344, PAD = 14, ICON = 36, RADIUS = 16, OUT = 8, M = 10, GAP = 8, SLOT_H = 76, CLOSE = 18;

function run(argv) {
    var probe = argv[0] === '--probe';
    if (probe) argv = argv.slice(1);
    var title = argv[0] || 'open-pr', summary = argv[1] || '', detail = argv[2] || '';
    var badge = BADGE[argv[3]] || BADGE.question;
    var slot = Number(argv[4] || 0), secs = Number(argv[5] || 8);
    var snoozeFile = argv[7] || '', shown = /^\/.*\/shown$/.test(argv[20] || '') ? argv[20] : '';
    var where = clickTarget(argv), fix = fixArgs(argv);

    var app = $.NSApplication.sharedApplication;
    app.setActivationPolicy($.NSApplicationActivationPolicyAccessory);
    var dark = isDark(app);

    var H = PAD + 17 + 17 + (detail ? 17 : 0) + PAD - 2;
    var scr = $.NSScreen.mainScreen.visibleFrame;
    var x = scr.origin.x + scr.size.width - W - M - OUT;       // window origin; the card sits at OUT, 0
    var y = scr.origin.y + scr.size.height - M - slot * (SLOT_H + GAP) - H - OUT;
    var win = $.NSPanel.alloc.initWithContentRectStyleMaskBackingDefer(
        $.NSMakeRect(x, y, W + OUT, H + OUT), $.NSWindowStyleMaskBorderless | $.NSWindowStyleMaskNonactivatingPanel,
        $.NSBackingStoreBuffered, false);
    win.setLevel($.NSStatusWindowLevel);
    win.setOpaque(false);
    win.setBackgroundColor($.NSColor.clearColor);
    win.setHasShadow(true);
    // FullScreenAuxiliary: shown over a full-screen app, where the user usually is.
    win.setCollectionBehavior($.NSWindowCollectionBehaviorFullScreenAuxiliary | $.NSWindowCollectionBehaviorCanJoinAllSpaces |
                              $.NSWindowCollectionBehaviorStationary);

    var root = $.NSView.alloc.initWithFrame($.NSMakeRect(0, 0, W + OUT, H + OUT));
    root.setWantsLayer(true);
    // The system banner material: blurred desktop behind, light or dark with the system.
    var card = $.NSVisualEffectView.alloc.initWithFrame($.NSMakeRect(OUT, 0, W, H));
    card.setMaterial($.NSVisualEffectMaterialPopover);
    card.setBlendingMode($.NSVisualEffectBlendingModeBehindWindow);
    card.setState($.NSVisualEffectStateActive);
    card.setMaskImage(roundedMask(RADIUS));
    root.addSubview(card);
    // the banner's hairline edge
    root.addSubview(pill($.NSMakeRect(OUT, 0, W, H), $.NSColor.clearColor, dark ? gray(1, 0.18) : gray(0, 0.12), RADIUS));

    var iconTop = PAD;
    var icon = $.NSImageView.imageViewWithImage(mothImage(ICON));
    icon.setFrame($.NSMakeRect(PAD, H - iconTop - ICON, ICON, ICON));
    card.addSubview(icon);
    var sym = symbol(badge);
    if (sym) {
        var B = 17, bx = PAD + ICON - B + 3, by = H - iconTop - ICON - 3;
        card.addSubview(pill($.NSMakeRect(bx, by, B, B), dark ? gray(0.17, 1) : gray(1, 1), $.NSColor.clearColor));
        var bv = $.NSImageView.imageViewWithImage(sym);
        bv.setFrame($.NSMakeRect(bx + 1, by + 1, B - 2, B - 2));
        card.addSubview(bv);   // a sibling: an NSBox insets what it contains
    }

    var tx = PAD + ICON + 10, tw = W - tx - PAD, labels = [];
    // tone: the grey (light, dark) a line with severity marks takes. Attributed text in this vibrant
    // card draws without vibrancy, where the dynamic colours turn dim on dark.
    function label(text, top, weight, color, tone) {
        var t = $.NSTextField.labelWithString(text);
        t.setFrame($.NSMakeRect(tx, H - top - 17, tw, 17));
        t.setFont($.NSFont.systemFontOfSizeWeight(13, weight));
        t.setTextColor(color);
        t.setLineBreakMode($.NSLineBreakByTruncatingTail);
        if (tone && /🔴|🟠|🔵|📝/.test(text)) {
            var a = t.attributedStringValue.mutableCopy;
            a.addAttributeValueRange('NSColor', gray(tone[dark ? 1 : 0], 1), $.NSMakeRange(0, text.length));
            t.setAttributedStringValue(smallMarks(a, 0, text, 13));
        }
        card.addSubview(t);
        labels.push(t);
    }
    label(title, PAD - 2, $.NSFontWeightSemibold, $.NSColor.labelColor);
    label(summary, PAD + 15, $.NSFontWeightRegular, $.NSColor.labelColor, [0.15, 0.93]);
    if (detail) label(detail, PAD + 32, $.NSFontWeightRegular, $.NSColor.secondaryLabelColor, [0.45, 0.9]);

    // Shown on hover only, as the system banner shows its close button and actions.
    var hoverViews = [], buttons = [];
    var close = pill($.NSMakeRect(OUT - CLOSE / 2 + 2, H - CLOSE / 2 - 2, CLOSE, CLOSE), dark ? gray(0.3, 1) : gray(0.98, 1),
                     dark ? gray(1, 0.2) : gray(0, 0.15));
    var xm = symbol(['xmark', null], 7);
    hoverViews.push(close);
    if (xm) {
        var xv = $.NSImageView.imageViewWithImage(xm);
        xv.setFrame($.NSMakeRect(OUT - CLOSE / 2 + 6, H - CLOSE / 2 + 2, CLOSE - 8, CLOSE - 8));
        hoverViews.push(xv);
    }
    function button(text, act) {
        var font = $.NSFont.systemFontOfSizeWeight(12, $.NSFontWeightMedium);
        var bw = Math.ceil($(text).sizeWithAttributes($({ NSFont: font })).width) + 20, bh = 22;
        var right = buttons.length ? buttons[buttons.length - 1].left - 6 : OUT + W - PAD + 4;
        var left = right - bw, b = pill($.NSMakeRect(left, (H - bh) / 2, bw, bh), dark ? gray(0.36, 1) : gray(0.9, 1),
                                         dark ? gray(1, 0.12) : gray(0, 0.08));
        var t = $.NSTextField.labelWithString(text);
        t.setFont(font);
        t.setTextColor($.NSColor.labelColor);
        // centred by frame: JXA's NSTextAlignmentCenter carries the Intel value, "right" on Apple silicon
        var iw = t.intrinsicContentSize.width;
        t.setFrame($.NSMakeRect(left + (bw - iw) / 2, (H - bh) / 2 + 3, iw, 16));
        hoverViews.push(b, t);   // siblings: an NSBox insets what it contains
        buttons.push({ left: left, right: right, bottom: (H - bh) / 2, top: (H + bh) / 2, act: act });
    }
    if (snoozeFile) button('1h', function () { snoozeHour(snoozeFile); });
    if (fix) button('Fix now', function () { spawn('/bin/sh', fix); });
    hoverViews.forEach(function (v) { v.setHidden(true); root.addSubview(v); });

    win.setContentView(root);
    if (probe) {
        win.setAlphaValue(0);
        win.setIgnoresMouseEvents(true);
        win.orderFrontRegardless;
        win.displayIfNeeded;
        if (shown) $('').writeToFileAtomicallyEncodingError(shown, true, $.NSUTF8StringEncoding, null);
        win.orderOut(null);
        return;
    }
    // Slides in from the right edge, easing out, as a banner arrives.
    var i, from = W + OUT + M;
    win.setAlphaValue(0);
    win.orderFrontRegardless;
    for (i = 1; i <= 14; i++) {
        var k = 1 - Math.pow(1 - i / 14, 3);
        win.setFrameOrigin($.NSMakePoint(x + from * (1 - k), y));
        win.setAlphaValue(Math.min(1, k * 1.4));
        pause(0.012);
    }
    win.invalidateShadow;
    if (shown) $('').writeToFileAtomicallyEncodingError(shown, true, $.NSUTF8StringEncoding, null);

    var TICK = 0.05, left = secs, wasDown = false, hovering = false;
    while (left > 0) {
        var p = $.NSEvent.mouseLocation, lx = p.x - x, ly = p.y - y;
        var onCard = lx >= OUT && lx <= OUT + W && ly >= 0 && ly <= H;
        var onClose = hovering && Math.pow(lx - (OUT + 2), 2) + Math.pow(ly - (H - 2), 2) <= Math.pow(CLOSE / 2 + 2, 2);
        var inside = onCard || onClose;
        if (inside !== hovering) {
            hovering = inside;
            hoverViews.forEach(function (v) { v.setHidden(!inside); });
            // the text makes room for the buttons rather than running under them
            var room = inside && buttons.length ? OUT + W - PAD - buttons[buttons.length - 1].left + 4 : 0;
            labels.forEach(function (t, n) { if (n) t.setFrameSize($.NSMakeSize(tw - room, 17)); });
        }
        var down = ($.NSEvent.pressedMouseButtons & 1) === 1;
        if (wasDown && !down && inside) {
            var hit = buttons.filter(function (b) { return lx >= b.left && lx <= b.right && ly >= b.bottom && ly <= b.top; })[0];
            if (hit) hit.act();
            else if (!onClose) focus(where);
            break;
        }
        wasDown = down;
        if (!inside) left -= TICK;
        pause(TICK);
    }
    for (i = 9; i >= 0; i--) { win.setAlphaValue(i / 10); pause(0.025); }
    win.orderOut(null);
}

// Severity marks in s from `at` on, `text` long, at about the x-height of text `size` points high and
// centred on it: at the text's own size they outweigh its words. Opaque black: a translucent text
// colour tints the colour glyph. Same in open-pr-menubar.js.
function smallMarks(s, at, text, size) {
    var re = /🔴|🟠|🔵|📝/g, m, font = $.NSFont.systemFontOfSize(Math.round(size * 0.7));
    while ((m = re.exec(text))) {
        var r = $.NSMakeRange(at + m.index, m[0].length);
        s.addAttributeValueRange('NSFont', font, r);
        s.addAttributeValueRange('NSBaselineOffset', $(size * 0.1), r);
        s.addAttributeValueRange('NSColor', $.NSColor.blackColor, r);
    }
    return s;
}
function isDark(app) {
    var a = app.effectiveAppearance.bestMatchFromAppearancesWithNames($([$.NSAppearanceNameAqua, $.NSAppearanceNameDarkAqua]));
    return ObjC.unwrap(a) === ObjC.unwrap($.NSAppearanceNameDarkAqua);
}
// A rounded box drawn by AppKit itself (a layer colour is not drawn in a view added hidden); radius
// defaults to half its short side.
function pill(frame, fill, border, radius) {
    var b = $.NSBox.alloc.initWithFrame(frame);
    b.setBoxType($.NSBoxCustom);
    b.setTitlePosition($.NSNoTitle);
    b.setContentViewMargins($.NSMakeSize(0, 0));
    b.setCornerRadius(radius || Math.min(frame.size.width, frame.size.height) / 2);
    b.setFillColor(fill);
    b.setBorderWidth(0.5);
    b.setBorderColor(border);
    return b;
}
function gray(w, a) { return $.NSColor.colorWithSRGBRedGreenBlueAlpha(w, w, w, a); }
// Stretchable rounded-rect mask: corners kept, middle stretched.
function roundedMask(r) {
    var n = 2 * r + 1, img = $.NSImage.alloc.initWithSize($.NSMakeSize(n, n));
    img.lockFocus;
    $.NSColor.blackColor.set;
    $.NSBezierPath.bezierPathWithRoundedRectXRadiusYRadius($.NSMakeRect(0, 0, n, n), r, r).fill;
    img.unlockFocus;
    img.setCapInsets($.NSEdgeInsetsMake(r, r, r, r));
    img.setResizingMode($.NSImageResizingModeStretch);
    return img;
}
// spec: [SF Symbol name, sRGB or null for the label colour]. Description '': JXA passes null as
// NSNull, which AppKit rejects.
function symbol(spec, pt) {
    var img = $.NSImage.imageWithSystemSymbolNameAccessibilityDescription(spec[0], '');
    if (img.isNil()) return null;
    var conf = $.NSImageSymbolConfiguration.configurationWithPointSizeWeight(pt || 15, $.NSFontWeightBold);
    if (spec[1]) conf = conf.configurationByApplyingConfiguration($.NSImageSymbolConfiguration.configurationWithPaletteColors(
        $([$.NSColor.whiteColor, $.NSColor.colorWithSRGBRedGreenBlueAlpha(spec[1][0], spec[1][1], spec[1][2], 1)])));
    var out = img.imageWithSymbolConfiguration(conf);
    return out.isNil() ? img : out;
}
function mothImage(pt) {   // 3× bitmap for sharpness
    var px = pt * 3, k = px / 128;
    var rep = $.NSBitmapImageRep.alloc.initWithBitmapDataPlanesPixelsWidePixelsHighBitsPerSampleSamplesPerPixelHasAlphaIsPlanarColorSpaceNameBytesPerRowBitsPerPixel(
        null, px, px, 8, 4, true, false, 'NSDeviceRGBColorSpace', 0, 0);
    $.NSGraphicsContext.saveGraphicsState;
    $.NSGraphicsContext.setCurrentContext($.NSGraphicsContext.graphicsContextWithBitmapImageRep(rep));
    MOTH.forEach(function (m) { hexColor(m[0]).set; polygon(m[1], k).fill; });
    hexColor('#A32C06').set;
    EYESPOTS.forEach(function (e) { polygon(e, k).fill; });
    $.NSGraphicsContext.restoreGraphicsState;
    rep.setSize($.NSMakeSize(pt, pt));
    var img = $.NSImage.alloc.initWithSize($.NSMakeSize(pt, pt));
    img.addRepresentation(rep);
    return img;
}
function hexColor(h) {
    var n = parseInt(h.slice(1), 16);
    return $.NSColor.colorWithSRGBRedGreenBlueAlpha((n >> 16 & 255) / 255, (n >> 8 & 255) / 255, (n & 255) / 255, 1);
}
function polygon(pts, k) {   // SVG y grows downward, AppKit's upward
    var p = $.NSBezierPath.bezierPath;
    for (var i = 0; i < pts.length; i += 2) {
        var pt = $.NSMakePoint(pts[i] * k, (128 - pts[i + 1]) * k);
        if (i === 0) p.moveToPoint(pt); else p.lineToPoint(pt);
    }
    p.closePath;
    return p;
}

function clickTarget(argv) {
    return { focus: argv[8] || 'pr', url: argv[6] || '', open: argv[9] || '', snoozeFile: argv[7] || '',
             term: argv[10] || '', term_session: argv[11] || '', tty: argv[12] || '', session_id: argv[13] || '',
             pids: argv[14] ? [argv[14]] : [], hosts: argv[15] ? [argv[15]] : [] };
}
// `open-pr-watch.sh fix-now` argv, or null when any value is outside its shape.
function fixArgs(argv) {
    var sh = argv[16] || '', dir = argv[17] || '', remote = argv[18] || '', pr = argv[19] || '';
    var fm = $.NSFileManager.defaultManager, isDir = Ref();
    if (!/^\/.*\/open-pr-watch\.sh$/.test(sh) || !fm.fileExistsAtPath(sh)) return null;
    if (dir.charAt(0) !== '/' || !fm.fileExistsAtPathIsDirectory(dir, isDir) || !isDir[0]) return null;
    if ((remote && !REMOTE.test(remote)) || !/^[0-9]+$/.test(pr)) return null;
    return [sh, 'fix-now', '--repo-dir', dir].concat(remote ? ['--remote', remote] : [], ['--pr', pr]);
}
function focus(o) {
    if (o.focus === 'session' && openSession(o.term, o.open, o.snoozeFile)) return;
    if ((o.focus === 'session' || o.focus === 'watcher') && goToTab(o)) return;
    if (/^https?:\/\/\S+$/.test(o.url)) $.NSWorkspace.sharedWorkspace.openURL($.NSURL.URLWithString(o.url));
}
// The terminal app openIn runs a command in, by TERM_PROGRAM: none recorded ⇒ iTerm while it runs
// (the user then works in it); one openIn cannot drive ⇒ Terminal.
function termApp(term) {
    if (term === 'iTerm.app' || term === 'ghostty' || term === 'WezTerm') return term;
    if (!term && $.NSRunningApplication.runningApplicationsWithBundleIdentifier('com.googlecode.iterm2').count > 0) return 'iTerm.app';
    return 'Apple_Terminal';
}
function bundleId(term) { return TERMS[term]; }
// FOCUS argv for the tab of app (a termApp value) where cmd already runs: the process on a tty whose
// args are exactly cmd, the newest (highest pid) of several; null when none or app has no FOCUS.
// ps: the output of `ps -A -o pid=,ppid=,tty=,args=`.
function attachedTab(app, cmd, ps) {
    var pid = -1, tty = '';
    if (!FOCUS[app] || !OPEN_CMD.test(cmd)) return null;
    String(ps || '').split('\n').forEach(function (l) {
        var f = /^\s*(\d+)\s+\d+\s+(\S+)\s+(.*)$/.exec(l);
        if (f && f[3].trim() === cmd && !/^(\?\??|-)$/.test(f[2]) && +f[1] > pid) { pid = +f[1]; tty = '/dev/' + f[2]; }
    });
    if (!TAB_ID.test(tty)) return null;
    return app === 'iTerm.app' ? ['', tty] : [tty, tty];
}
// Brings forward the tab where cmd already runs (attachedTab), else runs cmd in a new one (openIn): a
// second `attach` shows one session in two tabs. Tab not found ('') ⇒ a new one. A lookup that failed
// or still waits on its permission prompt (null) opens nothing, as in goToTab: ps saw the session on a
// tty, so its tab is there and a new one would be the duplicate; its app was brought forward.
function openSession(term, cmd, snooze) {
    var app = termApp(term), tab = attachedTab(app, cmd, output('/bin/ps', ['-A', '-o', 'pid=,ppid=,tty=,args=']));
    if (!tab) return openIn(term, cmd, snooze);
    spawn('/usr/bin/open', ['-b', bundleId(app)]);
    return output('/usr/bin/osascript', script(FOCUS[app]).concat(tab)) !== '' || openIn(term, cmd, snooze);
}
// Runs cmd in a new tab of the terminal app termApp(term) names. iTerm does not run a .command file
// handed to it (LaunchServices then falls back to Terminal), so it gets the command over AppleScript;
// Terminal opens the file via LaunchServices, which needs no Automation permission; Ghostty and
// WezTerm take it as a program.
function openIn(term, cmd, snooze) {
    if (!OPEN_CMD.test(cmd)) return false;
    term = termApp(term);
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
function tabId(w) {
    if (w.term === 'iTerm.app') return w.term_session.split(':').pop();
    if (w.term === 'Apple_Terminal' && w.tty) return w.tty.charAt(0) === '/' ? w.tty : '/dev/' + w.tty;
    return '';
}
// The tty of pid or of its nearest ancestor that has one, as ancestor_tty in open-pr-watch.sh
// records it; '' once pid is gone. ps: the output of `ps -A -o pid=,ppid=,tty=`.
function hostTty(ps, pid) {
    var up = {};
    String(ps || '').split('\n').forEach(function (l) {
        var f = l.trim().split(/\s+/);
        if (f.length === 3) up[f[0]] = f;
    });
    for (var p = String(pid), i = 0; up[p] && i < 15; p = up[p][1], i++) {
        if (!/^(\?\??|-)$/.test(up[p][2])) return up[p][2];
    }
    return '';
}
// [tab id, its tty] while a watcher pid — its wait, or the `claude` running it (between waits no wait
// runs) — still runs on the tty of the tab recorded, else null: the tab is closed, or it now runs
// something else — the user quit `claude` there (the session went on in the background), or a
// background session inherited the tab of the `claude` that started it.
function liveTab(w, ps) {
    var id = tabId(w), pids = w.pids.concat(w.hosts || []);
    if (!TAB_ID.test(id)) return null;
    for (var i = 0; i < pids.length; i++) {
        var t = hostTty(ps, pids[i]), tty = '/dev/' + t;
        if (t && TAB_ID.test(tty) && (w.term !== 'Apple_Terminal' || tty === id)) return [id, tty];
    }
    return null;
}
// What brings back a watcher session whose tab was not found, or '' while its `claude` runs (the session
// is open in a tab; a resume would start a second copy). Listed by `claude agents --json` (agents():
// its output, null when it did not run) as a background job ⇒ attach; not listed ⇒ resume. No host
// recorded, or no listing ⇒ attach: resuming blind might start that copy.
function reopen(w, ps, agents) {
    var hosts = w.hosts || [], up = String(ps || '').split('\n').map(function (l) { return l.trim().split(/\s+/)[0]; });
    if (!SESSION_ID.test(w.session_id)) return '';
    if (hosts.some(function (h) { return ps === null || up.indexOf(String(h)) >= 0; })) return '';
    var attach = 'claude attach ' + w.session_id.slice(0, 8), out = hosts.length ? agents() : null, list = [];
    if (out === null) return attach;
    // A listing that cannot be read may hide the job: attach only fails, a resume would copy it.
    try { list = JSON.parse(out); } catch (e) { return attach; }
    if (!Array.isArray(list)) return attach;
    var job = list.filter(function (a) {
        return a && a.sessionId === w.session_id && (a.kind === undefined || a.kind === 'background');
    })[0];
    if (!job) return 'claude --resume ' + w.session_id;
    return /^[0-9a-f]{8,64}$/.test(job.id) ? 'claude attach ' + job.id : attach;
}
// A tab that is gone (the user quit `claude`, which keeps the watcher's session running in the
// background) is reopened (reopen).
function goToTab(o) {
    var t = TERMS[o.term], sid = SESSION_ID.test(o.session_id) ? o.session_id : '';
    if (!t && !sid) return false;
    // Needs no permission, so the app comes forward even when the tab lookup is refused. Via
    // LaunchServices: an accessory app's own activate request is ignored by macOS.
    if (t) spawn('/usr/bin/open', ['-b', t]);
    var ps = output('/bin/ps', ['-A', '-o', 'pid=,ppid=,tty=']);
    var src = FOCUS[o.term], tab = src ? liveTab(o, ps) : null;
    var found = tab ? output('/usr/bin/osascript', script(src).concat(tab)) : '';
    // null: the lookup failed (no permission) — the tab may be there.
    var cmd = found === '' ? reopen(o, ps, function () { return output('/usr/bin/env', ['claude', 'agents', '--json']); }) : '';
    if (cmd) openSession(o.term, cmd, o.snoozeFile);
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
