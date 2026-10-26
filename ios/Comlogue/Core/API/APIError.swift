import Foundation

enum APIError: Error, Equatable, Sendable {
    case server(status: Int, code: String, message: String)
    case network(String)
    case decoding(String)
    case invalidResponse
    case notConfigured

    var code: String {
        switch self {
        case .server(_, let code, _): return code
        case .network: return "network"
        case .decoding: return "decoding"
        case .invalidResponse: return "invalid_response"
        case .notConfigured: return "not_configured"
        }
    }

    var status: Int? {
        if case .server(let status, _, _) = self { return status }
        return nil
    }

    var isSubscriptionRequired: Bool { code == "subscription_required" || status == 402 }
    var isConsentRequired: Bool { code == "consent_required" }
    var isUnauthorized: Bool { status == 401 }

    /// Copy that is safe to show to people: specific when we know what happened, calm when we don't.
    var userMessage: String {
        switch self {
        case .server(let status, let code, let message):
            switch code {
            case "subscription_required": return "This is part of Comlogue Pro."
            case "rate_limited": return "You're going fast! Give it a few seconds and try again."
            case "file_too_large": return message.isEmpty ? "That file is too large to analyse." : message
            case "unsupported_media": return "We can't open that type of file. Try an audio file like M4A, MP3 or WAV."
            case "ai_unavailable": return "Our AI coach is briefly unavailable. Your recording is safe — try again in a minute."
            default:
                if !message.isEmpty { return message }
                return status >= 500 ? "Something went wrong on our side. Please try again." : "That didn't work. Please try again."
            }
        case .network:
            return "We couldn't reach Comlogue. Check your connection and try again."
        case .decoding:
            return "We got an unexpected response. Please update the app or try again."
        case .invalidResponse:
            return "We got an unexpected response. Please try again."
        case .notConfigured:
            return "The app isn't connected to a server yet."
        }
    }
}

extension Error {
    /// Friendly message for any error surfaced in the UI.
    var userMessage: String {
        if let api = self as? APIError { return api.userMessage }
        return (self as NSError).localizedDescription
    }
}
