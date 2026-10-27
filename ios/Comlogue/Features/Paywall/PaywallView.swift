import StoreKit
import SwiftUI

/// Shown after the free baseline, one free task and the course preview. Price and terms are always shown
/// before purchase. Resolving a failed assessment is never paywalled.
struct PaywallView: View {
    @Environment(AppModel.self) private var app
    let onClose: () -> Void

    @State private var yearlySelected = true
    @State private var isPurchasing = false
    @State private var message: String?

    /// The caller's market price (₹ in India, $ in the US), used until the App Store's own prices load.
    private var pricing: Pricing? { app.pricing }
    private var store: StoreManager { app.store }

    var body: some View {
        VStack(spacing: 0) {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    VoiceOrb(level: 0.25, colors: [Color.white, Color(rgb: 0xC9C3FF), Color(rgb: 0xFFB4A8)])
                        .frame(width: 112, height: 112)
                        .frame(maxWidth: .infinity)
                        .padding(.top, 8)
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Keep the momentum").font(.display).foregroundStyle(.white)
                        Text("Turn your first win into real progress.")
                            .font(.body)
                            .foregroundStyle(.white.opacity(0.88))
                    }
                    VStack(alignment: .leading, spacing: 14) {
                        feature("map.fill", "The full course for your goal")
                        feature("bubble.left.and.bubble.right.fill", "Unlimited AI conversation practice")
                        feature("person.3.sequence.fill",
                                app.market == .in ? "Group discussions and interview panels" : "Panel interviews and group discussions")
                    }
                    .padding(.top, 6)
                    Label("Your daily 1-minute practice stays free, always.", systemImage: "heart.fill")
                        .font(.footnote.weight(.semibold))
                        .foregroundStyle(.white.opacity(0.85))
                        .padding(.top, 6)
                }
                .padding(Theme.gutter)
                .padding(.top, 16)
                .padding(.bottom, 24)
            }
            // Features that scroll under the plans fade out instead of being cut off mid-line.
            .mask {
                LinearGradient(stops: [.init(color: .black, location: 0), .init(color: .black, location: 0.9),
                                       .init(color: .clear, location: 1)],
                               startPoint: .top, endPoint: .bottom)
            }
            // Both plans and their prices stay on screen next to the button, whatever the screen size.
            VStack(spacing: 10) {
                planPicker
                    .padding(.top, 10)
                Button {
                    Task { await purchase() }
                } label: {
                    if isPurchasing || store.isPurchasing { ProgressView() } else { Text(ctaTitle) }
                }
                .buttonStyle(.lightPill)
                .disabled(isPurchasing)
                // Apple requires the renewal terms next to the button; they stay, just quietly.
                Text(terms)
                    .font(.caption2)
                    .foregroundStyle(.white.opacity(0.6))
                    .multilineTextAlignment(.center)
                HStack(spacing: 18) {
                    Button("Restore purchases") { Task { await restore() } }
                    Link("Terms", destination: Brand.termsURL)
                    Link("Privacy", destination: Brand.privacyURL)
                }
                .font(.caption.weight(.semibold))
                .foregroundStyle(.white.opacity(0.75))
                if let message {
                    Text(message).font(.footnote).foregroundStyle(.white).multilineTextAlignment(.center)
                }
                if store.products.isEmpty && !store.isLoading {
                    Button("Unlock Pro for testing") { Task { await devUnlock() } }
                        .font(.caption)
                        .foregroundStyle(.white.opacity(0.7))
                }
            }
            .padding(.horizontal, Theme.gutter)
            .padding(.bottom, 12)
        }
        .overlay(alignment: .topTrailing) {
            CircleIconButton(systemName: "xmark", tint: .white, background: .white.opacity(0.2), action: onClose)
                .padding(.trailing, Theme.gutter)
                .padding(.top, 8)
        }
        .background(
            LinearGradient(colors: [Color(rgb: 0x2A2470), Color(rgb: 0x5146E6), Color(rgb: 0x8B5CF6)],
                           startPoint: .top, endPoint: .bottom)
                .ignoresSafeArea()
        )
        .task {
            if let pricing {
                await store.load(productIds: [pricing.monthlyProductId, pricing.yearlyProductId])
            }
        }
    }

    private var planPicker: some View {
        VStack(spacing: 10) {
            planRow(
                selected: yearlySelected,
                title: "Yearly",
                price: store.yearly?.displayPrice ?? pricing?.yearlyLabel ?? "",
                detail: "\(pricing?.trialDays ?? 7)-day free trial",
                badge: yearlySavingPercent.map { "Save \($0)%" }
            ) { yearlySelected = true }
            planRow(
                selected: !yearlySelected,
                title: "Monthly",
                price: store.monthly?.displayPrice ?? pricing?.monthlyLabel ?? "",
                detail: "Cancel anytime",
                badge: nil
            ) { yearlySelected = false }
        }
    }

    /// Yearly against twelve months of monthly, from the App Store prices when loaded, else the server's pricing.
    private var yearlySavingPercent: Int? {
        if let monthlyProduct = store.monthly, let yearlyProduct = store.yearly {
            return HabitMath.yearlySavingPercent(monthly: NSDecimalNumber(decimal: monthlyProduct.price).doubleValue,
                                                 yearly: NSDecimalNumber(decimal: yearlyProduct.price).doubleValue)
        }
        guard let prices = pricing?.prices else { return nil }
        return HabitMath.yearlySavingPercent(monthly: prices.monthly, yearly: prices.yearly)
    }

    private func planRow(selected: Bool, title: String, price: String, detail: String, badge: String?, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack(spacing: 12) {
                Image(systemName: selected ? "largecircle.fill.circle" : "circle")
                    .font(.title3)
                    .foregroundStyle(.white)
                VStack(alignment: .leading, spacing: 2) {
                    HStack {
                        Text(title).font(.headlineRounded).foregroundStyle(.white)
                        if let badge {
                            Text(badge).font(.caption2.weight(.bold)).padding(.horizontal, 7).padding(.vertical, 3)
                                .background(Color.white, in: Capsule()).foregroundStyle(Color(rgb: 0x2A2470))
                        }
                    }
                    Text(detail).font(.caption).foregroundStyle(.white.opacity(0.8))
                }
                Spacer()
                Text(price).font(.headline).foregroundStyle(.white)
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 12)
            .background(Color.white.opacity(selected ? 0.22 : 0.1), in: RoundedRectangle(cornerRadius: 18, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 18, style: .continuous).strokeBorder(Color.white.opacity(selected ? 0.9 : 0.25), lineWidth: 1.5))
        }
        .buttonStyle(.plain)
    }

    private func feature(_ icon: String, _ title: String) -> some View {
        HStack(spacing: 14) {
            Image(systemName: icon)
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(.white)
                .frame(width: 36, height: 36)
                .background(Color.white.opacity(0.16), in: Circle())
            Text(title).font(.headlineRounded).foregroundStyle(.white)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    private var ctaTitle: String {
        yearlySelected ? "Start \(pricing?.trialDays ?? 7)-day free trial" : "Subscribe monthly"
    }

    private var terms: String {
        let yearly = store.yearly?.displayPrice ?? pricing?.yearlyLabel ?? "the yearly price"
        let monthly = store.monthly?.displayPrice ?? pricing?.monthlyLabel ?? "the monthly price"
        if yearlySelected {
            return "Free for \(pricing?.trialDays ?? 7) days, then \(yearly)/year. Renews automatically unless cancelled at least 24 hours before the end of the period. Cancel anytime in Settings."
        }
        return "\(monthly)/month. Renews automatically unless cancelled at least 24 hours before the end of the period. Cancel anytime in Settings."
    }

    private func purchase() async {
        message = nil
        guard let product = yearlySelected ? store.yearly : store.monthly else {
            message = "Purchases aren't available in this build yet."
            return
        }
        isPurchasing = true
        defer { isPurchasing = false }
        if await store.purchase(product) {
            Haptics.success()
            app.showToast("Welcome to Pro")
            onClose()
        } else if let error = store.lastError {
            message = error
        }
    }

    private func restore() async {
        await store.restore()
        await app.refreshMe()
        if app.isPro {
            app.showToast("Purchases restored")
            onClose()
        } else {
            message = store.lastError ?? "No active subscription found."
        }
    }

    private func devUnlock() async {
        if await app.devGrantPro() {
            app.showToast("Pro unlocked (testing)")
            onClose()
        } else {
            message = "Test unlocks are disabled on this server."
        }
    }
}
