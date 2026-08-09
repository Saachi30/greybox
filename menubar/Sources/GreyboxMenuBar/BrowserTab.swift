import AppKit
import Foundation

enum BrowserTab {

    /// Returns the URL of the frontmost tab in whichever supported browser
    /// is currently the frontmost application, or nil if none matched or
    /// the user hasn't granted Automation permission yet.
    ///
    /// This is intentionally synchronous and only ever called right when
    /// the user opens the popover - there is no polling, timer, or
    /// background observation of browser activity anywhere in this app.
    static func activeURL() -> URL? {
        guard let frontApp = NSWorkspace.shared.frontmostApplication,
              let bundleID = frontApp.bundleIdentifier else { return nil }

        let script: String
        switch bundleID {
        case "com.apple.Safari":
            script = #"tell application "Safari" to get URL of front document"#
        case "com.google.Chrome":
            script = #"tell application "Google Chrome" to get URL of active tab of front window"#
        case "com.brave.Browser":
            script = #"tell application "Brave Browser" to get URL of active tab of front window"#
        case "com.microsoft.edgemac":
            script = #"tell application "Microsoft Edge" to get URL of active tab of front window"#
        case "company.thebrowser.Browser": // Arc
            script = #"tell application "Arc" to get URL of active tab of front window"#
        default:
            return nil
        }

        var errorDict: NSDictionary?
        guard let appleScript = NSAppleScript(source: script) else { return nil }
        let result = appleScript.executeAndReturnError(&errorDict)

        if errorDict != nil {
            // Most commonly: Automation permission not yet granted for this
            // browser. macOS will have already shown the system prompt on
            // first attempt - nothing further to do here but fail quietly.
            return nil
        }
        guard let urlString = result.stringValue else { return nil }
        return URL(string: urlString)
    }

    /// Just the registrable domain, since that's what greybox scopes a
    /// session to (e.g. "example.com", not "example.com/some/deep/path").
    static func domain(from url: URL) -> String? {
        url.host
    }
}