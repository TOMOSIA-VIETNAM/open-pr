// macOS menu bar item for `/open-pr:menubar` (a status item needs no permission). It
// polls, in every data directory given, the files the watcher writes:
//   <data>/<repo>/watch-review/heartbeat    the repo counts as watched while this is fresh
//   <data>/<repo>/watch-review/state.json   sessions; active = not finished, working, question or draft
//   <data>/<repo>/watch-review/feed.jsonl   recent notifications
//   <data>/<repo>/watch-review/watcher.json the terminal tab whose watcher watches the repo
//   snooze file                             toasts off until then; the Snooze menu writes it too
// It stays until the user closes it (the menu, or `menubar --close`); watching goes on either way.
// argv: snooze file, pid file, heartbeat age (seconds) past which a repo is not watched, data dirs.
// File contents are data only: shown as menu titles, opened when they are http(s) URLs, copied
// as text, written into a .command file after matching OPEN_CMD, or passed to osascript as argv
// after matching TAB_ID — never spliced into source.
ObjC.import('Cocoa');

var REFRESH = 3, RECENT = 10, CLIP = 70, HEADER_W = 300;
// The only shape of `open` (see open_cmd in open-pr-watch.sh) allowed into a Terminal script.
var OPEN_CMD = /^[a-z-]+ (attach|resume|-r|--resume|--conversation) [A-Za-z0-9._-]+$/;
// iTerm's unique id (the part of ITERM_SESSION_ID after ':') or a Terminal tab's tty.
var TAB_ID = /^[A-Za-z0-9\/._-]{1,128}$/;
var dataDirs = [], snoozeFile = '', pidFile = '', fresh = 2700;
var item = null, target = null, icons = {};

var STATE = {   // SF Symbol, sRGB tint, label — by a session's last_state
    working:  ['circle.dotted', [0.35, 0.53, 0.95], 'Reviewing'],
    question: ['questionmark.bubble', [0.91, 0.27, 0.06], 'Needs your answer'],
    draft:    ['doc.badge.clock', [0.93, 0.68, 0.16], 'Draft waiting for your approval']
};
// by TERM_PROGRAM: menu name, bundle id, app name for NSWorkspace openFile:withApplication:
var TERMS = {
    'iTerm.app':      ['iTerm', 'com.googlecode.iterm2', 'iTerm'],
    'Apple_Terminal': ['Terminal', 'com.apple.Terminal', 'Terminal'],
    'ghostty':        ['Ghostty', 'com.mitchellh.ghostty', 'Ghostty'],
    'WezTerm':        ['WezTerm', 'com.github.wez.wezterm', 'WezTerm'],
    'WarpTerminal':   ['Warp', 'dev.warp.Warp-Stable', 'Warp']
};
var OPEN_APPS = ['iTerm', 'Terminal', 'Ghostty', 'WezTerm', 'Warp'];
// `on run argv`: the tab id arrives as an argument, never as source. Automation permission
// is asked once; without it the app was already brought forward (goToTab).
var FOCUS = {
    'iTerm.app': [
        'on run argv',
        'tell application id "com.googlecode.iterm2"',
        'repeat with w in windows',
        'repeat with t in tabs of w',
        'repeat with s in sessions of t',
        'if (unique id of s) is (item 1 of argv) then',
        'select w', 'select t', 'select s', 'activate', 'return',
        'end if', 'end repeat', 'end repeat', 'end repeat', 'end tell', 'end run'],
    'Apple_Terminal': [
        'on run argv',
        'tell application id "com.apple.Terminal"',
        'repeat with w in windows',
        'repeat with t in tabs of w',
        'if (tty of t) is (item 1 of argv) then',
        'set selected of t to true', 'set index of w to 1', 'activate', 'return',
        'end if', 'end repeat', 'end repeat', 'end tell', 'end run']
};
var EVENT = {   // SF Symbol, sRGB tint — by feed event; tints match open-pr-toast.js
    review_started: ['eye', [0.35, 0.53, 0.95]],
    re_review:      ['arrow.clockwise', [0.35, 0.53, 0.95]],
    question:       ['questionmark.bubble', [0.91, 0.27, 0.06]],
    draft_ready:    ['doc.badge.clock', [0.93, 0.68, 0.16]],
    posted:         ['checkmark.bubble', [0.22, 0.7, 0.45]]
};

// docs/images/logo/favicon.svg (viewBox 128×128).
var MOTH = [
    ['#FFC49E', [54,36, 6,12, 2,54, 24,90, 50,84]], ['#FFC49E', [78,84, 104,90, 126,54, 122,12, 74,36]],
    ['#FF8A50', [54,40, 14,28, 10,52, 50,76]],      ['#FF8A50', [78,76, 118,52, 114,28, 74,40]],
    ['#FF8A50', [56,32, 64,27, 30,6, 21,16]],       ['#FF8A50', [107,16, 98,6, 64,27, 72,32]],
    ['#A32C06', [55,26, 73,26, 71,94, 64,110, 57,94]]
];
var EYESPOTS = [[26,32, 38,44, 26,56, 14,44], [114,44, 102,56, 90,44, 102,32]];

ObjC.registerSubclass({
    name: 'OPRMenuTarget',
    methods: {
        'tick:': { types: ['void', ['id']], implementation: function () { refresh(); } },
        'openURL:': { types: ['void', ['id']], implementation: function (s) { openURL(unwrapString(s.representedObject)); } },
        'copyText:': { types: ['void', ['id']], implementation: function (s) { copyText(unwrapString(s.representedObject)); } },
        'openTerminal:': { types: ['void', ['id']], implementation: function (s) { openTerminal(parse(unwrapString(s.representedObject))); } },
        'goToTab:': { types: ['void', ['id']], implementation: function (s) { goToTab(parse(unwrapString(s.representedObject))); } },
        'snooze:': { types: ['void', ['id']], implementation: function (s) { snooze(Number(s.tag)); } },
        'quit:': { types: ['void', ['id']], implementation: function () { leave(); } }
    }
});

function run(argv) {
    snoozeFile = argv[0] || ''; pidFile = argv[1] || '';
    fresh = Number(argv[2]) || fresh;
    dataDirs = argv.slice(3).filter(function (d) { return typeof d === 'string' && d !== ''; });
    var app = $.NSApplication.sharedApplication;
    app.setActivationPolicy($.NSApplicationActivationPolicyAccessory);
    icons.bar = mothImage(18, true);
    icons.header = mothImage(28, false);
    item = $.NSStatusBar.systemStatusBar.statusItemWithLength(-1);   // -1 = variable length
    item.button.setImage(icons.bar);
    item.button.setImagePosition($.NSImageLeft);
    item.button.setToolTip('open-pr');
    target = $.OPRMenuTarget.alloc.init;
    refresh();
    $.NSTimer.scheduledTimerWithTimeIntervalTargetSelectorUserInfoRepeats(REFRESH, target, 'tick:', null, true);
    app.run;
}

// ------------------------------------------------------------- reading ----
function unwrapString(o) { var v = ObjC.unwrap(o); return typeof v === 'string' ? v : ''; }
function readText(path) {
    var s = $.NSString.stringWithContentsOfFileEncodingError(path, $.NSUTF8StringEncoding, null);
    return s.isNil() ? '' : ObjC.unwrap(s);
}
function listDir(path) {
    var a = $.NSFileManager.defaultManager.contentsOfDirectoryAtPathError(path, null);
    return a.isNil() ? [] : ObjC.deepUnwrap(a);
}
function ageSeconds(path) {
    var at = $.NSFileManager.defaultManager.attributesOfItemAtPathError(path, null);
    if (at.isNil()) return Infinity;
    var d = at.objectForKey($.NSFileModificationDate);
    return d.isNil() ? Infinity : -d.timeIntervalSinceNow;
}
function parse(text) { try { return JSON.parse(text); } catch (e) { return null; } }
function str(v) { return typeof v === 'string' ? v : ''; }
function p2(n) { return (n < 10 ? '0' : '') + n; }
function hhmm(d) { return p2(d.getHours()) + ':' + p2(d.getMinutes()); }
function when(d) {
    var today = new Date();
    if (d.toDateString() === today.toDateString()) return hhmm(d);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) + ' ' + hhmm(d);
}
function snoozedUntil() {
    var d = new Date(readText(snoozeFile).split('\n')[0].trim());
    return isNaN(d.getTime()) || d.getTime() <= Date.now() ? null : d;
}

function basename(p) { return p.replace(/\/+$/, '').split('/').pop() || p; }
// One per watcher tab: the waits of one watcher (one per repo) share its tab.
function watcherOf(w) {
    w = w && typeof w === 'object' ? w : {};
    var term = str(w.term), ts = str(w.term_session), tty = str(w.tty), cwd = str(w.cwd);
    var t = TERMS[term];
    return { key: ts ? 's:' + ts : tty ? 't:' + tty : typeof w.pid === 'number' ? 'p:' + w.pid : '',
             label: (cwd ? basename(cwd) : 'watcher') + (term ? ' · ' + (t ? t[0] : term) : ''),
             term: term, term_session: ts, tty: tty, app: t ? t[2] : 'Terminal',
             repos: [], sessions: [] };
}

function scan() {
    var out = { repos: 0, watchers: [], feed: [] }, byKey = {};
    dataDirs.forEach(function (data) { listDir(data).forEach(function (name) {
        if (typeof name !== 'string' || name.charAt(0) === '.') return;
        var dir = data + '/' + name + '/watch-review';
        if (ageSeconds(dir + '/heartbeat') > fresh) return;
        out.repos++;
        var wr = watcherOf(parse(readText(dir + '/watcher.json')));
        if (!byKey[wr.key]) { byKey[wr.key] = wr; out.watchers.push(wr); }
        wr = byKey[wr.key];
        var st = parse(readText(dir + '/state.json'));
        var ss = st && typeof st.sessions === 'object' && st.sessions ? st.sessions : {};
        Object.keys(ss).sort(function (a, b) { return Number(a) - Number(b); }).forEach(function (pr) {
            var s = ss[pr];
            if (!s || typeof s !== 'object' || s.finished === true || !STATE[s.last_state]) return;
            wr.sessions.push({ label: (str(s.repo) || name) + ' #' + pr, state: s.last_state,
                               url: str(s.url), open: str(s.open) });
        });
        wr.repos.push(name);
        readText(dir + '/feed.jsonl').split('\n').forEach(function (line) {
            var f = parse(line);
            if (f && typeof f === 'object' && str(f.summary)) out.feed.push(f);
        });
    }); });
    out.feed.sort(function (a, b) { return str(b.at) < str(a.at) ? -1 : str(b.at) > str(a.at) ? 1 : 0; });
    out.feed = out.feed.slice(0, RECENT);
    out.watchers.sort(function (a, b) { return a.label < b.label ? -1 : a.label > b.label ? 1 : 0; });
    out.sessions = out.watchers.reduce(function (n, w) { return n + w.sessions.length; }, 0);
    return out;
}

// -------------------------------------------------------------- images ----
function hexColor(h) {
    var n = parseInt(h.slice(1), 16);
    return $.NSColor.colorWithSRGBRedGreenBlueAlpha((n >> 16 & 255) / 255, (n >> 8 & 255) / 255, (n & 255) / 255, 1);
}
function rgb(c) { return $.NSColor.colorWithSRGBRedGreenBlueAlpha(c[0], c[1], c[2], 1); }
function polygon(pts, k) {   // SVG y grows downward, AppKit's upward
    var p = $.NSBezierPath.bezierPath;
    for (var i = 0; i < pts.length; i += 2) {
        var pt = $.NSMakePoint(pts[i] * k, (128 - pts[i + 1]) * k);
        if (i === 0) p.moveToPoint(pt); else p.lineToPoint(pt);
    }
    p.closePath;
    return p;
}
// 3× bitmap for sharpness. A template image is one flat colour the menu bar tints, so the
// eyespots are cleared to holes to stay visible.
function mothImage(pt, template) {
    var px = pt * 3, k = px / 128;
    var rep = $.NSBitmapImageRep.alloc.initWithBitmapDataPlanesPixelsWidePixelsHighBitsPerSampleSamplesPerPixelHasAlphaIsPlanarColorSpaceNameBytesPerRowBitsPerPixel(
        null, px, px, 8, 4, true, false, 'NSDeviceRGBColorSpace', 0, 0);
    var ctx = $.NSGraphicsContext.graphicsContextWithBitmapImageRep(rep);
    $.NSGraphicsContext.saveGraphicsState;
    $.NSGraphicsContext.setCurrentContext(ctx);
    MOTH.forEach(function (m) {
        (template ? $.NSColor.blackColor : hexColor(m[0])).set;
        polygon(m[1], k).fill;
    });
    if (template) ctx.setCompositingOperation($.NSCompositingOperationClear);
    else hexColor('#A32C06').set;
    EYESPOTS.forEach(function (e) { polygon(e, k).fill; });
    ctx.flushGraphics;
    $.NSGraphicsContext.restoreGraphicsState;
    rep.setSize($.NSMakeSize(pt, pt));
    var img = $.NSImage.alloc.initWithSize($.NSMakeSize(pt, pt));
    img.addRepresentation(rep);
    img.setTemplate(template);
    return img;
}
// Description '': JXA passes null as NSNull, which AppKit rejects; VoiceOver reads the item title.
function symbol(spec) {
    var key = spec[0] + spec[1].join();
    if (icons[key]) return icons[key];
    var img = $.NSImage.imageWithSystemSymbolNameAccessibilityDescription(spec[0], '');
    if (img.isNil()) return null;
    var tinted = img.imageWithSymbolConfiguration($.NSImageSymbolConfiguration.configurationWithHierarchicalColor(rgb(spec[1])));
    icons[key] = tinted.isNil() ? img : tinted;
    return icons[key];
}

// ---------------------------------------------------------------- menu ----
function refresh() {
    var s = scan();
    item.button.setTitle(s.sessions ? String(s.sessions) : '');
    item.setMenu(build(s));
}

function clip(t) { return t.length > CLIP ? t.slice(0, CLIP - 1) + '…' : t; }
// Auto-enabling greys out a submenu parent that has no action.
function newMenu(title) {
    var m = $.NSMenu.alloc.initWithTitle(title);
    m.setAutoenablesItems(false);
    return m;
}
function add(menu, title, action, value, tag) {
    var mi = $.NSMenuItem.alloc.initWithTitleActionKeyEquivalent(clip(title), action || null, '');
    mi.setEnabled(!!action);
    if (action) {
        mi.setTarget(target);
        if (value !== undefined) mi.setRepresentedObject($(value));
        if (tag !== undefined) mi.setTag(tag);
    }
    menu.addItem(mi);
    return mi;
}
// Native subtitle from macOS 14.4; before that, the same two lines as an attributed title.
function subtitle(mi, text) {
    if (mi.respondsToSelector('setSubtitle:')) { mi.setSubtitle(clip(text)); return; }
    var s = $.NSMutableAttributedString.alloc.initWithStringAttributes(ObjC.unwrap(mi.title) + '\n',
        $({ NSFont: $.NSFont.menuFontOfSize(0) }));
    s.appendAttributedString($.NSAttributedString.alloc.initWithStringAttributes(clip(text),
        $({ NSFont: $.NSFont.menuFontOfSize(11), NSColor: $.NSColor.secondaryLabelColor })));
    mi.setAttributedTitle(s);
}
function section(menu, title) {
    menu.addItem($.NSMenuItem.separatorItem);
    if ($.NSMenuItem.respondsToSelector('sectionHeaderWithTitle:')) menu.addItem($.NSMenuItem.sectionHeaderWithTitle(title));
    else add(menu, title);
}

function label(text, font, color, x, y) {
    var f = $.NSTextField.labelWithString(text);
    f.setFont(font);
    f.setTextColor(color);
    f.setLineBreakMode($.NSLineBreakByTruncatingTail);
    f.setFrame($.NSMakeRect(x, y, HEADER_W - x - 14, 17));
    return f;
}
function headerView(repos, watchers, until) {
    var v = $.NSView.alloc.initWithFrame($.NSMakeRect(0, 0, HEADER_W, 48));
    var iv = $.NSImageView.imageViewWithImage(icons.header);
    iv.setFrame($.NSMakeRect(14, 10, 28, 28));
    v.addSubview(iv);
    v.addSubview(label('open-pr', $.NSFont.boldSystemFontOfSize(13), $.NSColor.labelColor, 52, 24));
    var line = (repos ? 'Watching ' + repos + (repos === 1 ? ' repo' : ' repos') : 'Not watching') + ' · ' +
               (watchers > 1 ? watchers + ' watchers · ' : '') +
               (until ? 'toasts off until ' + hhmm(until) : 'toasts on');
    v.addSubview(label(line, $.NSFont.systemFontOfSize(11), $.NSColor.secondaryLabelColor, 52, 7));
    return v;
}

function build(s) {
    var m = newMenu('open-pr');
    var until = snoozedUntil();
    var head = $.NSMenuItem.alloc.initWithTitleActionKeyEquivalent('open-pr', null, '');
    head.setView(headerView(s.repos, s.watchers.length, until));
    m.addItem(head);

    section(m, 'In progress');
    s.watchers.forEach(function (w) {
        // A record from before watcher.json existed has no tab to show.
        if (w.key) {
            var wi = add(m, w.label, TERMS[w.term] ? 'goToTab:' : null,
                         JSON.stringify({ term: w.term, term_session: w.term_session, tty: w.tty }));
            subtitle(wi, w.repos.join(', '));
            wi.setImage($.NSImage.imageWithSystemSymbolNameAccessibilityDescription('terminal', ''));
            wi.setToolTip('Go to watcher tab');
        }
        w.sessions.forEach(function (x) {
            var spec = STATE[x.state];
            var mi = add(m, x.label, isURL(x.url) ? 'openURL:' : null, x.url);
            subtitle(mi, spec[2]);
            mi.setImage(symbol(spec));
            if (w.key) mi.setIndentationLevel(1);
            var sub = newMenu(x.label);
            if (isURL(x.url)) add(sub, 'Open pull request', 'openURL:', x.url);
            if (OPEN_CMD.test(x.open)) add(sub, 'Open session in ' + w.app, 'openTerminal:', JSON.stringify({ open: x.open, app: w.app }));
            if (x.open) add(sub, 'Copy command  ' + x.open, 'copyText:', x.open);
            if (sub.numberOfItems > 0) { mi.setSubmenu(sub); mi.setEnabled(true); }
        });
    });
    if (!s.sessions) add(m, 'No review in progress');

    section(m, 'Recent');
    if (!s.feed.length) add(m, 'No toasts yet');
    s.feed.forEach(function (f) {
        var url = str(f.url), d = new Date(str(f.at));
        var mi = add(m, str(f.summary), isURL(url) ? 'openURL:' : null, url);
        subtitle(mi, str(f.repo) + (isNaN(d.getTime()) ? '' : ' · ' + when(d)));
        var spec = EVENT[str(f.event)];
        if (spec) mi.setImage(symbol(spec));
    });

    m.addItem($.NSMenuItem.separatorItem);
    var sub = newMenu('Snooze toasts');
    if (until) add(sub, 'Off until ' + when(until)).setState($.NSControlStateValueOn);
    add(sub, '30 minutes', 'snooze:', undefined, 30);
    add(sub, '1 hour', 'snooze:', undefined, 60);
    add(sub, 'Until 9:00 tomorrow', 'snooze:', undefined, -1);
    sub.addItem($.NSMenuItem.separatorItem);
    if (until) add(sub, 'Turn toasts back on', 'snooze:', undefined, 0);
    else add(sub, 'Toasts on').setState($.NSControlStateValueOn);
    var sn = add(m, 'Snooze toasts');
    sn.setSubmenu(sub);
    sn.setEnabled(true);
    sn.setImage($.NSImage.imageWithSystemSymbolNameAccessibilityDescription(until ? 'bell.slash' : 'bell', ''));
    add(m, 'Quit menu bar', 'quit:').setImage($.NSImage.imageWithSystemSymbolNameAccessibilityDescription('power', ''));
    return m;
}

// ------------------------------------------------------------- actions ----
function isURL(u) { return /^https?:\/\/\S+$/.test(u); }
function openURL(u) { if (isURL(u)) $.NSWorkspace.sharedWorkspace.openURL($.NSURL.URLWithString(u)); }
function copyText(t) {
    if (!t) return;
    var pb = $.NSPasteboard.generalPasteboard;
    pb.clearContents;
    pb.setStringForType($(t), $.NSPasteboardTypeString);
}
// A .command file opened via LaunchServices needs no Automation permission.
function openTerminal(o) {
    var cmd = o ? str(o.open) : '', app = o && OPEN_APPS.indexOf(o.app) >= 0 ? o.app : 'Terminal';
    if (!OPEN_CMD.test(cmd) || !snoozeFile) return;
    var dir = snoozeFile.replace(/\/[^\/]*$/, '') + '/sessions';
    var fm = $.NSFileManager.defaultManager;
    fm.createDirectoryAtPathWithIntermediateDirectoriesAttributesError(dir, true, $({}), null);
    var path = dir + '/' + cmd.split(' ').pop() + '.command';
    if (!$('#!/bin/sh\n' + cmd + '\n').writeToFileAtomicallyEncodingError(path, true, $.NSUTF8StringEncoding, null)) return;
    fm.setAttributesOfItemAtPathError($({ NSFilePosixPermissions: 493 }), path, null);   // 0755
    $.NSWorkspace.sharedWorkspace.openFileWithApplication(path, app);
}
function tabId(w) {
    if (w.term === 'iTerm.app') return w.term_session.split(':').pop();
    if (w.term === 'Apple_Terminal' && w.tty) return w.tty.charAt(0) === '/' ? w.tty : '/dev/' + w.tty;
    return '';
}
function goToTab(w) {
    if (!w || typeof w !== 'object') return;
    w = { term: str(w.term), term_session: str(w.term_session), tty: str(w.tty) };
    var t = TERMS[w.term];
    if (!t) return;
    // Needs no permission, so the app comes forward even when the tab lookup is refused. Via
    // LaunchServices: an accessory app's own activate request is ignored by macOS.
    spawn('/usr/bin/open', ['-b', t[1]]);
    var id = tabId(w), src = FOCUS[w.term];
    if (!src || !TAB_ID.test(id)) return;
    var args = [];
    src.forEach(function (l) { args.push('-e', l); });
    spawn('/usr/bin/osascript', args.concat([id]));
}
function spawn(path, args) {
    var task = $.NSTask.alloc.init;
    task.setLaunchPath(path);
    task.setArguments($(args));
    task.setStandardOutput($.NSFileHandle.fileHandleWithNullDevice);
    task.setStandardError($.NSFileHandle.fileHandleWithNullDevice);
    task.launch;
}
// minutes > 0: that long; -1: until 9:00 local tomorrow; 0: back on. Same format as
// `open-pr-watch.sh snooze`.
function snooze(minutes) {
    if (!snoozeFile) return;
    if (minutes === 0) {
        $.NSFileManager.defaultManager.removeItemAtPathError(snoozeFile, null);
    } else {
        var d = new Date();
        if (minutes > 0) d = new Date(d.getTime() + minutes * 60000);
        else { d.setDate(d.getDate() + 1); d.setHours(9, 0, 0, 0); }
        var iso = d.toISOString().replace(/\.\d+Z$/, 'Z');
        $(iso + '\n').writeToFileAtomicallyEncodingError(snoozeFile, true, $.NSUTF8StringEncoding, null);
    }
    refresh();
}
function leave() {
    var me = String($.NSProcessInfo.processInfo.processIdentifier);
    if (readText(pidFile).trim() === me) $.NSFileManager.defaultManager.removeItemAtPathError(pidFile, null);
    if (item) $.NSStatusBar.systemStatusBar.removeStatusItem(item);
    $.NSApplication.sharedApplication.terminate(null);
}
