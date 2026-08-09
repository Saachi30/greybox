// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "GreyboxMenuBar",
    platforms: [.macOS(.v13)],
    targets: [
        .executableTarget(
            name: "GreyboxMenuBar",
            path: "Sources/GreyboxMenuBar"
        )
    ]
)
