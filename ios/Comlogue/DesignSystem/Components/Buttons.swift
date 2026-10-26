import SwiftUI

struct PillButtonStyle: ButtonStyle {
    enum Kind { case primary, secondary, ghost, destructive, light }

    var kind: Kind = .primary
    var fullWidth: Bool = true

    func makeBody(configuration: Configuration) -> some View {
        StyledPill(configuration: configuration, kind: kind, fullWidth: fullWidth)
    }

    private struct StyledPill: View {
        let configuration: Configuration
        let kind: Kind
        let fullWidth: Bool
        @Environment(\.isEnabled) private var isEnabled

        var body: some View {
            configuration.label
                .font(.headlineRounded)
                .lineLimit(1)
                .minimumScaleFactor(0.85)
                .padding(.vertical, 16)
                .padding(.horizontal, 22)
                .frame(maxWidth: fullWidth ? .infinity : nil)
                .foregroundStyle(foreground)
                .background(background)
                .overlay(border)
                .clipShape(Capsule())
                .opacity(isEnabled ? 1 : 0.45)
                .scaleEffect(configuration.isPressed ? 0.97 : 1)
                .animation(.spring(response: 0.25, dampingFraction: 0.8), value: configuration.isPressed)
                .contentShape(Capsule())
        }

        private var foreground: Color {
            switch kind {
            case .primary, .destructive: return .white
            case .secondary: return Theme.ink
            case .ghost: return Theme.indigo
            case .light: return Color(rgb: 0x2A2470)
            }
        }

        @ViewBuilder private var background: some View {
            switch kind {
            case .primary: Theme.aurora
            case .secondary: Theme.surface
            case .ghost: Color.clear
            case .destructive: Theme.danger
            case .light: Color.white
            }
        }

        @ViewBuilder private var border: some View {
            if kind == .secondary {
                Capsule().strokeBorder(Theme.stroke, lineWidth: 1)
            }
        }
    }
}

extension ButtonStyle where Self == PillButtonStyle {
    static var primaryPill: PillButtonStyle { PillButtonStyle(kind: .primary) }
    static var secondaryPill: PillButtonStyle { PillButtonStyle(kind: .secondary) }
    static var ghostPill: PillButtonStyle { PillButtonStyle(kind: .ghost) }
    static var destructivePill: PillButtonStyle { PillButtonStyle(kind: .destructive) }
    static var lightPill: PillButtonStyle { PillButtonStyle(kind: .light) }
    static func pill(_ kind: PillButtonStyle.Kind, fullWidth: Bool = true) -> PillButtonStyle {
        PillButtonStyle(kind: kind, fullWidth: fullWidth)
    }
}

/// Subtle press feedback for tappable cards.
struct PressableCardStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed ? 0.985 : 1)
            .opacity(configuration.isPressed ? 0.92 : 1)
            .animation(.spring(response: 0.25, dampingFraction: 0.85), value: configuration.isPressed)
    }
}

extension ButtonStyle where Self == PressableCardStyle {
    static var pressableCard: PressableCardStyle { PressableCardStyle() }
}

/// A round icon button used for close / back / replay.
struct CircleIconButton: View {
    let systemName: String
    var size: CGFloat = 36
    var tint: Color = Theme.ink
    var background: Color = Theme.surfaceMuted
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Image(systemName: systemName)
                .font(.system(size: size * 0.42, weight: .semibold))
                .foregroundStyle(tint)
                .frame(width: size, height: size)
                .background(background, in: Circle())
        }
        .buttonStyle(.plain)
    }
}
