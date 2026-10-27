import Foundation

/// Where someone practises. Drives content (names, places, ₹ or $), date formats and pricing.
enum Market: String, Codable, Hashable, Sendable, CaseIterable {
    case us, `in`, global

    init(from decoder: Decoder) throws {
        let raw = try decoder.singleValueContainer().decode(String.self)
        self = Market(rawValue: raw) ?? .global
    }

    /// Mirrors the server: `IN`/`IN-*` → India, `US`/`US-*` → US (`US-IN` is Indiana), anything else → global.
    static func from(region: String?) -> Market {
        guard let code = region?.uppercased(), !code.isEmpty else { return .global }
        if code == "IN" || code.hasPrefix("IN-") { return .in }
        if code == "US" || code.hasPrefix("US-") { return .us }
        return .global
    }
}

// MARK: - Notifications

enum NotificationCategory: String, Codable, Hashable, Sendable, CaseIterable {
    case practice
    case eventPrep = "event_prep"
    case results
    case checkIn = "check_in"
    case nudge
    case weeklyReveal = "weekly_reveal"
    case milestone
    case tips
    case other

    init(from decoder: Decoder) throws {
        let raw = try decoder.singleValueContainer().decode(String.self)
        self = NotificationCategory(rawValue: raw) ?? .other
    }
}

/// An inbox item (named to avoid clashing with Foundation's `Notification`).
struct InboxNotification: Codable, Hashable, Sendable, Identifiable {
    let id: String
    let category: NotificationCategory
    let title: String
    let body: String
    let deepLink: String
    let createdAt: Date
    let read: Bool
}

struct NotificationsResponse: Codable, Sendable {
    let items: [InboxNotification]
    let unreadCount: Int
}

struct ReadNotificationsRequest: Codable, Sendable {
    var ids: [String]?
    var all: Bool?
}

struct UnreadCountResponse: Codable, Sendable {
    let unreadCount: Int
}

struct DeviceRegistration: Codable, Hashable, Sendable {
    var apnsToken: String?
    var pushEnvironment: String?
    var authorization: String
    var timezone: String
    var locale: String
    var appVersion: String
}

struct DeviceInfo: Codable, Sendable {
    let id: String
    /// True when the server will actually deliver pushes to this device; otherwise the app schedules its own.
    let pushEnabled: Bool
}

// MARK: - Daily rep

struct DailyRep: Codable, Hashable, Sendable, Identifiable {
    let date: String
    let promptId: String
    let title: String
    let prompt: String
    let kind: String
    let dimension: DimensionId
    let targetBehavior: String
    let tips: [String]
    let suggestedSeconds: Int
    let example: String?
    let canShuffle: Bool
    let completed: Bool
    let attempts: [MissionAttempt]

    var id: String { date }
    var latestAttempt: MissionAttempt? { attempts.max { $0.attemptNumber < $1.attemptNumber } }
    var isProcessing: Bool { attempts.contains { $0.isProcessing } }
}

struct DailyRepPreview: Codable, Hashable, Sendable, Identifiable {
    let date: String
    let promptId: String
    let title: String
    let prompt: String
    let dimension: DimensionId

    var id: String { date }
}

// MARK: - Group conversations

struct Panel: Codable, Hashable, Sendable, Identifiable {
    let id: String
    let kind: String
    let title: String
    let scenario: String
    let description: String
    let topic: String?
    let userRole: String
    let participants: [Participant]
    let minutes: Int
    let markets: [String]
    let isFree: Bool
    let symbol: String
    let colorHex: String
    let defaultDifficulty: Difficulty

    var isGroupDiscussion: Bool { kind == "group_discussion" }
    var moderator: Participant? { participants.first }
}

struct PanelsResponse: Codable, Sendable {
    let panels: [Panel]
}
