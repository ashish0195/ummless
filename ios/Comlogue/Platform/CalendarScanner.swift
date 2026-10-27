import EventKit
import Foundation

/// An upcoming calendar entry that looks worth rehearsing for.
struct CalendarSuggestion: Identifiable, Hashable {
    let id: String
    let title: String
    let start: Date
    let isAllDay: Bool
    let kind: String
}

/// Reads the next two weeks of the person's calendar on the device to suggest prep. Read-only, opt-in.
@MainActor
enum CalendarScanner {
    private static let store = EKEventStore()

    static var isAuthorized: Bool { EKEventStore.authorizationStatus(for: .event) == .fullAccess }
    static var canAsk: Bool { EKEventStore.authorizationStatus(for: .event) == .notDetermined }

    static func requestAccess() async -> Bool {
        (try? await store.requestFullAccessToEvents()) ?? false
    }

    /// Suggestions in the next `days` days, skipping anything already added as an event.
    static func suggestions(days: Int = 14, excluding existing: [UpcomingEvent]) -> [CalendarSuggestion] {
        guard isAuthorized else { return [] }
        let now = Date()
        let end = now.addingTimeInterval(Double(days) * 86_400)
        let predicate = store.predicateForEvents(withStart: now, end: end, calendars: nil)
        let taken = Set(existing.map { "\($0.title.lowercased())|\($0.date)" })
        return store.events(matching: predicate)
            .compactMap { event -> CalendarSuggestion? in
                guard let title = event.title, let kind = EventClassifier.kind(for: title) else { return nil }
                let day = HabitMath.dayString(event.startDate, timeZone: .current)
                guard !taken.contains("\(title.lowercased())|\(day)") else { return nil }
                return CalendarSuggestion(id: event.calendarItemIdentifier + "\(event.startDate.timeIntervalSince1970)",
                                          title: title, start: event.startDate, isAllDay: event.isAllDay, kind: kind)
            }
            .sorted { $0.start < $1.start }
    }
}
