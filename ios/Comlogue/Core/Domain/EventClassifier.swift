import Foundation

/// Spots calendar entries worth preparing for, from their titles alone. Runs on the device; nothing is sent
/// unless the person chooses to prepare for one.
enum EventClassifier {
    /// Ordered most specific first; the first match wins.
    private static let rules: [(kind: String, keywords: [String])] = [
        ("group_discussion", ["group discussion", "gd round", " gd ", "gd-", "(gd)"]),
        ("placement", ["placement", "campus drive", "campus hiring", "pre-placement", "ppt "]),
        ("viva", ["viva", "thesis defense", "thesis defence", "dissertation", "defense of"]),
        ("appraisal", ["appraisal", "performance review", "perf review", "annual review", "mid-year review", "promotion"]),
        ("interview", ["interview", "screening call", "hr round", "technical round", "recruiter", "onsite loop",
                       "hiring manager"]),
        ("negotiation", ["negotiation", "offer call", "salary", "compensation", "contract review", "rent "]),
        ("client_call", ["client", "customer call", "escalation", "qbr", "stakeholder", "steerco", "steering committee"]),
        ("presentation", ["presentation", "pitch", "demo day", "demo ", "keynote", "webinar", "town hall", "all hands",
                          "talk at", "seminar"]),
        ("social", ["wedding", "toast", "farewell", "reunion", "networking", "meetup", "mixer"]),
    ]

    /// The event kind for a calendar title, or nil when it doesn't look like a moment to rehearse for.
    static func kind(for title: String) -> String? {
        let text = " " + title.lowercased() + " "
        return rules.first { rule in rule.keywords.contains { text.contains($0) } }?.kind
    }
}
