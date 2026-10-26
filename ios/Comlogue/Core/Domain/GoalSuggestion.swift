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
