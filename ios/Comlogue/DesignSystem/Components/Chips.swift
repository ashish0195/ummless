import SwiftUI

/// A selectable chip, used for multi-select answers.
struct SelectableChip: View {
    let title: String
    let isSelected: Bool
    var systemImage: String?
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 6) {
                if isSelected {
                    Image(systemName: "checkmark").font(.caption.weight(.bold))
                } else if let systemImage {
                    Image(systemName: systemImage).font(.caption.weight(.semibold))
                }
                Text(title).font(.subheadline.weight(.semibold))
            }
            .padding(.vertical, 11)
            .padding(.horizontal, 16)
            .foregroundStyle(isSelected ? Color.white : Theme.ink)
            .background {
                if isSelected {
                    Capsule().fill(Theme.aurora)
                } else {
                    Capsule().fill(Theme.surface)
                }
            }
            .overlay(Capsule().strokeBorder(isSelected ? Color.clear : Theme.stroke, lineWidth: 1))
        }
        .buttonStyle(.plain)
        .accessibilityAddTraits(isSelected ? .isSelected : [])
    }
}

/// A small static tag ("BRUTAL", "3 MIN", a dimension name).
struct Tag: View {
    let text: String
    var color: Color = Theme.inkSecondary
    var systemImage: String?
    var filled: Bool = false

    var body: some View {
        HStack(spacing: 4) {
            if let systemImage { Image(systemName: systemImage).font(.caption2.weight(.bold)) }
            Text(text).font(.caption.weight(.semibold))
        }
        .padding(.vertical, 5)
        .padding(.horizontal, 10)
        .foregroundStyle(filled ? Color.white : color)
        .background(filled ? color : color.opacity(0.12), in: Capsule())
    }
}

struct DimensionTag: View {
    let dimension: DimensionId
    var compact = false

    var body: some View {
        Tag(text: DimensionCatalog.title(dimension), color: Theme.color(for: dimension),
            systemImage: compact ? nil : DimensionCatalog.symbol(dimension))
    }
}

/// Visible whenever the backend runs without an AI key, so demo output is never mistaken for real analysis.
struct DemoBadge: View {
    /// Icon only, for crowded headers.
    var compact = false

    var body: some View {
        Group {
            if compact {
                Image(systemName: "theatermasks.fill")
            } else {
                Label("Demo mode", systemImage: "theatermasks.fill")
            }
        }
        .font(.caption2.weight(.bold))
        .padding(.vertical, 4)
        .padding(.horizontal, compact ? 6 : 8)
        .foregroundStyle(Theme.amber)
        .background(Theme.amber.opacity(0.14), in: Capsule())
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Demo mode: results are simulated, not real analysis")
    }
}

/// Wraps children onto new lines, like text.
struct FlowLayout: Layout {
    var spacing: CGFloat = 8
    var lineSpacing: CGFloat = 8

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let maxWidth = proposal.width ?? .infinity
        var x: CGFloat = 0
        var y: CGFloat = 0
        var lineHeight: CGFloat = 0
        var widest: CGFloat = 0
        for subview in subviews {
            let size = subview.sizeThatFits(.unspecified)
            if x > 0 && x + size.width > maxWidth {
                y += lineHeight + lineSpacing
                x = 0
                lineHeight = 0
            }
            x += size.width + spacing
            widest = max(widest, x - spacing)
            lineHeight = max(lineHeight, size.height)
        }
        return CGSize(width: proposal.width ?? widest, height: y + lineHeight)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        var x = bounds.minX
        var y = bounds.minY
        var lineHeight: CGFloat = 0
        for subview in subviews {
            let size = subview.sizeThatFits(.unspecified)
            if x > bounds.minX && x + size.width > bounds.maxX {
                y += lineHeight + lineSpacing
                x = bounds.minX
                lineHeight = 0
            }
            subview.place(at: CGPoint(x: x, y: y), proposal: ProposedViewSize(size))
            x += size.width + spacing
            lineHeight = max(lineHeight, size.height)
        }
    }
}
