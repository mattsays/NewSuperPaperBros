import AppKit
import CryptoKit

#if PAL_BUILD
private let dolHash = "c853aafb4beb7504d5ab8c81445c3dc7cc244a4486c70d9eaed71639c41049cf"
private let relHash = "9aa3d707395fc3b89354bf889ca332565f067e30243c66f5af48532689aca2eb"
private let supportFolder = "NewSuperPaperBrosPAL"
private let gameBundleIdentifier = "org.newsuperpaperbros.macos.pal.game"
private let revisionLabel = "Europe revision 1"
private let saveTitle = "52385050"
private let isPAL = true
#else
private let dolHash = "316fe3a88654cf55f164a493fdc7d872fb7362298613e335a2240b4921bfe7a0"
private let relHash = "24920508fb790854d3191c0caa6f6434efcf948b0656f15bb8236cd81cb060f6"
private let supportFolder = "NewSuperPaperBros"
private let gameBundleIdentifier = "org.newsuperpaperbros.macos.game"
private let revisionLabel = "USA revision 2"
private let saveTitle = "52385045"
private let isPAL = false
#endif
private let files = FileManager.default

enum SetupError: LocalizedError {
    case message(String)
    var errorDescription: String? { if case .message(let text) = self { return text }; return nil }
}

func sha256(_ url: URL) throws -> String {
    SHA256.hash(data: try Data(contentsOf: url)).map { String(format: "%02x", $0) }.joined()
}

func verifiedDisc(_ root: URL) throws {
    guard try sha256(root.appendingPathComponent("sys/main.dol")) == dolHash,
          try sha256(root.appendingPathComponent("files/rel/relF.bin")) == relHash else {
        throw SetupError.message("This build needs Super Paper Mario \(revisionLabel). The selected game files do not match that version.")
    }
    guard files.fileExists(atPath: root.appendingPathComponent("sys/fst.bin").path) else {
        throw SetupError.message("The extracted game is incomplete. Please choose the disc image again.")
    }
}


func applicationDataRoot() -> URL {
    files.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
        .appendingPathComponent(supportFolder, isDirectory: true)
}

@discardableResult func installTextures(_ source: URL) throws -> Int {
    let manager = FileManager.default
    let support = applicationDataRoot().appendingPathComponent("texture_replacements", isDirectory: true)
    try manager.createDirectory(at: support, withIntermediateDirectories: true)
    let staging = support.appendingPathComponent(".hd-staging-" + UUID().uuidString, isDirectory: true)
    try manager.createDirectory(at: staging, withIntermediateDirectories: true)
    defer { try? manager.removeItem(at: staging) }
    guard let entries = manager.enumerator(at: source, includingPropertiesForKeys: [.isRegularFileKey, .isSymbolicLinkKey]) else {
        throw SetupError.message("Choose an extracted HD texture pack folder.")
    }
    var count = 0
    for case let file as URL in entries {
        let properties = try file.resourceValues(forKeys: [.isRegularFileKey, .isSymbolicLinkKey])
        guard properties.isRegularFile == true, properties.isSymbolicLink != true,
              file.lastPathComponent.hasPrefix("tex1_"), ["dds", "png"].contains(file.pathExtension.lowercased()) else { continue }
        let destination = staging.appendingPathComponent(file.lastPathComponent)
        if !manager.fileExists(atPath: destination.path) { try manager.copyItem(at: file, to: destination); count += 1 }
    }
    guard count > 0 else { throw SetupError.message("This folder contains no supported HD textures.") }
    let destination = support.appendingPathComponent("SPM_HD_Razius_4x", isDirectory: true)
    let previous = support.appendingPathComponent(".hd-previous-" + UUID().uuidString)
    if manager.fileExists(atPath: destination.path) { try manager.moveItem(at: destination, to: previous) }
    do { try manager.moveItem(at: staging, to: destination) }
    catch {
        if manager.fileExists(atPath: previous.path) { try? manager.moveItem(at: previous, to: destination) }
        throw error
    }
    if manager.fileExists(atPath: previous.path) { try? manager.removeItem(at: previous) }
    let config = applicationDataRoot().appendingPathComponent("Config.toml")
    let text = (try? String(contentsOf: config, encoding: .utf8)) ?? ""
    try replacingSetting(text, section: "video", key: "texture_replacements", value: "true")
        .write(to: config, atomically: true, encoding: .utf8)
    return count
}

// Preserve unrelated settings, including bindings and paths, when updating one value.
func settingValue(_ text: String, section: String, key: String) -> String? {
    var current = ""
    for line in text.components(separatedBy: .newlines) {
        let clean = line.trimmingCharacters(in: .whitespaces)
        if clean.hasPrefix("[") { current = clean.components(separatedBy: "#")[0].trimmingCharacters(in: .whitespaces) }
        guard current == "[\(section)]", let equals = clean.firstIndex(of: "="),
              clean[..<equals].trimmingCharacters(in: .whitespaces) == key else { continue }
        return String(clean[clean.index(after: equals)...]).components(separatedBy: "#")[0]
            .trimmingCharacters(in: .whitespaces)
    }
    return nil
}

func replacingSetting(_ text: String, section: String, key: String, value: String) -> String {
    var lines = text.components(separatedBy: "\n")
    var current = ""; var sectionIndex: Int?
    for index in lines.indices {
        let clean = lines[index].trimmingCharacters(in: .whitespaces)
        if clean.hasPrefix("[") {
            current = clean.components(separatedBy: "#")[0].trimmingCharacters(in: .whitespaces)
            if current == "[\(section)]" { sectionIndex = index }
        }
        if current == "[\(section)]", let equals = clean.firstIndex(of: "="),
           clean[..<equals].trimmingCharacters(in: .whitespaces) == key {
            lines[index] = "\(key) = \(value)"
            return lines.joined(separator: "\n")
        }
    }
    if let sectionIndex { lines.insert("\(key) = \(value)", at: sectionIndex + 1) }
    else { lines.append(contentsOf: ["", "[\(section)]", "\(key) = \(value)"]) }
    return lines.joined(separator: "\n")
}

@discardableResult func prepareInstallation(_ url: URL, support: URL, tool: URL) throws -> URL {
    let destination = support.appendingPathComponent("Disc", isDirectory: true)
    var temporary: URL?
    defer { if let temporary { try? files.removeItem(at: temporary) } }
    var isDirectory: ObjCBool = false
    _ = files.fileExists(atPath: url.path, isDirectory: &isDirectory)
    let root: URL
    if isDirectory.boolValue {
        root = files.fileExists(atPath: url.appendingPathComponent("sys/main.dol").path)
            ? url : url.appendingPathComponent("DATA", isDirectory: true)
    } else {
        try files.createDirectory(at: support, withIntermediateDirectories: true)
        let staging = support.appendingPathComponent("Disc-staging-" + UUID().uuidString, isDirectory: true)
        temporary = staging
        let process = Process(); process.executableURL = tool
        process.arguments = ["extract", "-q", url.path, staging.path]
        let log = support.appendingPathComponent("setup.log")
        files.createFile(atPath: log.path, contents: nil)
        let handle = try FileHandle(forWritingTo: log)
        defer { try? handle.close() }
        process.standardOutput = handle; process.standardError = handle
        try process.run(); process.waitUntilExit()
        guard process.terminationStatus == 0 else {
            throw SetupError.message("The disc image could not be extracted. Please check that the dump is complete. Details are in setup.log.")
        }
        try verifiedDisc(staging)
        // Only replace the app's own validated disc extraction. Saves are elsewhere.
        let previous = support.appendingPathComponent("Disc-previous-" + UUID().uuidString)
        if files.fileExists(atPath: destination.path) { try files.moveItem(at: destination, to: previous) }
        do { try files.moveItem(at: staging, to: destination) }
        catch {
            if files.fileExists(atPath: previous.path) { try? files.moveItem(at: previous, to: destination) }
            throw error
        }
        temporary = nil
        if files.fileExists(atPath: previous.path) { try? files.removeItem(at: previous) }
        root = destination
    }
    try verifiedDisc(root)
    try files.createDirectory(at: support, withIntermediateDirectories: true)
    let record = try JSONSerialization.data(withJSONObject: ["discRoot": root.path], options: [.prettyPrinted])
    try record.write(to: support.appendingPathComponent("installation.json"), options: .atomic)
    return root
}

final class Launcher: NSObject, NSApplicationDelegate {
    let dataRoot = applicationDataRoot()
    var window: NSWindow!
    let status = NSTextField(wrappingLabelWithString: "Choose your disc image to set up the game.")
    let play = NSButton(title: "Play", target: nil, action: nil)
    let choose = NSButton(title: "Choose Game…", target: nil, action: nil)
    let progress = NSProgressIndicator()
    let resolution = NSPopUpButton(frame: .zero, pullsDown: false)
    let aspect = NSPopUpButton(frame: .zero, pullsDown: false)
    let language = NSPopUpButton(frame: .zero, pullsDown: false)
    let hdTextures = NSButton(checkboxWithTitle: "HD textures", target: nil, action: nil)
    private let resolutions: [(String, Double)] = [
        ("Match screen (Retina)", 0), ("480p", 1), ("720p", 1.5),
        ("1080p — Full HD", 2.25), ("1440p — QHD", 3), ("2160p — 4K", 4.5)
    ]
    var discRoot: URL?
    var game: Process?
    private var started = false

    func applicationDidFinishLaunching(_ notification: Notification) {
        start()
    }

    func start() {
        guard !started else { return }
        started = true
        NSApp.setActivationPolicy(.regular)
        if let icon = Bundle.main.url(forResource: "AppIcon", withExtension: "icns") {
            NSApp.applicationIconImage = NSImage(contentsOf: icon)
        }
        let menu = NSMenu()
        let appItem = NSMenuItem(); menu.addItem(appItem)
        let appMenu = NSMenu(); appItem.submenu = appMenu
        appMenu.addItem(withTitle: "Quit New Super Paper Bros.", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        NSApp.mainMenu = menu
        makeWindow()
        loadInstallation()
        loadResolution()
        loadAspect()
        loadLanguageAndTextures()
        NSApp.activate(ignoringOtherApps: true)
    }

    func makeWindow() {
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 600, height: isPAL ? 610 : 560),
                          styleMask: [.titled, .closable, .miniaturizable], backing: .buffered, defer: false)
        window.title = isPAL ? "New Super Paper Bros. PAL" : "New Super Paper Bros."
        window.center()
        window.isReleasedWhenClosed = false
        let stack = NSStackView(); stack.orientation = .vertical; stack.alignment = .leading; stack.spacing = 18
        stack.translatesAutoresizingMaskIntoConstraints = false
        window.contentView!.addSubview(stack)
        NSLayoutConstraint.activate([
            stack.leadingAnchor.constraint(equalTo: window.contentView!.leadingAnchor, constant: 36),
            stack.trailingAnchor.constraint(equalTo: window.contentView!.trailingAnchor, constant: -36),
            stack.topAnchor.constraint(equalTo: window.contentView!.topAnchor, constant: 32)
        ])
        let title = NSTextField(labelWithString: "New Super Paper Bros.")
        title.font = .systemFont(ofSize: 28, weight: .bold)
        let icon = NSImageView()
        if let url = Bundle.main.url(forResource: "AppIcon", withExtension: "icns") { icon.image = NSImage(contentsOf: url) }
        icon.imageScaling = .scaleProportionallyUpOrDown
        icon.translatesAutoresizingMaskIntoConstraints = false
        NSLayoutConstraint.activate([icon.widthAnchor.constraint(equalToConstant: 48), icon.heightAnchor.constraint(equalToConstant: 48)])
        let heading = NSStackView(views: [icon, title]); heading.spacing = 14; heading.alignment = .centerY
        stack.addArrangedSubview(heading)
        let subtitle = NSTextField(labelWithString: "Native macOS preview · Apple Silicon · \(revisionLabel)")
        subtitle.textColor = .secondaryLabelColor; subtitle.font = .systemFont(ofSize: 12)
        stack.addArrangedSubview(subtitle)
        let description = NSTextField(wrappingLabelWithString: "Play using your own Super Paper Mario disc dump. Your saves, settings and mods stay in your Mac’s Application Support folder.")
        description.font = .systemFont(ofSize: 14); stack.addArrangedSubview(description)
        status.font = .systemFont(ofSize: 13); status.textColor = .secondaryLabelColor
        status.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)
        stack.addArrangedSubview(status)
        progress.style = .bar; progress.isIndeterminate = true; progress.isHidden = true
        progress.translatesAutoresizingMaskIntoConstraints = false
        stack.addArrangedSubview(progress)
        progress.widthAnchor.constraint(equalTo: stack.widthAnchor).isActive = true
        resolution.target = self; resolution.action = #selector(resolutionChanged)
        resolution.setAccessibilityLabel("Render resolution")
        for (label, scale) in resolutions {
            resolution.addItem(withTitle: label)
            resolution.lastItem?.representedObject = NSNumber(value: scale)
        }
        let resolutionRow = NSStackView(views: [NSTextField(labelWithString: "Resolution:"), resolution])
        resolutionRow.spacing = 12; resolutionRow.alignment = .centerY
        stack.addArrangedSubview(resolutionRow)
        let resolutionNote = NSTextField(labelWithString: "Applies when you start the game. Higher resolutions use more GPU power.")
        resolutionNote.font = .systemFont(ofSize: 11); resolutionNote.textColor = .secondaryLabelColor
        stack.addArrangedSubview(resolutionNote)
        for (label, mode) in [("16:10 — Mac", 4), ("16:9", 1), ("Original 4:3", 0), ("Fill window", 2), ("Cinematic 2.39:1", 3)] {
            aspect.addItem(withTitle: label); aspect.lastItem?.representedObject = NSNumber(value: mode)
        }
        aspect.target = self; aspect.action = #selector(resolutionChanged)
        aspect.setAccessibilityLabel("Aspect ratio")
        let aspectRow = NSStackView(views: [NSTextField(labelWithString: "Aspect ratio:"), aspect])
        aspectRow.spacing = 12; aspectRow.alignment = .centerY; stack.addArrangedSubview(aspectRow)
        if isPAL {
            for (label, code) in [("Italiano", "it"), ("English", "en"), ("Français", "fr"), ("Deutsch", "de"), ("Español", "es")] {
                language.addItem(withTitle: label); language.lastItem?.representedObject = code
            }
            language.target = self; language.action = #selector(resolutionChanged)
            language.setAccessibilityLabel("Game language")
            let row = NSStackView(views: [NSTextField(labelWithString: "Language:"), language])
            row.spacing = 12; row.alignment = .centerY; stack.addArrangedSubview(row)
        }
        hdTextures.target = self; hdTextures.action = #selector(resolutionChanged)
        stack.addArrangedSubview(hdTextures)
        choose.target = self; choose.action = #selector(selectGame)
        play.target = self; play.action = #selector(launchGame)
        play.bezelStyle = .rounded; play.controlSize = .large; play.keyEquivalent = "\r"
        play.isEnabled = false
        let buttons = NSStackView(views: [choose, play]); buttons.spacing = 12
        stack.addArrangedSubview(buttons)
        let footer = NSStackView(views: [
            NSButton(title: "Open Saves", target: self, action: #selector(openSaves)),
            NSButton(title: "Open Mods", target: self, action: #selector(openMods)),
            NSButton(title: "Open Logs", target: self, action: #selector(openLogs))
        ]); footer.spacing = 8; stack.addArrangedSubview(footer)
        let hint = NSTextField(labelWithString: "F10: settings and controls     F11: full screen")
        hint.font = .systemFont(ofSize: 12); hint.textColor = .secondaryLabelColor
        stack.addArrangedSubview(hint)
        window.makeKeyAndOrderFront(nil)
    }

    func loadInstallation() {
        let record = dataRoot.appendingPathComponent("installation.json")
        if let data = try? Data(contentsOf: record),
           let object = try? JSONSerialization.jsonObject(with: data) as? [String: String],
           let path = object["discRoot"] {
            let url = URL(fileURLWithPath: path, isDirectory: true)
            if (try? verifiedDisc(url)) != nil {
                discRoot = url; play.isEnabled = true; status.stringValue = "Your game is ready."
            }
        }
    }

    func loadResolution() {
        let text = (try? String(contentsOf: dataRoot.appendingPathComponent("Config.toml"), encoding: .utf8)) ?? ""
        let scale = settingValue(text, section: "video", key: "resolution_multiplier").flatMap(Double.init) ?? 2.25
        if let index = resolution.itemArray.firstIndex(where: { ($0.representedObject as? NSNumber)?.doubleValue == scale }) {
            resolution.selectItem(at: index)
        } else {
            // Keep advanced resolutions chosen in the game's F10 menu.
            resolution.addItem(withTitle: "\(Int(scale * 480))p (advanced)")
            resolution.lastItem?.representedObject = NSNumber(value: scale)
            resolution.select(resolution.lastItem)
        }
    }

    func loadLanguageAndTextures() {
        let text = (try? String(contentsOf: dataRoot.appendingPathComponent("Config.toml"), encoding: .utf8)) ?? ""
        let code = settingValue(text, section: "game", key: "language")?.trimmingCharacters(in: CharacterSet(charactersIn: "\"")) ?? "it"
        if let item = language.itemArray.first(where: { ($0.representedObject as? String) == code }) { language.select(item) }
        let installed = files.fileExists(atPath: dataRoot.appendingPathComponent("texture_replacements/SPM_HD_Razius_4x").path)
        hdTextures.isEnabled = installed
        hdTextures.title = installed ? "HD textures" : "HD textures (pack not installed)"
        hdTextures.state = installed && settingValue(text, section: "video", key: "texture_replacements") != "false" ? .on : .off
    }

    func loadAspect() {
        let text = (try? String(contentsOf: dataRoot.appendingPathComponent("Config.toml"), encoding: .utf8)) ?? ""
        let mode = settingValue(text, section: "video", key: "aspect_mode").flatMap(Int.init) ?? 4
        if let item = aspect.itemArray.first(where: { ($0.representedObject as? NSNumber)?.intValue == mode }) { aspect.select(item) }
    }

    @objc func resolutionChanged() {
        do {
            try writeConfiguration()
        } catch { status.stringValue = "Could not save resolution: \(error.localizedDescription)"; loadResolution() }
    }

    @objc func selectGame() {
        let panel = NSOpenPanel()
        panel.title = "Choose your Super Paper Mario disc image or extracted folder"
        panel.canChooseFiles = true; panel.canChooseDirectories = true; panel.allowsMultipleSelection = false
        guard panel.runModal() == .OK, let url = panel.url else { return }
        choose.isEnabled = false; play.isEnabled = false
        progress.isHidden = false; progress.startAnimation(nil)
        status.stringValue = "Preparing your game… This can take a few minutes."
        let tool = Bundle.main.bundleURL.appendingPathComponent("Contents/Helpers/nodtool")
        let support = dataRoot
        DispatchQueue.global(qos: .userInitiated).async {
            let result = Result { try prepareInstallation(url, support: support, tool: tool) }
            DispatchQueue.main.async {
                self.progress.stopAnimation(nil); self.progress.isHidden = true; self.choose.isEnabled = true
                switch result {
                case .success(let root):
                    self.discRoot = root; self.play.isEnabled = true; self.status.stringValue = "Your game is ready."
                case .failure(let error):
                    self.play.isEnabled = self.discRoot != nil; self.status.stringValue = error.localizedDescription
                }
            }
        }
    }

    func writeConfiguration(disc: URL? = nil) throws {
        try files.createDirectory(at: dataRoot, withIntermediateDirectories: true)
        let config = dataRoot.appendingPathComponent("Config.toml")
        var text = (try? String(contentsOf: config, encoding: .utf8)) ?? """
        [video]
        graphics_api = "metal"
        display_mode = "windowed"
        resolution_multiplier = 2.25
        aspect_mode = 4
        frame_interpolation_fps = 0
        [network]
        enabled = false
        [discord]
        enabled = false
        """
        if let scale = resolution.selectedItem?.representedObject as? NSNumber {
            text = replacingSetting(text, section: "video", key: "resolution_multiplier", value: scale.stringValue)
        }
        if let mode = aspect.selectedItem?.representedObject as? NSNumber {
            text = replacingSetting(text, section: "video", key: "aspect_mode", value: mode.stringValue)
            if mode.intValue == 4 && settingValue(text, section: "video", key: "window_width") == nil {
                text = replacingSetting(text, section: "video", key: "window_width", value: "960")
                text = replacingSetting(text, section: "video", key: "window_height", value: "600")
            }
        }
        if window != nil && hdTextures.isEnabled {
            text = replacingSetting(text, section: "video", key: "texture_replacements", value: hdTextures.state == .on ? "true" : "false")
        }
        if isPAL {
            let code = language.selectedItem?.representedObject as? String
                ?? settingValue(text, section: "game", key: "language")?.trimmingCharacters(in: CharacterSet(charactersIn: "\"")) ?? "it"
            text = replacingSetting(text, section: "game", key: "language", value: "\"\(code)\"")
        }
        if let disc {
            let quote = disc.path.replacingOccurrences(of: "\\", with: "\\\\")
                .replacingOccurrences(of: "\"", with: "\\\"")
                .replacingOccurrences(of: "\n", with: "\\n").replacingOccurrences(of: "\r", with: "\\r")
            text = replacingSetting(text, section: "paths", key: "dvd_root", value: "\"\(quote)\"")
        }
        text = text.trimmingCharacters(in: .newlines) + "\n"
        try text.write(to: config, atomically: true, encoding: .utf8)
    }

    @objc func launchGame() {
        guard let root = discRoot, game == nil else { return }
        do {
            try verifiedDisc(root); try writeConfiguration(disc: root)
            let logs = dataRoot.appendingPathComponent("Logs", isDirectory: true)
            try files.createDirectory(at: logs, withIntermediateDirectories: true)
            let log = logs.appendingPathComponent("last-launch.log")
            files.createFile(atPath: log.path, contents: nil)
            let handle = try FileHandle(forWritingTo: log)
            let process = Process()
            let gameBundle = Bundle.main.bundleURL.appendingPathComponent("Contents/Helpers/Game.app")
            // Launch Services registers the game's own bundle identity and Dock icon.
            // Waiting keeps the launcher's lifecycle tied to the running game.
            process.executableURL = URL(fileURLWithPath: "/usr/bin/open")
            var arguments = ["-W", "--stdout", log.path, "--stderr", log.path]
            if isPAL { arguments += ["--env", "SPM_LANGUAGE=" + (language.selectedItem?.representedObject as? String ?? "it")] }
            process.arguments = arguments + [gameBundle.path]
            process.standardOutput = handle; process.standardError = handle
            process.terminationHandler = { finished in
                try? handle.close()
                DispatchQueue.main.async {
                    self.game = nil; self.play.isEnabled = true; self.resolution.isEnabled = true
                    self.loadResolution(); self.loadAspect(); self.loadLanguageAndTextures(); self.window.makeKeyAndOrderFront(nil)
                    self.status.stringValue = finished.terminationStatus == 0 ? "Your game is ready." : "The game closed unexpectedly. Open Logs for details."
                    NSApp.activate(ignoringOtherApps: true)
                }
            }
            try process.run(); game = process; play.isEnabled = false; resolution.isEnabled = false; window.orderOut(nil)
        } catch { status.stringValue = error.localizedDescription }
    }

    func openFolder(_ relative: String) {
        let url = dataRoot.appendingPathComponent(relative, isDirectory: true)
        try? files.createDirectory(at: url, withIntermediateDirectories: true)
        NSWorkspace.shared.open(url)
    }
    @objc func openSaves() { openFolder("NAND/title/00010000/\(saveTitle)/data") }
    @objc func openMods() { openFolder("mods") }
    @objc func openLogs() { openFolder("Logs") }
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { game == nil }
    func applicationWillTerminate(_ notification: Notification) {
        if game != nil {
            for application in NSRunningApplication.runningApplications(withBundleIdentifier: gameBundleIdentifier) {
                application.terminate()
            }
            game?.terminate()
        }
    }
}

func launcherMain() {
    if let index = CommandLine.arguments.firstIndex(of: "--install-textures"), index + 1 < CommandLine.arguments.count {
        do {
            let count = try installTextures(URL(fileURLWithPath: CommandLine.arguments[index + 1]))
            print("Installed \(count) HD textures in \(applicationDataRoot().path)")
            return
        } catch { fputs("\(error.localizedDescription)\n", stderr); exit(1) }
    }
    if let index = CommandLine.arguments.firstIndex(of: "--install-game"), index + 1 < CommandLine.arguments.count {
        do {
            let root = try prepareInstallation(URL(fileURLWithPath: CommandLine.arguments[index + 1]),
                support: applicationDataRoot(),
                tool: Bundle.main.bundleURL.appendingPathComponent("Contents/Helpers/nodtool"))
            _ = NSApplication.shared
            try Launcher().writeConfiguration(disc: root)
            print("Game prepared: \(root.path)")
            return
        } catch { fputs("\(error.localizedDescription)\n", stderr); exit(1) }
    }
    let application = NSApplication.shared
    application.setActivationPolicy(.regular)
    let delegate = Launcher()
    application.delegate = delegate
    // Set up once for both Finder launches and direct developer invocations.
    delegate.start()
    withExtendedLifetime(delegate) { application.run() }
}

launcherMain()
