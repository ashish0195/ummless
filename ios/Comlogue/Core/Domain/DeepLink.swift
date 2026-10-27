import Foundation

/// `comlogue://` links used by notifications, the inbox, widgets and Shortcuts. Mirrors docs/API.md.
enum DeepLink: Hashable, Sendable {
    case today
    case daily(date: String?)
    case mission(id: String)
    case reflect(missionId: String)
    case recording(id: String)
    case assessment(id: String)
    case event(id: String)
    case weeklyReview
    case inbox
    case practice
    case group(panelId: String)
    case paywall
    case notificationSettings

    static let scheme = "comlogue"

    init?(string: String) {
        guard let url = URL(string: string) else { return nil }
        self.init(url: url)
    }

    init?(url: URL) {
        guard url.scheme?.lowercased() == Self.scheme, let host = url.host?.lowercased() else { return nil }
        let parts = url.path.split(separator: "/").map(String.init)
        let first = parts.first
        switch host {
        case "today": self = .today
        case "daily": self = .daily(date: first)
        case "inbox": self = .inbox
        case "practice": self = .practice
        case "paywall": self = .paywall
        case "review" where first == nil || first == "weekly": self = .weeklyReview
        case "settings" where first == "notifications": self = .notificationSettings
        case "mission": guard let first else { return nil }; self = .mission(id: first)
        case "reflect": guard let first else { return nil }; self = .reflect(missionId: first)
        case "recording": guard let first else { return nil }; self = .recording(id: first)
        case "assessment": guard let first else { return nil }; self = .assessment(id: first)
        case "event": guard let first else { return nil }; self = .event(id: first)
        case "group": guard let first else { return nil }; self = .group(panelId: first)
        default: return nil
        }
    }

    var url: URL {
        let path: String
        switch self {
        case .today: path = "today"
        case .daily(let date): path = date.map { "daily/\($0)" } ?? "daily"
        case .mission(let id): path = "mission/\(id)"
        case .reflect(let missionId): path = "reflect/\(missionId)"
        case .recording(let id): path = "recording/\(id)"
        case .assessment(let id): path = "assessment/\(id)"
        case .event(let id): path = "event/\(id)"
        case .weeklyReview: path = "review/weekly"
        case .inbox: path = "inbox"
        case .practice: path = "practice"
        case .group(let panelId): path = "group/\(panelId)"
        case .paywall: path = "paywall"
        case .notificationSettings: path = "settings/notifications"
        }
        // Ids are server slugs ([a-z0-9._-]); nothing here needs percent-encoding.
        return URL(string: "\(Self.scheme)://\(path)")!
    }
}
