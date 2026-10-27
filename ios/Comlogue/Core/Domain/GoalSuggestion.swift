import Foundation

/// Suggests a goal area from the onboarding answers. Only a suggestion — the person always chooses.
enum GoalSuggestion {
    static func suggest(contextsRanked: [String], easeTargets: Set<String>, available: [String]) -> String? {
        var score: [String: Double] = [:]
        let weights: [Double] = [3, 2, 1, 1]
        for (index, context) in contextsRanked.enumerated() {
            let weight = weights[min(index, weights.count - 1)]
            switch context {
            case "social":
                score["conversational", default: 0] += weight
                score["storytelling", default: 0] += weight * 0.4
            case "networking":
                score["conversational", default: 0] += weight * 0.7
                score["business", default: 0] += weight * 0.5
            case "meetings":
                score["business", default: 0] += weight
            case "interviews":
                score["business", default: 0] += weight * 0.6
                score["storytelling", default: 0] += weight * 0.5
            default:
                break
            }
        }
        for ease in easeTargets {
            switch ease {
            case "persuading": score["negotiation", default: 0] += 2
            case "concise": score["business", default: 0] += 1.5
            case "explaining": score["public_speaking", default: 0] += 1.5
            case "connecting": score["conversational", default: 0] += 1.5
            case "contributing": score["business", default: 0] += 1.2
            default: break
            }
        }
        let candidates = score.filter { available.contains($0.key) }
        // Highest score wins; ties resolve by the order the server lists the tracks, so the result is stable.
        let best = candidates.max { lhs, rhs in
            if lhs.value != rhs.value { return lhs.value < rhs.value }
            return (available.firstIndex(of: lhs.key) ?? 0) > (available.firstIndex(of: rhs.key) ?? 0)
        }
        return best?.key ?? available.first
    }
}

/// One-tap goals for the first-run walkthrough, in plain words. The spec's onboarding answers (ranked contexts and
/// what should feel easier) are derived from the goal, so a newcomer answers one question instead of three.
struct GoalChoice: Hashable, Sendable, Identifiable {
    let id: String // track id
    let title: String
    let symbol: String

    /// Most common first, per market: placements and interviews lead in India.
    static func ordered(for market: Market, available: [String]) -> [GoalChoice] {
        let all: [GoalChoice] = [
            GoalChoice(id: "business", title: "Meetings at work", symbol: "person.3.fill"),
            GoalChoice(id: "interviews", title: "Job interviews", symbol: "briefcase.fill"),
            GoalChoice(id: "conversational", title: "Everyday conversations", symbol: "bubble.left.and.bubble.right.fill"),
            GoalChoice(id: "public_speaking", title: "Speaking to a group", symbol: "megaphone.fill"),
            GoalChoice(id: "negotiation", title: "Asking for what I want", symbol: "hand.raised.fill"),
            GoalChoice(id: "storytelling", title: "Telling better stories", symbol: "book.fill"),
        ]
        var ordered = all
        if market == .in, let index = ordered.firstIndex(where: { $0.id == "interviews" }) {
            ordered.insert(ordered.remove(at: index), at: 0)
        }
        return available.isEmpty ? ordered : ordered.filter { available.contains($0.id) }
    }

    /// The contexts (most relevant first) and "what should feel easier" answers implied by a goal.
    static func answers(for goal: String) -> (contexts: [String], ease: [String]) {
        switch goal {
        case "interviews": return (["interviews", "meetings", "networking", "social"], ["concise"])
        case "negotiation": return (["meetings", "networking", "interviews", "social"], ["persuading"])
        case "conversational": return (["social", "networking", "meetings", "interviews"], ["connecting"])
        case "storytelling": return (["social", "meetings", "networking", "interviews"], ["explaining"])
        case "public_speaking": return (["meetings", "networking", "social", "interviews"], ["explaining"])
        default: return (["meetings", "interviews", "networking", "social"], ["concise", "contributing"])
        }
    }
}
