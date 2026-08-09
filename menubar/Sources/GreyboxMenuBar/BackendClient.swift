import Foundation

struct Finding: Decodable, Identifiable {
    let id: String
    let tool: String
    let severity: String
    let summary: String?
}

struct QuickScanResponse: Decodable {
    let session_id: String
    let domain: String
    let findings: [Finding]
}

struct QuickActionResponse: Decodable {
    let session_id: String
    let domain: String
    let finding: Finding
}

enum BackendError: Error, LocalizedError {
    case unreachable
    case badResponse

    var errorDescription: String? {
        switch self {
        case .unreachable: return "Backend isn't running on localhost:8000"
        case .badResponse: return "Unexpected response from backend"
        }
    }
}

final class BackendClient {
    static let shared = BackendClient()
    private let baseURL = URL(string: "http://localhost:8000")!

    func isReachable() async -> Bool {
        guard let url = URL(string: "/health", relativeTo: baseURL) else { return false }
        do {
            let (_, response) = try await URLSession.shared.data(from: url)
            return (response as? HTTPURLResponse)?.statusCode == 200
        } catch {
            return false
        }
    }

    func quickScan(domain: String) async throws -> QuickScanResponse {
        var request = URLRequest(url: URL(string: "/api/quickscan", relativeTo: baseURL)!)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(["domain": domain])
        request.timeoutInterval = 120 // quick tier, but nmap can still take a little while

        let (data, response) = try await URLSession.shared.data(for: request)
        guard (response as? HTTPURLResponse)?.statusCode == 200 else {
            throw BackendError.badResponse
        }
        return try JSONDecoder().decode(QuickScanResponse.self, from: data)
    }

    func quickAction(domain: String, tool: String) async throws -> QuickActionResponse {
        var request = URLRequest(url: URL(string: "/api/quickaction", relativeTo: baseURL)!)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(["domain": domain, "tool": tool])
        request.timeoutInterval = 180 // subdomain_enum/nikto can take a while

        let (data, response) = try await URLSession.shared.data(for: request)
        guard (response as? HTTPURLResponse)?.statusCode == 200 else {
            throw BackendError.badResponse
        }
        return try JSONDecoder().decode(QuickActionResponse.self, from: data)
    }

    /// Downloads the actual PDF bytes and saves them to ~/Downloads,
    /// returning the local file URL. This replaces the old path-based
    /// approach entirely - no dependency on the Docker volume mount
    /// resolving to the same path the host expects, since the bytes
    /// travel directly over the HTTP response body.
    func downloadReport(sessionID: String) async throws -> URL {
        var request = URLRequest(url: URL(string: "/api/sessions/\(sessionID)/report/download", relativeTo: baseURL)!)
        request.httpMethod = "POST"
        request.timeoutInterval = 180

        let (data, response) = try await URLSession.shared.data(for: request)
        guard (response as? HTTPURLResponse)?.statusCode == 200 else {
            throw BackendError.badResponse
        }

        guard let downloadsDir = FileManager.default.urls(for: .downloadsDirectory, in: .userDomainMask).first else {
            throw BackendError.badResponse
        }
        let timestamp = Int(Date().timeIntervalSince1970)
        let localURL = downloadsDir.appendingPathComponent("greybox-report-\(sessionID)-\(timestamp).pdf")
        try data.write(to: localURL)
        return localURL
    }
}