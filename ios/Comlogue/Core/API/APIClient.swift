import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

/// A file attached to a multipart request.
struct UploadFile: Sendable {
    let data: Data
    let fileName: String
    let mimeType: String

    static func audio(at url: URL) throws -> UploadFile {
        let data = try Data(contentsOf: url)
        return UploadFile(data: data, fileName: url.lastPathComponent, mimeType: mimeType(for: url))
    }

    static func mimeType(for url: URL) -> String {
        switch url.pathExtension.lowercased() {
        case "m4a", "mp4", "aac": return "audio/mp4"
        case "mp3": return "audio/mpeg"
        case "wav": return "audio/wav"
        case "caf": return "audio/x-caf"
        case "aif", "aiff": return "audio/aiff"
        case "ogg", "oga": return "audio/ogg"
        case "webm": return "audio/webm"
        case "flac": return "audio/flac"
        case "mov": return "video/quicktime"
        default: return "application/octet-stream"
        }
    }
}

/// Thin, cross-platform HTTP client for the Comlogue API (also compiled on Linux for contract tests).
final class APIClient: @unchecked Sendable {
    private(set) var baseURL: URL
    private let session: URLSession
    private let decoder = JSONCoding.makeDecoder()
    private let encoder = JSONCoding.makeEncoder()
    private let lock = NSLock()
    private var _token: String?

    /// Called once when a request returns 401; should obtain a fresh token and return true on success.
    var reauthenticate: (@Sendable () async -> Bool)?

    init(baseURL: URL, token: String? = nil, session: URLSession? = nil) {
        self.baseURL = baseURL
        self._token = token
        if let session {
            self.session = session
        } else {
            let config = URLSessionConfiguration.default
            config.timeoutIntervalForRequest = 90
            config.timeoutIntervalForResource = 600
            self.session = URLSession(configuration: config)
        }
    }

    var token: String? {
        get { lock.lock(); defer { lock.unlock() }; return _token }
        set { lock.lock(); _token = newValue; lock.unlock() }
    }

    func updateBaseURL(_ url: URL) { baseURL = url }

    /// Resolves relative API paths (like media URLs) against the base URL.
    func resolve(_ pathOrURL: String) -> URL? {
        if let absolute = URL(string: pathOrURL), absolute.scheme != nil { return absolute }
        return URL(string: pathOrURL, relativeTo: baseURL)?.absoluteURL
    }

    // MARK: - JSON requests

    func get<T: Decodable>(_ path: String, query: [String: String] = [:]) async throws -> T {
        try await send(method: "GET", path: path, query: query, body: nil)
    }

    func post<T: Decodable>(_ path: String) async throws -> T {
        try await send(method: "POST", path: path, query: [:], body: nil)
    }

    func post<T: Decodable, Body: Encodable>(_ path: String, body: Body) async throws -> T {
        try await send(method: "POST", path: path, query: [:], body: try encoder.encode(body))
    }

    func patch<T: Decodable, Body: Encodable>(_ path: String, body: Body) async throws -> T {
        try await send(method: "PATCH", path: path, query: [:], body: try encoder.encode(body))
    }

    func delete(_ path: String) async throws {
        let request = try makeRequest(method: "DELETE", path: path, query: [:], body: nil, contentType: nil)
        _ = try await execute(request)
    }

    /// Multipart upload with an `audio` file part plus string fields.
    func upload<T: Decodable>(
        _ path: String,
        file: UploadFile,
        fields: [String: String] = [:],
        timeout: TimeInterval = 300
    ) async throws -> T {
        let boundary = "Boundary-\(UUID().uuidString)"
        let body = Self.multipartBody(boundary: boundary, file: file, fields: fields)
        var request = try makeRequest(
            method: "POST",
            path: path,
            query: [:],
            body: body,
            contentType: "multipart/form-data; boundary=\(boundary)"
        )
        request.timeoutInterval = timeout
        let data = try await execute(request)
        return try decode(T.self, from: data)
    }

    /// Downloads raw bytes (e.g. audio). Adds auth when the URL points at our API.
    func download(_ pathOrURL: String) async throws -> Data {
        guard let url = resolve(pathOrURL) else { throw APIError.invalidResponse }
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        if url.host == baseURL.host, let token { request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization") }
        return try await execute(request)
    }

    // MARK: - Internals

    private func send<T: Decodable>(method: String, path: String, query: [String: String], body: Data?) async throws -> T {
        let request = try makeRequest(method: method, path: path, query: query, body: body, contentType: body == nil ? nil : "application/json")
        let data = try await execute(request)
        return try decode(T.self, from: data)
    }

    private func decode<T: Decodable>(_ type: T.Type, from data: Data) throws -> T {
        do {
            return try decoder.decode(T.self, from: data)
        } catch {
            throw APIError.decoding(String(describing: error))
        }
    }

    private func makeRequest(method: String, path: String, query: [String: String], body: Data?, contentType: String?) throws -> URLRequest {
        guard var components = URLComponents(url: baseURL.appendingPathComponent(path.hasPrefix("/") ? String(path.dropFirst()) : path), resolvingAgainstBaseURL: false) else {
            throw APIError.notConfigured
        }
        if !query.isEmpty {
            components.queryItems = query.sorted { $0.key < $1.key }.map { URLQueryItem(name: $0.key, value: $0.value) }
        }
        guard let url = components.url else { throw APIError.notConfigured }
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.httpBody = body
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        if let contentType { request.setValue(contentType, forHTTPHeaderField: "Content-Type") }
        if let token { request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization") }
        return request
    }

    /// Runs a request, maps HTTP errors to `APIError`, and retries once after re-authenticating on 401.
    private func execute(_ request: URLRequest, allowReauth: Bool = true) async throws -> Data {
        let (data, response) = try await perform(request)
        if (200..<300).contains(response.statusCode) { return data }

        if response.statusCode == 401, allowReauth, let reauthenticate, await reauthenticate() {
            var retried = request
            if let token { retried.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization") }
            return try await execute(retried, allowReauth: false)
        }

        if let envelope = try? decoder.decode(APIErrorEnvelope.self, from: data) {
            throw APIError.server(status: response.statusCode, code: envelope.error.code, message: envelope.error.message)
        }
        throw APIError.server(status: response.statusCode, code: "http_\(response.statusCode)", message: "")
    }

    private func perform(_ request: URLRequest) async throws -> (Data, HTTPURLResponse) {
        try await withCheckedThrowingContinuation { continuation in
            let task = session.dataTask(with: request) { data, response, error in
                if let error {
                    continuation.resume(throwing: APIError.network(error.localizedDescription))
                    return
                }
                guard let http = response as? HTTPURLResponse else {
                    continuation.resume(throwing: APIError.invalidResponse)
                    return
                }
                continuation.resume(returning: (data ?? Data(), http))
            }
            task.resume()
        }
    }

    static func multipartBody(boundary: String, file: UploadFile, fields: [String: String]) -> Data {
        var body = Data()
        func append(_ string: String) { body.append(Data(string.utf8)) }
        for (name, value) in fields.sorted(by: { $0.key < $1.key }) {
            append("--\(boundary)\r\n")
            append("Content-Disposition: form-data; name=\"\(name)\"\r\n\r\n")
            append("\(value)\r\n")
        }
        append("--\(boundary)\r\n")
        append("Content-Disposition: form-data; name=\"audio\"; filename=\"\(file.fileName)\"\r\n")
        append("Content-Type: \(file.mimeType)\r\n\r\n")
        body.append(file.data)
        append("\r\n--\(boundary)--\r\n")
        return body
    }

    func encodeJSONString<T: Encodable>(_ value: T) -> String {
        guard let data = try? encoder.encode(value) else { return "{}" }
        return String(decoding: data, as: UTF8.self)
    }
}

/// An empty JSON object, for endpoints that return `{}` or 204.
struct EmptyResponse: Codable, Sendable {}
