import Foundation

enum Brand {
    static let name = "Comlogue"
    static let tagline = "Say what you mean. Be understood."
    static let supportEmail = "support@comlogue.app"
    static let termsURL = URL(string: "https://comlogue.app/terms")!
    static let privacyURL = URL(string: "https://comlogue.app/privacy")!
    static let websiteURL = URL(string: "https://comlogue.app")!

    /// What a person sends a friend (WhatsApp is how most Indian users will share it).
    static func inviteMessage(market: Market) -> String {
        switch market {
        case .in:
            return "I've been practising how I speak with Comlogue: 60 seconds a day for interviews, GDs and work calls. Try it with me:"
        default:
            return "I've been practising how I speak with Comlogue: 60 seconds a day for interviews, meetings and hard conversations. Try it with me:"
        }
    }
}

/// Local fallbacks for UI metadata so screens render before /v1/meta arrives (or offline).
enum DimensionCatalog {
    static func title(_ id: DimensionId) -> String {
        switch id {
        case .clarity: return "Clarity"
        case .structure: return "Structure"
        case .listening: return "Listening"
        case .warmth: return "Warmth"
        case .persuasion: return "Persuasion"
        case .concision: return "Concision"
        case .storytelling: return "Storytelling"
        }
    }

    static func blurb(_ id: DimensionId) -> String {
        switch id {
        case .clarity: return "People understand your point the first time."
        case .structure: return "Your ideas arrive in an order that's easy to follow."
        case .listening: return "You show you heard what the other person meant."
        case .warmth: return "People feel respected and at ease with you."
        case .persuasion: return "You make a case that moves people to act."
        case .concision: return "You say what matters without detours."
        case .storytelling: return "Your experiences become stories people remember."
        }
    }

    static func symbol(_ id: DimensionId) -> String {
        switch id {
        case .clarity: return "sun.max.fill"
        case .structure: return "square.stack.3d.up.fill"
        case .listening: return "ear.fill"
        case .warmth: return "heart.fill"
        case .persuasion: return "megaphone.fill"
        case .concision: return "scissors"
        case .storytelling: return "book.fill"
        }
    }

    static func colorHex(_ id: DimensionId) -> String {
        switch id {
        case .clarity: return "#2F9BFF"
        case .structure: return "#6366F1"
        case .listening: return "#10B3A3"
        case .warmth: return "#FF8A3D"
        case .persuasion: return "#E64980"
        case .concision: return "#7CB518"
        case .storytelling: return "#9B5DE5"
        }
    }

    static func levelLabel(_ level: Int) -> String {
        switch level {
        case ...1: return "Emerging"
        case 2: return "Developing"
        case 3: return "Capable"
        case 4: return "Strong"
        default: return "Exceptional"
        }
    }

    static func statusLabel(_ status: DimensionStatus) -> String {
        switch status {
        case .assessed: return "Assessed"
        case .provisional: return "Early read"
        case .notEnoughEvidence, .notAssessed: return "Not enough evidence yet"
        }
    }

    static func confidenceLabel(_ confidence: Confidence?) -> String {
        switch confidence {
        case .high: return "High confidence"
        case .moderate: return "Moderate confidence"
        case .low: return "Low confidence"
        case nil: return "Confidence unknown"
        }
    }
}

enum ActivityCatalog {
    static func symbol(_ id: ActivityId) -> String {
        switch id {
        case "meet_someone_new": return "hand.wave.fill"
        case "explain_interest": return "lightbulb.fill"
        case "respond_to_someone": return "bubble.left.and.bubble.right.fill"
        case "make_a_case": return "hand.thumbsup.fill"
        case "tell_a_story": return "book.pages.fill"
        default: return "waveform"
        }
    }
}

enum MissionCatalog {
    static func title(_ type: MissionType) -> String {
        switch type {
        case .learnAndTry: return "Learn & try"
        case .remix: return "Remix"
        case .realLife: return "Real-life mission"
        case .weeklyReveal: return "Weekly reveal"
        }
    }

    static func symbol(_ type: MissionType) -> String {
        switch type {
        case .learnAndTry: return "sparkles"
        case .remix: return "shuffle"
        case .realLife: return "figure.walk"
        case .weeklyReveal: return "gift.fill"
        }
    }
}

enum DifficultyCatalog {
    static func title(_ difficulty: Difficulty) -> String {
        switch difficulty {
        case .kind: return "Kind"
        case .real: return "Real"
        case .brutal: return "Brutal"
        }
    }

    static func blurb(_ difficulty: Difficulty) -> String {
        switch difficulty {
        case .kind: return "Patient and encouraging."
        case .real: return "Like a real person on a normal day."
        case .brutal: return "Impatient, skeptical, interrupts."
        }
    }
}

enum Formatting {
    /// 75 → "1:15"
    static func clock(_ seconds: Double) -> String {
        let total = max(0, Int(seconds.rounded(.down)))
        return String(format: "%d:%02d", total / 60, total % 60)
    }

    /// 75 → "1 min", 30 → "30 sec", 600 → "10 min"
    static func shortDuration(_ seconds: Double) -> String {
        if seconds < 60 { return "\(Int(seconds.rounded())) sec" }
        return "\(Int((seconds / 60).rounded())) min"
    }

    static func minutesRange(_ range: [Int]) -> String {
        guard let first = range.first else { return "" }
        if let last = range.last, last != first { return "\(first)–\(last) min" }
        return "\(first) min"
    }

    static func percent(_ value: Double) -> String { "\(Int((value * 100).rounded()))%" }

    /// 14.99 → "$14.99"
    static func usd(_ value: Double) -> String { String(format: "$%.2f", value) }

    static func oneDecimal(_ value: Double) -> String { String(format: "%.1f", value) }

    static func shortDate(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.dateStyle = .medium
        formatter.timeStyle = .none
        return formatter.string(from: date)
    }

    static func relative(_ date: Date, now: Date = Date()) -> String {
        let seconds = now.timeIntervalSince(date)
        if seconds < 60 { return "just now" }
        if seconds < 3600 { return "\(Int(seconds / 60)) min ago" }
        if seconds < 86_400 { return "\(Int(seconds / 3600)) h ago" }
        let days = Int(seconds / 86_400)
        if days < 7 { return days == 1 ? "yesterday" : "\(days) days ago" }
        return shortDate(date)
    }

    static func greeting(for date: Date = Date(), calendar: Calendar = .current) -> String {
        let hour = calendar.component(.hour, from: date)
        switch hour {
        case 5..<12: return "Good morning"
        case 12..<17: return "Good afternoon"
        case 17..<22: return "Good evening"
        default: return "Hello"
        }
    }

    /// Parses "#RRGGBB" into 0–1 RGB components.
    static func rgb(fromHex hex: String) -> (red: Double, green: Double, blue: Double)? {
        var string = hex.trimmingCharacters(in: .whitespacesAndNewlines)
        if string.hasPrefix("#") { string.removeFirst() }
        guard string.count == 6, let value = UInt32(string, radix: 16) else { return nil }
        return (Double((value >> 16) & 0xFF) / 255, Double((value >> 8) & 0xFF) / 255, Double(value & 0xFF) / 255)
    }
}
