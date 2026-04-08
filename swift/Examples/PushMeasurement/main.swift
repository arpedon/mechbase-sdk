import Foundation
import Mechbase

@main
struct PushMeasurement {
    static func main() async {
        let env = ProcessInfo.processInfo.environment
        guard let token = env["MECHBASE_TOKEN"] else {
            FileHandle.standardError.write(Data("MECHBASE_TOKEN not set\n".utf8))
            exit(1)
        }
        let baseURL = env["MECHBASE_BASE_URL"].flatMap(URL.init(string:)) ?? MechbaseClient.defaultBaseURL
        let pointId = Int(env["POINT_ID"] ?? "1") ?? 1

        let client = MechbaseClient(token: token, baseURL: baseURL)
        do {
            let me = try await client.me()
            let installation = client.forInstallation(id: me.currentInstallationId)
            let measurement = try await installation.measurements.create(
                pointId: pointId,
                data: ["rms": 2.3, "peak": 4.1],
                notes: "from PushMeasurement example"
            )
            print("created measurement \(measurement.uuid) seq=\(measurement.pointSequence)")
        } catch {
            FileHandle.standardError.write(Data("error: \(error)\n".utf8))
            exit(1)
        }
    }
}
