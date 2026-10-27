import Foundation
import Security

/// Where the backend lives. Defaults to the build setting `API_BASE_URL` (Info.plist `ComlogueAPIBaseURL`);
/// a developer override can be set in Settings → Developer (handy for testing on a device against a laptop).
enum AppConfig {
    private static let overrideKey = "comlogue.apiBaseURLOverride"

    static var defaultBaseURL: URL {
        if let raw = Bundle.main.object(forInfoDictionaryKey: "ComlogueAPIBaseURL") as? String,
           let url = URL(string: raw), url.scheme != nil {
            return url
        }
        return URL(string: "http://localhost:8000")!
    }

    static var baseURL: URL {
        if let raw = UserDefaults.standard.string(forKey: overrideKey), let url = URL(string: raw), url.scheme != nil {
            return url
        }
        return defaultBaseURL
    }

    static var baseURLOverride: String? {
        get { UserDefaults.standard.string(forKey: overrideKey) }
        set {
            if let newValue, !newValue.trimmingCharacters(in: .whitespaces).isEmpty {
                UserDefaults.standard.set(newValue.trimmingCharacters(in: .whitespaces), forKey: overrideKey)
            } else {
                UserDefaults.standard.removeObject(forKey: overrideKey)
            }
        }
    }

    /// Which APNs environment this build's device token belongs to.
    static var pushEnvironment: String {
        #if DEBUG
        return "sandbox"
        #else
        return "production"
        #endif
    }

    static var appVersion: String {
        let version = Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "1.0"
        let build = Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "1"
        return "\(version) (\(build))"
    }
}

/// Minimal Keychain wrapper for the device identity and API token.
enum KeychainStore {
    private static let service = "com.comlogue.app"

    static func string(for key: String) -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: key,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var item: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &item) == errSecSuccess, let data = item as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }

    static func set(_ value: String?, for key: String) {
        let base: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: key,
        ]
        SecItemDelete(base as CFDictionary)
        guard let value else { return }
        var attributes = base
        attributes[kSecValueData as String] = Data(value.utf8)
        attributes[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        SecItemAdd(attributes as CFDictionary, nil)
    }
}

/// Stable anonymous identity for this install, used to obtain an API token.
enum DeviceIdentity {
    private static let deviceKey = "device_id"
    private static let tokenKey = "api_token"

    static var deviceId: String {
        if let existing = KeychainStore.string(for: deviceKey) { return existing }
        let fresh = UUID().uuidString
        KeychainStore.set(fresh, for: deviceKey)
        return fresh
    }

    static var token: String? {
        get { KeychainStore.string(for: tokenKey) }
        set { KeychainStore.set(newValue, for: tokenKey) }
    }

    /// Forget this device's identity (after account deletion) so the next launch starts fresh.
    static func reset() {
        KeychainStore.set(nil, for: tokenKey)
        KeychainStore.set(nil, for: deviceKey)
    }
}
