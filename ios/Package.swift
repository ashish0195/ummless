// swift-tools-version:5.10
// Builds the platform-independent core of the app (models, API client, audio math) so it can be unit-tested
// on macOS and Linux without Xcode. The app target compiles the same files directly.
import PackageDescription

let package = Package(
    name: "ComlogueCore",
    platforms: [.macOS(.v13), .iOS(.v17)],
    products: [
        .library(name: "ComlogueCore", targets: ["ComlogueCore"]),
    ],
    targets: [
        .target(name: "ComlogueCore", path: "Comlogue/Core"),
        // Files compiled into both the app and the widget extension.
        .target(name: "ComlogueShared", path: "Shared"),
        .testTarget(name: "ComlogueCoreTests", dependencies: ["ComlogueCore", "ComlogueShared"], path: "CoreTests"),
    ]
)
