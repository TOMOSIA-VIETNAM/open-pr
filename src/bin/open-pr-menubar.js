// The open-pr menu bar item on macOS, started by `open-pr-watch.sh menubar`, one per machine.
// A status item needs no permission. Everything it shows is read, every few seconds, from files
// the watcher writes, in every data directory it was given:
//   <data>/<repo>/watch-review/heartbeat    the repo counts as watched while this is fresh
//   <data>/<repo>/watch-review/state.json   sessions; active = not finished, working or question
//   <data>/<repo>/watch-review/feed.jsonl   the recent notifications
//   ${XDG_CONFIG_HOME:-~/.config}/open-pr/watch/snooze_until   toasts off until then — the Snooze menu writes it too
// It leaves by itself, removing its pid file, once no repo has been watched for 5 minutes;
// "Quit menu" leaves at once. Watching goes on either way.
// argv: snooze file, pid file, heartbeat age (seconds) past which a repo is not watched, then
// every data directory (`open-pr.sh data-dir --all`).
// File contents are data only: shown as menu titles, opened when they are http(s) URLs, copied
// as text — never spliced into source.
ObjC.import('Cocoa');

var REFRESH = 3, IDLE_EXIT = 300, RECENT = 10, CLIP = 90;
var dataDirs = [], snoozeFile = '', pidFile = '', fresh = 2700;
var item = null, target = null, lastWatched = Date.now();

ObjC.registerSubclass({
    name: 'OPRMenuTarget',
    methods: {
        'tick:': { types: ['void', ['id']], implementation: function () { refresh(); } },
        'openURL:': { types: ['void', ['id']], implementation: function (s) { openURL(unwrapString(s.representedObject)); } },
        'copyText:': { types: ['void', ['id']], implementation: function (s) { copyText(unwrapString(s.representedObject)); } },
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
    item = $.NSStatusBar.systemStatusBar.statusItemWithLength(-1);   // -1 = variable length
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
function hhmm(d) { function p(n) { return (n < 10 ? '0' : '') + n; } return p(d.getHours()) + ':' + p(d.getMinutes()); }
function snoozedUntil() {
    var d = new Date(readText(snoozeFile).split('\n')[0].trim());
    return isNaN(d.getTime()) || d.getTime() <= Date.now() ? null : d;
}

// Every watched repo's active sessions and feed, newest notification first.
function scan() {
    var out = { repos: 0, sessions: [], feed: [] };
    dataDirs.forEach(function (data) { listDir(data).forEach(function (name) {
        if (typeof name !== 'string' || name.charAt(0) === '.') return;
        var dir = data + '/' + name + '/watch-review';
        if (ageSeconds(dir + '/heartbeat') > fresh) return;
        out.repos++;
        var st = parse(readText(dir + '/state.json'));
        var ss = st && typeof st.sessions === 'object' && st.sessions ? st.sessions : {};
        Object.keys(ss).sort(function (a, b) { return Number(a) - Number(b); }).forEach(function (pr) {
            var s = ss[pr];
            if (!s || typeof s !== 'object' || s.finished === true) return;
            if (s.last_state !== 'working' && s.last_state !== 'question') return;
            out.sessions.push({ label: (str(s.repo) || name) + '#' + pr, state: s.last_state,
                                url: str(s.url), open: str(s.open) });
        });
        readText(dir + '/feed.jsonl').split('\n').forEach(function (line) {
            var f = parse(line);
            if (f && typeof f === 'object' && str(f.summary)) out.feed.push(f);
        });
    }); });
    out.feed.sort(function (a, b) { return str(b.at) < str(a.at) ? -1 : str(b.at) > str(a.at) ? 1 : 0; });
    out.feed = out.feed.slice(0, RECENT);
    return out;
}

// ---------------------------------------------------------------- menu ----
function refresh() {
    var s = scan(), now = Date.now();
    if (s.repos) lastWatched = now;
    else if (now - lastWatched > IDLE_EXIT * 1000) { leave(); return; }
    item.button.setTitle('open-pr' + (s.sessions.length ? ' ·' + s.sessions.length : ''));
    item.setMenu(build(s));
}

function add(menu, title, action, value, tag) {
    var t = title.length > CLIP ? title.slice(0, CLIP - 1) + '…' : title;
    var mi = $.NSMenuItem.alloc.initWithTitleActionKeyEquivalent(t, action || null, '');
    if (action) {
        mi.setTarget(target);
        if (value !== undefined) mi.setRepresentedObject($(value));
        if (tag !== undefined) mi.setTag(tag);
    }
    menu.addItem(mi);
    return mi;
}

function build(s) {
    var m = $.NSMenu.alloc.initWithTitle('open-pr');
    add(m, 'Watching ' + s.repos + (s.repos === 1 ? ' repo' : ' repos'));
    var until = snoozedUntil();
    if (until) add(m, 'Toasts off until ' + hhmm(until));
    if (s.sessions.length) {
        m.addItem($.NSMenuItem.separatorItem);
        s.sessions.forEach(function (x) {
            add(m, x.label + ' — ' + x.state, isURL(x.url) ? 'openURL:' : null, x.url);
            if (x.open) add(m, 'Copy: ' + x.open, 'copyText:', x.open);
        });
    }
    if (s.feed.length) {
        m.addItem($.NSMenuItem.separatorItem);
        add(m, 'Recent');
        s.feed.forEach(function (f) {
            var d = new Date(str(f.at));
            var when = isNaN(d.getTime()) ? '' : hhmm(d) + '  ';
            add(m, when + str(f.summary), isURL(str(f.url)) ? 'openURL:' : null, str(f.url));
        });
    }
    m.addItem($.NSMenuItem.separatorItem);
    var sub = $.NSMenu.alloc.initWithTitle('Snooze');
    add(sub, '30 minutes', 'snooze:', undefined, 30);
    add(sub, '1 hour', 'snooze:', undefined, 60);
    add(sub, 'Until 9:00 tomorrow', 'snooze:', undefined, -1);
    add(sub, 'Resume toasts', 'snooze:', undefined, 0);
    add(m, 'Snooze').setSubmenu(sub);
    m.addItem($.NSMenuItem.separatorItem);
    add(m, 'Quit menu', 'quit:');
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
// minutes > 0: that long; -1: until 9:00 local tomorrow; 0: resume. Same file and line format
// as `open-pr-watch.sh snooze`, written atomically.
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
