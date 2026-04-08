// swift-tools-version:5.9
import PackageDescription

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
            path: "Sources/Mechbase"
        ),
        .testTarget(
            name: "MechbaseTests",
            dependencies: ["Mechbase"],
            path: "Tests/MechbaseTests"
        ),
        .executableTarget(
            name: "PushMeasurement",
            dependencies: ["Mechbase"],
            path: "Examples/PushMeasurement"
        ),
        .executableTarget(
            name: "RunSurvey",
            dependencies: ["Mechbase"],
            path: "Examples/RunSurvey"
        ),
    ]
)
