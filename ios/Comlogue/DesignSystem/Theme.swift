import SwiftUI
import UIKit

// Comlogue's visual language: calm surfaces, an "aurora" gradient for moments of energy, a colour per
// communication dimension, and rounded type that feels like a friendly voice rather than a test.

extension UIColor {
    convenience init(rgb: UInt32, alpha: CGFloat = 1) {
        self.init(
            red: CGFloat((rgb >> 16) & 0xFF) / 255,
            green: CGFloat((rgb >> 8) & 0xFF) / 255,
            blue: CGFloat(rgb & 0xFF) / 255,
            alpha: alpha
        )
    }
}

extension Color {
    /// A colour that adapts to light and dark mode.
    init(light: UInt32, dark: UInt32) {
        self.init(uiColor: UIColor { traits in
            traits.userInterfaceStyle == .dark ? UIColor(rgb: dark) : UIColor(rgb: light)
        })
    }

    init(rgb: UInt32) {
        self.init(uiColor: UIColor(rgb: rgb))
    }

    /// "#RRGGBB" from the API, with a fallback when the string is malformed.
    init(hex: String, fallback: Color = Theme.indigo) {
        if let rgb = Formatting.rgb(fromHex: hex) {
            self.init(red: rgb.red, green: rgb.green, blue: rgb.blue)
        } else {
            self = fallback
        }
    }
}

enum Theme {
    // Surfaces
    static let background = Color(light: 0xF6F5FB, dark: 0x0B0B12)
    static let surface = Color(light: 0xFFFFFF, dark: 0x161622)
    static let surfaceMuted = Color(light: 0xEFEEF7, dark: 0x202030)
    static let stroke = Color(light: 0xE3E2EE, dark: 0x2C2C3D)

    // Text
    static let ink = Color(light: 0x111325, dark: 0xF3F3FA)
    static let inkSecondary = Color(light: 0x575B73, dark: 0xA9ACC4)
    static let inkTertiary = Color(light: 0x8C90A8, dark: 0x6F7391)

    // Brand and semantic colours
    static let indigo = Color(light: 0x5146E6, dark: 0x8C84FF)
    static let violet = Color(light: 0x8B5CF6, dark: 0xA88BFF)
    static let coral = Color(light: 0xF2605A, dark: 0xFF8A7F)
    static let mint = Color(light: 0x0FA97A, dark: 0x3DDBA6)
    static let amber = Color(light: 0xE08E00, dark: 0xFFC145)
    static let danger = Color(light: 0xE5484D, dark: 0xFF6369)
    static let recording = Color(light: 0xFF3B30, dark: 0xFF453A)

    static let auroraColors: [Color] = [Color(rgb: 0x4F46E5), Color(rgb: 0x8B5CF6), Color(rgb: 0xF2708A)]
    static let aurora = LinearGradient(colors: auroraColors, startPoint: .topLeading, endPoint: .bottomTrailing)
    static let auroraSoft = LinearGradient(
        colors: [Color(rgb: 0x4F46E5).opacity(0.14), Color(rgb: 0x8B5CF6).opacity(0.12), Color(rgb: 0xF2708A).opacity(0.12)],
        startPoint: .topLeading, endPoint: .bottomTrailing
    )

    static func color(for dimension: DimensionId) -> Color {
        Color(hex: DimensionCatalog.colorHex(dimension))
    }

    // Layout
    static let radius: CGFloat = 24
    static let radiusSmall: CGFloat = 16
    static let gutter: CGFloat = 20
    static let spacing: CGFloat = 16
}

extension Font {
    static let displayLarge = Font.system(.largeTitle, design: .rounded, weight: .bold)
    static let display = Font.system(.title, design: .rounded, weight: .bold)
    static let titleRounded = Font.system(.title2, design: .rounded, weight: .bold)
    static let title3Rounded = Font.system(.title3, design: .rounded, weight: .semibold)
    static let headlineRounded = Font.system(.headline, design: .rounded, weight: .semibold)
    static let eyebrow = Font.system(.caption, design: .rounded, weight: .bold)
    static let metric = Font.system(.title, design: .rounded, weight: .bold).monospacedDigit()
    static let metricSmall = Font.system(.headline, design: .rounded, weight: .bold).monospacedDigit()
}

// MARK: - Common modifiers

struct CardModifier: ViewModifier {
    var padding: CGFloat = 18
    var background: Color = Theme.surface

    func body(content: Content) -> some View {
        content
            .padding(padding)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(background, in: RoundedRectangle(cornerRadius: Theme.radius, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: Theme.radius, style: .continuous)
                    .strokeBorder(Theme.stroke.opacity(0.7), lineWidth: 0.5)
            )
            .shadow(color: Color.black.opacity(0.04), radius: 12, x: 0, y: 6)
    }
}

extension View {
    func card(padding: CGFloat = 18, background: Color = Theme.surface) -> some View {
        modifier(CardModifier(padding: padding, background: background))
    }

    /// Standard screen background that extends under the safe areas.
    func screenBackground() -> some View {
        background(Theme.background.ignoresSafeArea())
    }

    /// Hides a view without removing it from layout.
    @ViewBuilder func isHidden(_ shouldHide: Bool) -> some View {
        if shouldHide { self.hidden() } else { self }
    }
}

/// Small label used above titles ("Week 2 · Structure"). Sentence case: capitals shout, and a calm screen reads faster.
struct Eyebrow: View {
    let text: String
    var color: Color = Theme.inkSecondary

    init(_ text: String, color: Color = Theme.inkSecondary) {
        self.text = text
        self.color = color
    }

    var body: some View {
        Text(text)
            .font(.subheadline.weight(.semibold))
            .foregroundStyle(color)
    }
}
