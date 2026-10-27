import Foundation
import Observation
import StoreKit

/// StoreKit 2 purchases. Verified transactions are forwarded to the backend, which owns the entitlement.
@MainActor
@Observable
final class StoreManager {
    private(set) var products: [Product] = []
    private(set) var isLoading = false
    private(set) var isPurchasing = false
    var lastError: String?

    /// Sends a verified transaction's JWS to the backend and returns the updated entitlement.
    var forwardTransaction: ((String) async -> Bool)?

    private var updatesTask: Task<Void, Never>?

    var monthly: Product? { products.first { $0.id.hasSuffix("monthly") } }
    var yearly: Product? { products.first { $0.id.hasSuffix("yearly") } }

    func load(productIds: [String]) async {
        guard products.isEmpty else { return }
        isLoading = true
        defer { isLoading = false }
        do {
            products = try await Product.products(for: productIds).sorted { $0.price < $1.price }
        } catch {
            lastError = "Purchases aren't available right now."
        }
    }

    /// Returns true when the purchase completed and the backend accepted it.
    func purchase(_ product: Product) async -> Bool {
        isPurchasing = true
        defer { isPurchasing = false }
        lastError = nil
        do {
            let result = try await product.purchase()
            switch result {
            case .success(let verification):
                return await handle(verification)
            case .userCancelled:
                return false
            case .pending:
                lastError = "Your purchase is waiting for approval."
                return false
            @unknown default:
                return false
            }
        } catch {
            lastError = "The purchase didn't go through. You haven't been charged."
            return false
        }
    }

    func restore() async {
        do {
            try await AppStore.sync()
            await syncCurrentEntitlements()
        } catch {
            lastError = "We couldn't restore purchases. Check that you're signed in to the App Store."
        }
    }

    /// Start at launch: StoreKit delivers renewals, Ask to Buy approvals and transactions left unfinished last time
    /// through `Transaction.updates`, once, right after the app starts.
    func startListening() {
        guard updatesTask == nil else { return }
        updatesTask = Task { [weak self] in
            for await update in Transaction.updates {
                _ = await self?.handle(update)
            }
        }
    }

    /// Hands the server any purchase it hasn't accepted yet (it was offline, or we weren't signed in).
    func retryUnfinished() async {
        for await transaction in Transaction.unfinished {
            _ = await handle(transaction)
        }
    }

    func syncCurrentEntitlements() async {
        for await entitlement in Transaction.currentEntitlements {
            _ = await handle(entitlement)
        }
    }

    private func handle(_ verification: VerificationResult<Transaction>) async -> Bool {
        switch verification {
        case .verified(let transaction):
            if transaction.revocationDate != nil {
                // Refunded or revoked: nothing to unlock.
                await transaction.finish()
                return false
            }
            // Finish only once the server has unlocked Pro. An unfinished transaction stays with StoreKit, which
            // offers it again (`Transaction.updates`, `retryUnfinished`), so a dropped connection never loses a purchase.
            guard await forwardTransaction?(verification.jwsRepresentation) ?? false else {
                lastError = "Your purchase went through, but we couldn't unlock Pro yet. We'll keep trying, or tap Restore purchases."
                return false
            }
            await transaction.finish()
            return true
        case .unverified:
            lastError = "We couldn't verify that purchase with the App Store."
            return false
        }
    }
}
