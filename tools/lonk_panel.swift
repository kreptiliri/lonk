// lonk_panel: a small floating panel for Lonk, so you don't need a terminal while you play.
// Every button appends one or two command lines to the survey's commands file (TOTK_INPUT_FILE), the same lines you'd
// type, and the panel shows his newest log lines. It stays on top of the game (also in full screen) and doesn't take
// the keyboard from it: release the mouse from the game's camera first (the ` key), then click.
//
// Build: swiftc -O tools/lonk_panel.swift -o lonk_panel
// Run:   ./lonk_panel <commands file> [log file]   (log default: ~/Library/Logs/MacNativeGames/totk.log)
//        or with TOTK_INPUT_FILE set, just ./lonk_panel
import AppKit

let args = CommandLine.arguments
let inputPath = args.count > 1 ? args[1] : ProcessInfo.processInfo.environment["TOTK_INPUT_FILE"] ?? ""
if inputPath.isEmpty {
    FileHandle.standardError.write("usage: lonk_panel <commands file> [log file]\n".data(using: .utf8)!)
    exit(2)
}
let logPath = args.count > 2 ? args[2] : NSString(string: "~/Library/Logs/MacNativeGames/totk.log").expandingTildeInPath

func send(_ lines: [String]) {
    guard let data = (lines.joined(separator: "\n") + "\n").data(using: .utf8) else { return }
    if let file = FileHandle(forWritingAtPath: inputPath) {
        file.seekToEndOfFile(); file.write(data); try? file.close()
    } else {
        FileManager.default.createFile(atPath: inputPath, contents: data)
    }
}

let forever = "216000000"   // the longest a mood can be set for (1000 hours of frames)
let moods = ["stalk", "buddy", "block", "behind", "wander", "gift", "hide", "race", "fight", "party", "flee"]
let emotes = ["look", "lookup", "eat", "yuck", "jump", "sulk", "surprise"]
let outfits = ["hylian", "wild", "zora", "desert", "snowquill", "flamebreaker", "stealth", "climbing", "radiant",
               "soldier", "rubber", "barbarian", "royal", "glide", "froggy", "miner", "ember", "charged", "frostbite",
               "mystic", "zonaite", "awakening", "depths", "yiga"]

final class Panel: NSObject, NSApplicationDelegate {
    var panel: NSPanel!
    let status = NSTextField(wrappingLabelWithString: "")
    var actions: [ObjectIdentifier: () -> Void] = [:]
    var logOffset: UInt64 = 0
    var recent: [String] = []

    func button(_ title: String, _ action: @escaping () -> Void) -> NSButton {
        let b = NSButton(title: title, target: self, action: #selector(clicked(_:)))
        b.bezelStyle = .rounded
        b.controlSize = .small
        b.font = .systemFont(ofSize: NSFont.smallSystemFontSize)
        actions[ObjectIdentifier(b)] = action
        return b
    }
    @objc func clicked(_ sender: NSButton) { actions[ObjectIdentifier(sender)]?() }

    func row(_ label: String, _ views: [NSView]) -> NSView {
        let title = NSTextField(labelWithString: label)
        title.font = .boldSystemFont(ofSize: NSFont.smallSystemFontSize)
        title.textColor = .secondaryLabelColor
        let flow = NSStackView(views: views)
        flow.orientation = .horizontal
        flow.spacing = 4
        let stack = NSStackView(views: [title, flow])
        stack.orientation = .vertical
        stack.alignment = .leading
        stack.spacing = 3
        return stack
    }
    func rows(_ label: String, _ views: [NSView], per: Int) -> NSView {   // a long list of buttons, wrapped
        var lines: [NSView] = []
        var i = 0
        while i < views.count {
            let line = NSStackView(views: Array(views[i..<min(i + per, views.count)]))
            line.orientation = .horizontal
            line.spacing = 4
            lines.append(line)
            i += per
        }
        let title = NSTextField(labelWithString: label)
        title.font = .boldSystemFont(ofSize: NSFont.smallSystemFontSize)
        title.textColor = .secondaryLabelColor
        let stack = NSStackView(views: [title] + lines)
        stack.orientation = .vertical
        stack.alignment = .leading
        stack.spacing = 3
        return stack
    }

    func applicationDidFinishLaunching(_ note: Notification) {
        let outfit = NSPopUpButton(frame: .zero, pullsDown: false)
        outfit.controlSize = .small
        outfit.font = .systemFont(ofSize: NSFont.smallSystemFontSize)
        outfit.addItems(withTitles: ["outfit…", "random"] + outfits)
        outfit.target = self
        outfit.action = #selector(pickOutfit(_:))

        let spawn = row("Lonk", [
            button("Spawn (brain)") { send(["survey lonk twin", "survey lonk start"]) },
            button("Brain on") { send(["survey lonk brain \(forever)"]) },
            button("Stop") { send(["survey lonk stop"]) },
        ])
        let mood = rows("Mood (brain off, he stays in it)", moods.map { m in button(m) { send(["survey lonk \(m) \(forever)"]) } }, per: 6)
        let emote = rows("Emote", emotes.map { e in button(e) { send(["survey lonk emote \(e)"]) } } +
                         [button("hit him") { send(["survey lonk hit"]) }], per: 4)
        let look = row("Looks", [
            button("twin") { send(["survey lonk twin"]) },
            button("naked") { send(["survey lonk naked"]) },
            outfit,
        ])
        let dice = row("His dice", [
            button("no buddy") { send(["survey lonk nobuddy"]) },
            button("buddy ok") { send(["survey lonk buddyok"]) },
            button("no stalk") { send(["survey lonk nostalk"]) },
            button("stalk ok") { send(["survey lonk stalkok"]) },
        ])
        status.font = .monospacedSystemFont(ofSize: 10, weight: .regular)
        status.textColor = .secondaryLabelColor
        status.preferredMaxLayoutWidth = 300
        status.stringValue = "watching \(logPath)"

        let stack = NSStackView(views: [spawn, mood, emote, look, dice, status])
        stack.orientation = .vertical
        stack.alignment = .leading
        stack.spacing = 10
        stack.edgeInsets = NSEdgeInsets(top: 10, left: 12, bottom: 12, right: 12)

        panel = NSPanel(contentRect: NSRect(x: 0, y: 0, width: 320, height: 300),
                        styleMask: [.titled, .closable, .utilityWindow, .nonactivatingPanel], backing: .buffered, defer: false)
        panel.title = "Lonk"
        panel.level = .floating
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        panel.hidesOnDeactivate = false
        panel.becomesKeyOnlyIfNeeded = true
        panel.contentView = stack
        panel.setContentSize(stack.fittingSize)
        if let screen = NSScreen.main?.visibleFrame {
            panel.setFrameTopLeftPoint(NSPoint(x: screen.maxX - panel.frame.width - 16, y: screen.maxY - 16))
        }
        panel.orderFrontRegardless()

        // start at the log's end, then show his newest lines twice a second
        if let a = try? FileManager.default.attributesOfItem(atPath: logPath), let size = a[.size] as? UInt64 { logOffset = size }
        Timer.scheduledTimer(withTimeInterval: 0.5, repeats: true) { [weak self] _ in self?.readLog() }
    }

    @objc func pickOutfit(_ sender: NSPopUpButton) {
        guard sender.indexOfSelectedItem > 0, let name = sender.titleOfSelectedItem else { return }
        send(["survey lonk outfit \(name)"])
        sender.selectItem(at: 0)
    }

    func readLog() {
        guard let file = FileHandle(forReadingAtPath: logPath) else { return }
        defer { try? file.close() }
        let end = file.seekToEndOfFile()
        if end < logOffset { logOffset = 0 }   // the log started over (a new session)
        file.seek(toFileOffset: logOffset)
        let data = file.readDataToEndOfFile()
        logOffset = end
        guard let text = String(data: data, encoding: .utf8) else { return }
        for line in text.split(separator: "\n") where line.hasPrefix("[survey] lonk: ") || line.hasPrefix("[survey] twins: ") {
            let s = line.replacingOccurrences(of: "[survey] ", with: "")
            if s.hasPrefix("lonk: frame=") { continue }
            recent.append(s)
        }
        if recent.count > 4 { recent.removeFirst(recent.count - 4) }
        if !recent.isEmpty { status.stringValue = recent.joined(separator: "\n") }
    }
}

let app = NSApplication.shared
app.setActivationPolicy(.accessory)   // no Dock icon, no menu bar of its own
let delegate = Panel()
app.delegate = delegate
app.run()
