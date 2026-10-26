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

    private var pricing: Pricing? { app.meta?.pricing }
    private var store: StoreManager { app.store }

    var body: some View {
        VStack(spacing: 0) {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    VoiceOrb(level: 0.25, colors: [Color.white, Color(rgb: 0xC9C3FF), Color(rgb: 0xFFB4A8)])
                        .frame(width: 88, height: 88)
                        .frame(maxWidth: .infinity)
                        .padding(.top, 8)
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Keep the momentum").font(.display).foregroundStyle(.white)
                        Text("Your profile and first win are yours to keep. Pro turns them into steady, real-world progress.")
                            .font(.body)
                            .foregroundStyle(.white.opacity(0.88))
                    }
                    VStack(alignment: .leading, spacing: 12) {
                        feature("map.fill", "The full course for your goal", "Every mission, remix and real-life challenge")
                        feature("bubble.left.and.exclamationmark.bubble.right.fill", "Unlimited AI sparring", "Personas, custom scenarios, Brutal mode")
                        feature("calendar.badge.clock", "Event prep", "Rehearse your interview, pitch or hard talk")
                        feature("quote.bubble.fill", "Every talk to shadow", "Steal the style of great speakers")
                        feature("gift.fill", "Weekly reveal", "Before-and-after moments and your next focus")
                    }
                }
                .padding(Theme.gutter)
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
                Text(terms)
                    .font(.caption2)
                    .foregroundStyle(.white.opacity(0.75))
                    .multilineTextAlignment(.center)
                HStack(spacing: 18) {
                    Button("Restore purchases") { Task { await restore() } }
                    Link("Terms", destination: Brand.termsURL)
                    Link("Privacy", destination: Brand.privacyURL)
                }
                .font(.caption.weight(.semibold))
                .foregroundStyle(.white.opacity(0.9))
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
                price: store.yearly?.displayPrice ?? pricing.map { "$\(String(format: "%.2f", $0.yearlyUsd))" } ?? "",
                detail: "\(pricing?.trialDays ?? 7)-day free trial · best value",
                badge: yearlySavingPercent.map { "Save \($0)%" }
            ) { yearlySelected = true }
            planRow(
                selected: !yearlySelected,
                title: "Monthly",
                price: store.monthly?.displayPrice ?? pricing.map { "$\(String(format: "%.2f", $0.monthlyUsd))" } ?? "",
                detail: "Cancel anytime",
                badge: nil
            ) { yearlySelected = false }
        }
    }

    /// Yearly against twelve months of monthly, from the App Store prices when loaded, else the server's pricing.
    private var yearlySavingPercent: Int? {
        var monthlyPrice = pricing?.monthlyUsd
        var yearlyPrice = pricing?.yearlyUsd
        if let monthlyProduct = store.monthly, let yearlyProduct = store.yearly {
            monthlyPrice = NSDecimalNumber(decimal: monthlyProduct.price).doubleValue
            yearlyPrice = NSDecimalNumber(decimal: yearlyProduct.price).doubleValue
        }
        guard let monthly = monthlyPrice, let yearly = yearlyPrice, monthly > 0 else { return nil }
        let percent = Int(((1 - yearly / (monthly * 12)) * 100).rounded(.down))
        return percent > 0 ? percent : nil
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

    private func feature(_ icon: String, _ title: String, _ detail: String) -> some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: icon).font(.headline).foregroundStyle(.white).frame(width: 28)
            VStack(alignment: .leading, spacing: 2) {
                Text(title).font(.subheadline.weight(.semibold)).foregroundStyle(.white)
                Text(detail).font(.caption).foregroundStyle(.white.opacity(0.78))
            }
        }
    }

    private var ctaTitle: String {
        yearlySelected ? "Start \(pricing?.trialDays ?? 7)-day free trial" : "Subscribe monthly"
    }

    private var terms: String {
        let yearly = store.yearly?.displayPrice ?? pricing.map { "$\(String(format: "%.2f", $0.yearlyUsd))" } ?? "the yearly price"
        let monthly = store.monthly?.displayPrice ?? pricing.map { "$\(String(format: "%.2f", $0.monthlyUsd))" } ?? "the monthly price"
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
