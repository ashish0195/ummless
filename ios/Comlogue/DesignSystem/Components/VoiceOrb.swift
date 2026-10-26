import SwiftUI

/// A softly morphing blob that represents a voice. It breathes when idle and swells with `level` (0…1)
/// while someone is speaking. Used for the AI partner and for the user's own microphone.
struct VoiceOrb: View {
    var level: Double = 0
    var colors: [Color] = Theme.auroraColors
    var isActive: Bool = true

    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        TimelineView(.animation(minimumInterval: 1.0 / 30.0, paused: reduceMotion || !isActive)) { context in
            let time = context.date.timeIntervalSinceReferenceDate
            ZStack {
                OrbShape(phase: time, level: level, lobes: 5, wobble: 0.05)
                    .fill(
                        AngularGradient(colors: colors + [colors.first ?? .white], center: .center,
                                        angle: .degrees(time * 25))
                    )
                    .blur(radius: 18)
                    .opacity(0.55)
                    .scaleEffect(1.08 + level * 0.12)
                OrbShape(phase: time * 1.3, level: level, lobes: 4, wobble: 0.07)
                    .fill(
                        RadialGradient(colors: [Color.white.opacity(0.9), colors.last ?? .white, colors.first ?? .white],
                                       center: UnitPoint(x: 0.35, y: 0.3), startRadius: 2, endRadius: 140)
                    )
                    .overlay(
                        OrbShape(phase: time * 0.8, level: level, lobes: 3, wobble: 0.05)
                            .stroke(Color.white.opacity(0.35), lineWidth: 1.5)
                            .blendMode(.plusLighter)
                    )
                    .shadow(color: (colors.first ?? .clear).opacity(0.35), radius: 24, x: 0, y: 12)
            }
            .animation(.spring(response: 0.25, dampingFraction: 0.75), value: level)
        }
        .accessibilityHidden(true)
    }
}

/// A circle whose radius is modulated by a few slow sine waves; `level` makes it swell and ripple.
struct OrbShape: Shape {
    var phase: Double
    var level: Double
    var lobes: Int
    var wobble: Double

    var animatableData: Double {
        get { level }
        set { level = newValue }
    }

    func path(in rect: CGRect) -> Path {
        let center = CGPoint(x: rect.midX, y: rect.midY)
        let base = min(rect.width, rect.height) / 2 * (0.78 + 0.16 * min(1, max(0, level)))
        let amplitude = base * (wobble + 0.10 * min(1, max(0, level)))
        let steps = 96
        var path = Path()
        for step in 0...steps {
            let angle = Double(step) / Double(steps) * 2 * .pi
            let ripple = sin(angle * Double(lobes) + phase * 1.7) * 0.6
                + sin(angle * Double(lobes + 2) - phase * 1.1) * 0.3
                + sin(angle * 2 + phase * 0.6) * 0.4
            let radius = base + amplitude * ripple
            let point = CGPoint(x: center.x + CGFloat(cos(angle)) * radius, y: center.y + CGFloat(sin(angle)) * radius)
            if step == 0 { path.move(to: point) } else { path.addLine(to: point) }
        }
        path.closeSubpath()
        return path
    }
}

extension VoiceOrb {
    /// Orb tinted with a single accent colour (e.g. the partner's colour).
    static func tinted(_ color: Color, level: Double, isActive: Bool = true) -> VoiceOrb {
        VoiceOrb(level: level, colors: [color, color.opacity(0.75), Theme.violet], isActive: isActive)
    }
}

#Preview {
    VoiceOrb(level: 0.4).frame(width: 220, height: 220).padding().screenBackground()
}
