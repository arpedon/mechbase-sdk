import Foundation
import Mechbase

@main
struct RunSurvey {
    static func main() async {
        let env = ProcessInfo.processInfo.environment
        guard let token = env["MECHBASE_TOKEN"], let routeUUID = env["ROUTE_UUID"] else {
            FileHandle.standardError.write(Data("MECHBASE_TOKEN and ROUTE_UUID required\n".utf8))
            exit(1)
        }
        let baseURL = URL(string: env["MECHBASE_BASE_URL"] ?? "https://mechbase.arpedon.com")!

        let client = MechbaseClient(token: token, baseURL: baseURL)
        do {
            let me = try await client.me()
            let installation = client.forInstallation(id: me.currentInstallationId)
            let execution = try await installation.routes.start(routeUUID: routeUUID)
            print("started execution \(execution.uuid)")

            try await execution.addFieldItem(
                label: "Oil leak under pump",
                itemType: "pass_fail",
                data: ["passed": false, "severity": "major"],
                zoneId: nil,
                assetId: nil
            )
            print("added field item")

            let completed = try await execution.complete()
            print("completed execution status=\(completed.status)")
        } catch {
            FileHandle.standardError.write(Data("error: \(error)\n".utf8))
            exit(1)
        }
    }
}
