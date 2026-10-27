import Foundation

/// A notification the app schedules on the device.
struct LocalNotification: Hashable, Sendable {
    enum Kind: String, Hashable, Sendable {
        case practice
        case eventPrep = "event_prep"
        case checkIn = "check_in"
        case weeklyReveal = "weekly_reveal"
        case nudge

        /// Lower wins when a day has more than the cap.
        var priority: Int {
            switch self {
            case .eventPrep: return 0
            case .checkIn: return 1
            case .practice: return 2
            case .weeklyReveal: return 3
            case .nudge: return 4
            }
        }
    }

    let id: String
    let kind: Kind
    let fireDate: Date
    let title: String
    let body: String
    let deepLink: DeepLink

    var threadId: String { kind.rawValue }
}

struct PlannedEvent: Hashable, Sendable {
    let id: String
    let title: String
    let date: String // YYYY-MM-DD
    let time: String? // HH:MM
}

struct NotificationPlanInput: Sendable {
    var now: Date
    var timeZone: TimeZone
    var settings: NotificationSettings = .defaults
    var practiceDays: [Int] = []
    var reminderTime: String?
    var anchor: String?
    var pausedUntil: String?
    var weeklyTarget: Int = 3
    var practicedToday = false
    /// At least one session this week (Monday to Sunday), so Sunday's weekly reveal has something to show.
    var practicedThisWeek = false
    var upcomingReps: [DailyRepPreview] = []
    var events: [PlannedEvent] = []
    /// The server delivers event prep, check-ins and nudges by push, so the device mustn't duplicate them.
    var serverSendsPush = false
    var horizonDays = 7
}

/// Decides which reminders to schedule locally for the next week.
///
/// Rules:
/// - Practice reminders go out on the chosen days at the chosen time. They follow that explicit choice even
///   inside quiet hours, and are skipped on a day already practised or during a break.
/// - Event prep, check-ins and Sunday's weekly reveal are planned only when the server isn't pushing them.
/// - Re-engagement nudges (3 and 8 days out) are re-planned on every app open, so they only fire if the person
///   stays away, and never on a day that already has a practice reminder.
/// - Everything except practice respects quiet hours. Each day is capped at two notifications (event prep
///   first), and the plan stays well under iOS's 64 pending local notifications.
enum NotificationPlanner {
    static let identifierPrefix = "comlogue.local."
    static let maxPending = 48
    static let maxPerDay = 2

    static func plan(_ input: NotificationPlanInput) -> [LocalNotification] {
        let zone = input.timeZone
        let calendar = HabitMath.calendar(zone)
        let startOfToday = calendar.startOfDay(for: input.now)
        let todayString = HabitMath.dayString(input.now, timeZone: zone)
        var planned: [LocalNotification] = []

        func isPaused(_ day: String) -> Bool { input.pausedUntil.map { day <= $0 } ?? false }

        // Practice reminders.
        if input.settings.practiceReminders, let time = HabitMath.parseTime(input.reminderTime) {
            for offset in 0..<input.horizonDays {
                let day = HabitMath.adding(days: offset, to: startOfToday, timeZone: zone)
                let dayString = HabitMath.dayString(day, timeZone: zone)
                guard input.practiceDays.contains(HabitMath.weekday(day, timeZone: zone)), !isPaused(dayString),
                      !(offset == 0 && input.practicedToday),
                      let fire = HabitMath.moment(on: day, at: time, timeZone: zone), fire > input.now else { continue }
                let rep = input.upcomingReps.first { $0.date == dayString }
                let copy = practiceCopy(rep: rep, anchor: input.anchor, variant: offset)
                planned.append(LocalNotification(id: identifierPrefix + "practice.\(dayString)", kind: .practice,
                                                 fireDate: fire, title: copy.title, body: copy.body,
                                                 deepLink: .daily(date: dayString == todayString ? nil : dayString)))
            }
        }

        if !input.serverSendsPush {
            // Event prep and check-ins.
            for event in input.events {
                guard let eventDay = HabitMath.date(fromDay: event.date, timeZone: zone) else { continue }
                if input.settings.eventPrep {
                    let eve = HabitMath.adding(days: -1, to: eventDay, timeZone: zone)
                    if let fire = HabitMath.moment(on: eve, at: (19, 0), timeZone: zone) {
                        planned.append(LocalNotification(
                            id: identifierPrefix + "event_eve.\(event.id)", kind: .eventPrep,
                            fireDate: respectingQuietHours(fire, settings: input.settings, timeZone: zone),
                            title: "Tomorrow: \(event.title)",
                            body: "A 5-minute warm-up tonight makes tomorrow easier. Your prep is ready.",
                            deepLink: .event(id: event.id)))
                    }
                    let morningOf: Date? = {
                        if let start = HabitMath.parseTime(event.time),
                           let startDate = HabitMath.moment(on: eventDay, at: start, timeZone: zone) {
                            return startDate.addingTimeInterval(-2 * 3600)
                        }
                        return HabitMath.moment(on: eventDay, at: (8, 0), timeZone: zone)
                    }()
                    let startsAt = HabitMath.parseTime(event.time).flatMap { HabitMath.moment(on: eventDay, at: $0, timeZone: zone) }
                    // Quiet hours can push an early event's reminder past its start; the evening one covers it then.
                    if let fire = morningOf.map({ respectingQuietHours($0, settings: input.settings, timeZone: zone) }),
                       startsAt.map({ fire <= $0.addingTimeInterval(-15 * 60) }) ?? true {
                        planned.append(LocalNotification(
                            id: identifierPrefix + "event_day.\(event.id)", kind: .eventPrep,
                            fireDate: fire,
                            title: "Today: \(event.title)",
                            body: "One quick practice to warm up your voice? A minute is enough.",
                            deepLink: .event(id: event.id)))
                    }
                }
                if input.settings.checkIns {
                    let after = HabitMath.adding(days: 1, to: eventDay, timeZone: zone)
                    if let fire = HabitMath.moment(on: after, at: (19, 0), timeZone: zone) {
                        planned.append(LocalNotification(
                            id: identifierPrefix + "check_in.\(event.id)", kind: .checkIn,
                            fireDate: respectingQuietHours(fire, settings: input.settings, timeZone: zone),
                            title: "How did \(event.title) go?",
                            body: "Take 30 seconds to reflect. It's how practice turns into progress.",
                            deepLink: .event(id: event.id)))
                    }
                }
            }

            // Sunday evening: the week's before-and-after moments and next week's focus.
            if input.settings.weeklyReveal, input.practicedThisWeek {
                let sunday = HabitMath.adding(days: 7 - HabitMath.weekday(input.now, timeZone: zone), to: startOfToday, timeZone: zone)
                if !isPaused(HabitMath.dayString(sunday, timeZone: zone)),
                   let fire = HabitMath.moment(on: sunday, at: (18, 0), timeZone: zone) {
                    planned.append(LocalNotification(
                        id: identifierPrefix + "weekly_reveal.\(HabitMath.dayString(sunday, timeZone: zone))", kind: .weeklyReveal,
                        fireDate: respectingQuietHours(fire, settings: input.settings, timeZone: zone),
                        title: "Your week in review is ready",
                        body: "See what changed this week and choose next week's focus.",
                        deepLink: .weeklyReview))
                }
            }

            // Re-engagement: only fires if the app isn't opened again before then.
            if input.settings.nudges, input.weeklyTarget > 0 {
                let time = HabitMath.parseTime(input.reminderTime) ?? (hour: 19, minute: 0)
                for (daysAway, isWelcomeBack) in [(3, false), (8, true)] {
                    let day = HabitMath.adding(days: daysAway, to: startOfToday, timeZone: zone)
                    let dayString = HabitMath.dayString(day, timeZone: zone)
                    guard !isPaused(dayString), let moment = HabitMath.moment(on: day, at: time, timeZone: zone) else { continue }
                    let fire = respectingQuietHours(moment, settings: input.settings, timeZone: zone)
                    // A practice reminder that day already says the same thing.
                    let fireDay = HabitMath.dayString(fire, timeZone: zone)
                    if planned.contains(where: { $0.kind == .practice && HabitMath.dayString($0.fireDate, timeZone: zone) == fireDay }) {
                        continue
                    }
                    let rep = input.upcomingReps.first { $0.date == dayString }
                    let title = isWelcomeBack ? "Welcome back whenever you're ready" : "Your 1-minute practice is waiting"
                    let body = isWelcomeBack
                        ? "Your progress is saved. Start with one short practice. No catching up needed."
                        : (rep.map { "Today's prompt: \($0.title). One minute, one small change." }
                           ?? "One minute, one small change. No catching up needed.")
                    planned.append(LocalNotification(
                        id: identifierPrefix + "nudge.\(daysAway)", kind: .nudge,
                        fireDate: fire,
                        title: title, body: body, deepLink: .daily(date: nil)))
                }
            }
        }

        // Drop anything in the past, cap each day, keep the soonest.
        let future = planned.filter { $0.fireDate > input.now }
        let byDay = Dictionary(grouping: future) { HabitMath.dayString($0.fireDate, timeZone: zone) }
        let capped = byDay.values.flatMap { day in
            day.sorted { ($0.kind.priority, $0.fireDate) < ($1.kind.priority, $1.fireDate) }.prefix(maxPerDay)
        }
        return Array(capped.sorted { $0.fireDate < $1.fireDate }.prefix(maxPending))
    }

    /// Moves a time inside quiet hours to the end of them. Quiet hours may cross midnight (22:00–08:00).
    static func respectingQuietHours(_ date: Date, settings: NotificationSettings, timeZone: TimeZone) -> Date {
        guard let start = HabitMath.parseTime(settings.quietStart), let end = HabitMath.parseTime(settings.quietEnd)
        else { return date }
        let calendar = HabitMath.calendar(timeZone)
        let parts = calendar.dateComponents([.hour, .minute], from: date)
        let minute = (parts.hour ?? 0) * 60 + (parts.minute ?? 0)
        let startMinute = start.hour * 60 + start.minute
        let endMinute = end.hour * 60 + end.minute
        guard startMinute != endMinute else { return date }
        let crossesMidnight = startMinute > endMinute
        let inQuiet = crossesMidnight ? (minute >= startMinute || minute < endMinute)
                                      : (minute >= startMinute && minute < endMinute)
        guard inQuiet else { return date }
        let day = calendar.startOfDay(for: date)
        // Late-evening times move to tomorrow morning; early-morning times to this morning.
        let endDay = crossesMidnight && minute >= startMinute ? HabitMath.adding(days: 1, to: day, timeZone: timeZone) : day
        return HabitMath.moment(on: endDay, at: end, timeZone: timeZone) ?? date
    }

    /// When "Remind me later" fires: about two hours on, but never inside quiet hours. If quiet hours begin sooner,
    /// it comes just before they do, or else when they end.
    static func snoozeDate(now: Date, settings: NotificationSettings, timeZone: TimeZone) -> Date {
        for hours in [2.0, 1.0] {
            let candidate = now.addingTimeInterval(hours * 3600)
            if respectingQuietHours(candidate, settings: settings, timeZone: timeZone) == candidate { return candidate }
        }
        let nowIsQuiet = respectingQuietHours(now, settings: settings, timeZone: timeZone) != now
        if !nowIsQuiet, let start = HabitMath.parseTime(settings.quietStart),
           let quietStart = HabitMath.moment(on: HabitMath.calendar(timeZone).startOfDay(for: now), at: start, timeZone: timeZone),
           quietStart.timeIntervalSince(now) >= 20 * 60 {
            return quietStart.addingTimeInterval(-10 * 60)
        }
        return respectingQuietHours(now.addingTimeInterval(2 * 3600), settings: settings, timeZone: timeZone)
    }

    private static func practiceCopy(rep: DailyRepPreview?, anchor: String?, variant: Int) -> (title: String, body: String) {
        let cue = anchor.map { PracticeAnchor.secondPerson($0) }
        let closers = ["One minute, one small change.", "Sixty seconds counts.", "Quick, and it adds up."]
        let closer = closers[variant % closers.count]
        if let rep {
            return (rep.title, cue.map { "\($0): today's 1-minute practice. \(closer)" } ?? "Today's 1-minute practice. \(closer)")
        }
        return ("Time for today's practice", cue.map { "\($0): your 1-minute practice is ready. \(closer)" }
            ?? "Your 1-minute practice is ready. \(closer)")
    }
}
