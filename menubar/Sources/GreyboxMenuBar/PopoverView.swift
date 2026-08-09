import AppKit
import SwiftUI

final class PopoverViewModel: ObservableObject {
    @Published var domain: String?
    @Published var backendReachable: Bool = false
    @Published var scanning: Bool = false
    @Published var scanElapsed: Int = 0
    @Published var findings: [Finding] = []
    @Published var errorMessage: String?
    @Published var lastSessionID: String?
    @Published var lastScanTime: Date?
    @Published var latestOutput: String = ""
    @Published var generatingReport: Bool = false

    var onScanningChanged: ((Bool) -> Void)?
    private var elapsedTimer: Timer?
    private var currentTask: Task<Void, Never>?

    private func startElapsedTimer() {
        scanElapsed = 0
        elapsedTimer?.invalidate()
        elapsedTimer = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { [weak self] _ in
            Task { @MainActor in self?.scanElapsed += 1 }
        }
    }

    private func stopElapsedTimer() {
        elapsedTimer?.invalidate()
        elapsedTimer = nil
    }

    /// Cancels the in-flight scan/quick-action. This stops the app from
    /// waiting on the backend response, but - same limitation as the
    /// CLI's own Ctrl+C - it does NOT necessarily kill the actual tool
    /// still running inside the Kali container, since that's a separate
    /// process on the backend side. This just stops watching for it.
    func stopScan() {
        currentTask?.cancel()
        scanning = false
        onScanningChanged?(false)
        stopElapsedTimer()
        errorMessage = "Stopped watching - the check may still be finishing on the backend."
    }

    // Called synchronously from AppDelegate (already on the main thread,
    // since it's driven by an AppKit UI event) - safe without actor
    // isolation annotations since nothing here crosses threads except the
    // Task below, which explicitly hops back via MainActor.run.
    func refreshActiveTab() {
        errorMessage = nil
        if let url = BrowserTab.activeURL() {
            domain = BrowserTab.domain(from: url)
        } else {
            domain = nil
        }
        Task {
            let reachable = await BackendClient.shared.isReachable()
            await MainActor.run { self.backendReachable = reachable }
        }
    }

    func scan() {
        guard let domain else { return }
        scanning = true
        onScanningChanged?(true)
        errorMessage = nil
        findings = []
        latestOutput = ""  // clear stale output from a previous action - otherwise the old
        // tool's output stays visible for the whole "Scanning..." phase of this new one,
        // which looked like the wrong tool's results were showing
        startElapsedTimer()

        currentTask = Task {
            do {
                let result = try await BackendClient.shared.quickScan(domain: domain)
                await MainActor.run {
                    self.findings = result.findings
                    self.lastSessionID = result.session_id
                    self.lastScanTime = Date()
                    self.latestOutput = result.findings
                        .map { "=== \($0.tool) ===\n\($0.summary ?? "(no output)")" }
                        .joined(separator: "\n\n")
                }
            } catch is CancellationError {
                // stopScan() already set its own message - don't overwrite it
            } catch {
                if !Task.isCancelled {
                    await MainActor.run { self.errorMessage = error.localizedDescription }
                }
            }
            await MainActor.run {
                self.scanning = false
                self.onScanningChanged?(false)
                self.stopElapsedTimer()
            }
        }
    }

    func runQuickAction(tool: String) {
        guard let domain else { return }
        scanning = true
        onScanningChanged?(true)
        errorMessage = nil
        latestOutput = ""  // same reasoning as scan() above
        startElapsedTimer()

        currentTask = Task {
            do {
                let result = try await BackendClient.shared.quickAction(domain: domain, tool: tool)
                await MainActor.run {
                    self.findings.append(result.finding)
                    self.lastSessionID = result.session_id
                    self.lastScanTime = Date()
                    self.latestOutput = "=== \(result.finding.tool) ===\n\(result.finding.summary ?? "(no output)")"
                }
            } catch is CancellationError {
                // stopScan() already set its own message - don't overwrite it
            } catch {
                if !Task.isCancelled {
                    await MainActor.run { self.errorMessage = error.localizedDescription }
                }
            }
            await MainActor.run {
                self.scanning = false
                self.onScanningChanged?(false)
                self.stopElapsedTimer()
            }
        }
    }

    /// Downloads the report's actual bytes and opens the freshly-saved
    /// local file - guaranteed to exist since we just wrote it ourselves,
    /// unlike the old approach of opening a container-side path that
    /// depended on the Docker volume mount lining up correctly.
    func openFullReport() {
        guard let sessionID = lastSessionID else { return }
        generatingReport = true
        Task {
            do {
                let localURL = try await BackendClient.shared.downloadReport(sessionID: sessionID)
                print("[greybox] report downloaded to: \(localURL.path)")
                await MainActor.run {
                    let opened = NSWorkspace.shared.open(localURL)
                    if !opened {
                        self.errorMessage = "Downloaded but couldn't open: \(localURL.path)"
                    }
                }
            } catch {
                await MainActor.run { self.errorMessage = error.localizedDescription }
            }
            await MainActor.run { self.generatingReport = false }
        }
    }

    /// Highest severity across current findings, for the compact summary line.
    var topSeverity: String? {
        let order = ["critical", "high", "medium", "low", "info"]
        for level in order where findings.contains(where: { $0.severity == level }) {
            return level
        }
        return nil
    }
}

struct PopoverView: View {
    @ObservedObject var viewModel: PopoverViewModel

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            header

            if !viewModel.backendReachable {
                Label("Backend isn't running", systemImage: "exclamationmark.triangle")
                    .font(.system(.caption, design: .monospaced))
                    .foregroundColor(.orange)
            } else if let domain = viewModel.domain {
                scanSection(domain: domain)
            } else {
                Text("Open a site in your browser, then click the icon again.")
                    .font(.system(.caption, design: .monospaced))
                    .foregroundColor(.secondary)
            }

            if let error = viewModel.errorMessage {
                Text(error)
                    .font(.system(.caption2, design: .monospaced))
                    .foregroundColor(.red)
            }
        }
        .padding(.top, 20)
        .padding(.horizontal, 16)
        .padding(.bottom, 10)
        .frame(width: 380, height: 460, alignment: .top)
        .background(Color(nsColor: .windowBackgroundColor))
    }

    private var header: some View {
        HStack {
            Image(systemName: "square.righthalf.filled")
            Text("greybox")
                .font(.system(.headline, design: .monospaced))
            Spacer()
        }
    }

    @ViewBuilder
    private func scanSection(domain: String) -> some View {
        Text(domain)
            .font(.system(.body, design: .monospaced))
            .foregroundColor(.secondary)

        quickActionsRow

        if viewModel.scanning {
            HStack(spacing: 8) {
                ProgressView().controlSize(.small)
                Text("Scanning... (\(viewModel.scanElapsed)s)")
                    .font(.system(.caption, design: .monospaced))
                Spacer()
                Button("Stop") { viewModel.stopScan() }
                    .controlSize(.small)
            }
            if viewModel.scanElapsed > 15 {
                Text("Subdomain/nikto checks can take a while - this is normal")
                    .font(.system(.caption2, design: .monospaced))
                    .foregroundColor(.secondary)
            }
        } else if !viewModel.findings.isEmpty {
            resultSummary
        } else {
            Button("Full scan") { viewModel.scan() }
                .keyboardShortcut(.defaultAction)
        }
    }

    /// Individual quick actions - for when someone wants just one specific
    /// check (open ports, subdomains, tech stack, certs) rather than the
    /// fixed whatweb+nmap bundle "Full scan" runs. Each appends its result
    /// to the same running findings list instead of starting a new session.
    private var quickActionsRow: some View {
        let actions: [(label: String, tool: String, systemImage: String)] = [
            ("Ports", "nmap", "network"),
            ("Subdomains", "subdomain_enum", "point.3.connected.trianglepath.dotted"),
            ("Tech", "whatweb", "curlybraces"),
            ("Certs", "crtsh", "checkmark.seal"),
        ]
        return HStack(spacing: 6) {
            ForEach(actions, id: \.tool) { action in
                Button {
                    viewModel.runQuickAction(tool: action.tool)
                } label: {
                    VStack(spacing: 2) {
                        Image(systemName: action.systemImage)
                        Text(action.label).font(.system(.caption2, design: .monospaced))
                    }
                    .frame(maxWidth: .infinity)
                }
                .disabled(viewModel.scanning)
            }
        }
    }

    private var resultSummary: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("\(viewModel.findings.count) check(s) run")
                .font(.system(.caption, design: .monospaced))
            if let sev = viewModel.topSeverity {
                Text("Top severity: \(sev)")
                    .font(.system(.caption, design: .monospaced))
                    .foregroundColor(severityColor(sev))
            }
            if let scanTime = viewModel.lastScanTime {
                Text("Last scanned \(scanTime.formatted(date: .omitted, time: .standard))")
                    .font(.system(.caption2, design: .monospaced))
                    .foregroundColor(.secondary)
            }
            HStack {
                Button("Full scan") { viewModel.scan() }
                if viewModel.generatingReport {
                    HStack(spacing: 6) {
                        ProgressView().controlSize(.small)
                        Text("Generating report...")
                            .font(.system(.caption2, design: .monospaced))
                            .foregroundColor(.secondary)
                    }
                } else {
                    Button("Open full report") { viewModel.openFullReport() }
                }
            }
            if !viewModel.latestOutput.isEmpty {
                outputLog
            }
        }
    }

    /// The raw tool output, auto-scrolled to the bottom by default so the
    /// most recent/important lines (e.g. "Scan completed successfully!")
    /// are visible immediately instead of requiring a manual scroll.
    private var outputLog: some View {
        ScrollViewReader { proxy in
            ScrollView {
                Text(viewModel.latestOutput)
                    .font(.system(.caption2, design: .monospaced))
                    .foregroundColor(.secondary)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .textSelection(.enabled)
                    .id("logBottom")
            }
            .frame(minHeight: 160, maxHeight: .infinity)
            .background(Color.black.opacity(0.15))
            .cornerRadius(4)
            .onChange(of: viewModel.latestOutput) { _ in
                proxy.scrollTo("logBottom", anchor: .bottom)
            }
            .onAppear {
                proxy.scrollTo("logBottom", anchor: .bottom)
            }
        }
    }

    private func severityColor(_ severity: String) -> Color {
        switch severity {
        case "critical": return .red
        case "high": return .orange
        case "medium": return .yellow
        case "low": return .green
        default: return .secondary
        }
    }
}