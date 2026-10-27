import Foundation

/// Calendar and copy helpers for the practice habit. Weeks run Monday to Sunday in the person's own timezone,
/// matching the server.
enum HabitMath {
    /// Gregorian calendar in `timeZone`, weeks starting on Monday.
    static func calendar(_ timeZone: TimeZone) -> Calendar {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = timeZone
        calendar.firstWeekday = 2
        calendar.locale = Locale(identifier: "en_US_POSIX")
        return calendar
    }

    /// "YYYY-MM-DD" for `date` in `timeZone`.
    static func dayString(_ date: Date, timeZone: TimeZone) -> String {
        let parts = calendar(timeZone).dateComponents([.year, .month, .day], from: date)
        return String(format: "%04d-%02d-%02d", parts.year ?? 0, parts.month ?? 0, parts.day ?? 0)
    }

    /// Start of the local day for "YYYY-MM-DD".
    static func date(fromDay day: String, timeZone: TimeZone) -> Date? {
        let parts = day.split(separator: "-").compactMap { Int($0) }
        guard parts.count == 3 else { return nil }
        return calendar(timeZone).date(from: DateComponents(year: parts[0], month: parts[1], day: parts[2]))
    }

    /// 1 = Monday … 7 = Sunday (the API's convention).
    static func weekday(_ date: Date, timeZone: TimeZone) -> Int {
        let sundayFirst = calendar(timeZone).component(.weekday, from: date) // 1 = Sunday
        return (sundayFirst + 5) % 7 + 1
    }

    static func adding(days: Int, to date: Date, timeZone: TimeZone) -> Date {
        calendar(timeZone).date(byAdding: .day, value: days, to: date) ?? date.addingTimeInterval(Double(days) * 86_400)
    }

    /// "HH:MM" → (hour, minute).
    static func parseTime(_ value: String?) -> (hour: Int, minute: Int)? {
        guard let parts = value?.split(separator: ":").compactMap({ Int($0) }), parts.count == 2,
              (0..<24).contains(parts[0]), (0..<60).contains(parts[1]) else { return nil }
        return (parts[0], parts[1])
    }

    static func timeString(hour: Int, minute: Int) -> String { String(format: "%02d:%02d", hour, minute) }

    /// The moment `time` ("HH:MM") happens on the local day containing `day`.
    static func moment(on day: Date, at time: (hour: Int, minute: Int), timeZone: TimeZone) -> Date? {
        calendar(timeZone).date(bySettingHour: time.hour, minute: time.minute, second: 0, of: day)
    }

    /// Suggested practice days for a weekly target, spread through the week.
    static func defaultDays(forTarget target: Int) -> [Int] {
        switch target {
        case ...1: return [3]
        case 2: return [2, 4]
        case 3: return [1, 3, 5]
        case 4: return [1, 2, 4, 5]
        case 5: return [1, 2, 3, 4, 5]
        case 6: return [1, 2, 3, 4, 5, 6]
        default: return [1, 2, 3, 4, 5, 6, 7]
        }
    }

    static let weekdayInitials = ["M", "T", "W", "T", "F", "S", "S"]
    static let weekdayShortNames = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    enum DayState: Equatable, Sendable { case practiced, today, upcoming, rest }

    /// States for the Monday–Sunday strip on Today.
    static func weekStrip(practicedDays: [Int], today: Int) -> [DayState] {
        (1...7).map { day in
            if practicedDays.contains(day) { return .practiced }
            if day == today { return .today }
            return day > today ? .upcoming : .rest
        }
    }

    /// Yearly saving against twelve monthly payments, rounded down; nil when there's no saving.
    static func yearlySavingPercent(monthly: Double, yearly: Double) -> Int? {
        guard monthly > 0, yearly > 0 else { return nil }
        let percent = Int(((1 - yearly / (monthly * 12)) * 100).rounded(.down))
        return percent > 0 ? percent : nil
    }
}

/// When-and-where cues that attach practice to an existing routine ("implementation intentions").
enum PracticeAnchor {
    static func presets(for market: Market) -> [String] {
        let drink = market == .in ? "chai" : "coffee"
        return [
            "After my morning \(drink)",
            "On my commute",
            "Before my first meeting",
            "After lunch",
            "On my evening walk",
            "Before bed",
        ]
    }

    /// "After my morning chai" → "After your morning chai", for reminder copy.
    static func secondPerson(_ anchor: String) -> String {
        anchor.split(separator: " ").map { word -> String in
            switch word.lowercased() {
            case "my": return "your"
            case "i": return "you"
            case "i'm": return "you're"
            case "me": return "you"
            default: return String(word)
            }
        }.joined(separator: " ")
    }
}

/// A practice moment tied to something people already do: the cue and the time in one choice.
struct PracticeRoutine: Hashable, Sendable, Identifiable {
    let id: String
    let title: String
    let symbol: String
    /// Stored as `practice_settings.anchor`.
    let anchor: String
    /// "HH:MM"
    let time: String

    static func options(for market: Market) -> [PracticeRoutine] {
        let drink = market == .in ? "chai" : "coffee"
        return [
            PracticeRoutine(id: "morning", title: "With my morning \(drink)", symbol: "sunrise.fill",
                            anchor: "After my morning \(drink)", time: "08:00"),
            PracticeRoutine(id: "lunch", title: "After lunch", symbol: "sun.max.fill", anchor: "After lunch", time: "13:00"),
            PracticeRoutine(id: "evening", title: "After work", symbol: "sunset.fill", anchor: "After work", time: "19:00"),
            PracticeRoutine(id: "night", title: "Before bed", symbol: "moon.stars.fill", anchor: "Before bed", time: "21:30"),
        ]
    }

    /// The routine a saved plan matches, by its time.
    static func matching(time: String?, market: Market) -> PracticeRoutine? {
        options(for: market).first { $0.time == time }
    }
}

