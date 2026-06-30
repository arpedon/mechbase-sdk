// swift-tools-version:5.9
import PackageDescription

// SwiftPM requires the manifest at the repository root, so this lives here even
// though the Swift sources are under swift/. Consumers depend on it with:
//   .package(url: "https://github.com/arpedon/mechbase-sdk", from: "0.2.0")
//   .product(name: "Mechbase", package: "mechbase-sdk")
let package = Package(
    name: "Mechbase",
    platforms: [.iOS(.v16), .macOS(.v13)],
    products: [
        .library(name: "Mechbase", targets: ["Mechbase"]),
        .executable(name: "PushMeasurement", targets: ["PushMeasurement"]),
        .executable(name: "RunSurvey", targets: ["RunSurvey"]),
    ],
    targets: [
        .target(
            name: "Mechbase",
            path: "swift/Sources/Mechbase"
        ),
        .testTarget(
            name: "MechbaseTests",
            dependencies: ["Mechbase"],
            path: "swift/Tests/MechbaseTests"
        ),
        .executableTarget(
            name: "PushMeasurement",
            dependencies: ["Mechbase"],
            path: "swift/Examples/PushMeasurement"
        ),
        .executableTarget(
            name: "RunSurvey",
            dependencies: ["Mechbase"],
            path: "swift/Examples/RunSurvey"
        ),
    ]
)
