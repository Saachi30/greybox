import AppKit

// LSUIElement is also set in Info.plist when packaged as a .app bundle,
// but setting activation policy here too means it behaves correctly even
// when run directly via `swift run` during development.
let app = NSApplication.shared
app.setActivationPolicy(.accessory)

let delegate = AppDelegate()
app.delegate = delegate
app.run()