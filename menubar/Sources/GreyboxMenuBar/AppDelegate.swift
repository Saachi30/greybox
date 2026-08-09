import AppKit
import SwiftUI

final class AppDelegate: NSObject, NSApplicationDelegate {
    private var statusItem: NSStatusItem!
    private var popover: NSPopover!
    private let viewModel = PopoverViewModel()

    func applicationDidFinishLaunching(_ notification: Notification) {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.squareLength)
        updateIcon(scanning: false)

        if let button = statusItem.button {
            button.action = #selector(togglePopover(_:))
            button.target = self
        }

        popover = NSPopover()
        popover.behavior = .transient
        popover.contentSize = NSSize(width: 380, height: 460)
        popover.contentViewController = NSHostingController(
            rootView: PopoverView(viewModel: viewModel)
        )

        viewModel.onScanningChanged = { [weak self] scanning in
            self?.updateIcon(scanning: scanning)
        }

        // Read the active tab as soon as the popover is about to be shown,
        // not continuously - the app does nothing until the user clicks.
        viewModel.refreshActiveTab()
    }

    @objc private func togglePopover(_ sender: AnyObject?) {
        guard let button = statusItem.button else { return }
        if popover.isShown {
            popover.performClose(sender)
        } else {
            viewModel.refreshActiveTab()
            popover.show(relativeTo: button.bounds, of: button, preferredEdge: .minY)
            NSApp.activate(ignoringOtherApps: true)
        }
    }

    /// The greybox mark: a square split solid/outline, rendered as a
    /// template image so macOS adapts it to light/dark automatically.
    /// A filled square means idle; a dashed/outline square means a scan
    /// is running - this is the whole status vocabulary, no extra text
    /// needed in the menu bar itself.
    private func updateIcon(scanning: Bool) {
        let symbolName = scanning ? "square.dashed" : "square.righthalf.filled"
        let image = NSImage(
            systemSymbolName: symbolName,
            accessibilityDescription: scanning ? "Greybox - scan running" : "Greybox"
        )
        image?.isTemplate = true
        statusItem.button?.image = image
    }
}