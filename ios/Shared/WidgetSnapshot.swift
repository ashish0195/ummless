import Foundation

/// What the home-screen and lock-screen widgets show. The app writes it to the shared App Group whenever its data
/// refreshes; the widget only reads it, so it never needs network access or the person's token.
struct WidgetSnapshot: Codable, Equatable, Sendable {
    /// Local day ("YYYY-MM-DD") the rep belongs to.
    var day: String
    var repTitle: String?
    var repPrompt: String?
    var repCompleted: Bool
    var weekSessions: Int
    var weekTarget: Int
    /// Weekdays practised this week, 1 = Monday.
    var weekDays: [Int]
    var weeksOnTarget: Int
    var pausedUntil: String?
    var timeZoneIdentifier: String

    static let appGroup = "group.com.comlogue.app"
    static let storageKey = "comlogue.widgetSnapshot.v1"

    static let placeholder = WidgetSnapshot(
        day: "", repTitle: "Explain your job to a 10-year-old",
        repPrompt: "Explain your work so a curious kid would get it.", repCompleted: false,
        weekSessions: 2, weekTarget: 3, weekDays: [1, 3], weeksOnTarget: 3, pausedUntil: nil,
        timeZoneIdentifier: TimeZone.current.identifier)

    var timeZone: TimeZone { TimeZone(identifier: timeZoneIdentifier) ?? .current }

    /// Today's rep is only shown on the day it was chosen for; after midnight the widget asks for a fresh one.
    func isCurrent(at date: Date = Date()) -> Bool { day == Self.dayString(date, timeZone: timeZone) }

    func isPaused(at date: Date = Date()) -> Bool {
        guard let pausedUntil else { return false }
        return Self.dayString(date, timeZone: timeZone) <= pausedUntil
    }

    static func dayString(_ date: Date, timeZone: TimeZone) -> String {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = timeZone
        let parts = calendar.dateComponents([.year, .month, .day], from: date)
        return String(format: "%04d-%02d-%02d", parts.year ?? 0, parts.month ?? 0, parts.day ?? 0)
    }

    /// The next local midnight, when the widget should roll over.
    static func nextMidnight(after date: Date, timeZone: TimeZone) -> Date {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = timeZone
        let start = calendar.startOfDay(for: date)
        return calendar.date(byAdding: .day, value: 1, to: start) ?? date.addingTimeInterval(86_400)
    }

    // MARK: Storage

    static func load(from defaults: UserDefaults?) -> WidgetSnapshot? {
        guard let data = defaults?.data(forKey: storageKey) else { return nil }
        return try? JSONDecoder().decode(WidgetSnapshot.self, from: data)
    }

    /// Returns true when something changed (so the caller reloads widget timelines only when needed).
    @discardableResult
    func save(to defaults: UserDefaults?) -> Bool {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys] // stable bytes, so an unchanged snapshot compares equal
        guard let defaults, let data = try? encoder.encode(self) else { return false }
        if defaults.data(forKey: Self.storageKey) == data { return false }
        defaults.set(data, forKey: Self.storageKey)
        return true
    }
}

/// Links the widgets open. Mirrors `DeepLink` in the app.
enum WidgetLinks {
    static let dailyRep = URL(string: "comlogue://daily")!
    static let today = URL(string: "comlogue://today")!
}
