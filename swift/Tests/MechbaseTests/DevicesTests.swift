import XCTest
@testable import Mechbase

/// Devices, sources and staff tunnels: method, path, body, decode.
final class DevicesTests: XCTestCase {
    private func client() -> MechbaseClient {
        let cfg = URLSessionConfiguration.ephemeral
        cfg.protocolClasses = [CaptureMock.self]
        return MechbaseClient(token: "t", baseURL: URL(string: "https://x.test")!, session: URLSession(configuration: cfg))
    }
    private var inst: Installation { client().forInstallation(id: 7) }
    private let base = "https://x.test/api/installations/7"
    private let node = "6f1e2d3c-4b5a-4968-8776-5a4b3c2d1e0f"
    private let group = "6f1c0000-0000-4000-8000-000000000001"
    private let src = "6f1c0000-0000-4000-8000-000000000002"

    private var device: String { #"{"node_uuid":"\#(node)","name":"Node A","is_online":true,"last_seen_at":null,"claimed_at":null,"health":{"cpu_usage":95},"health_warnings":["CPU 95%"],"health_url":null,"groups":[{"uuid":"\#(group)","name":"hat","hardware_type":"hat","hardware_config":{},"interval":600,"sample_rate":null,"samples":null,"channels":[{"uuid":"m1","channel":3,"point_id":1,"point_name":"DE","asset_id":1,"asset_name":"Pump","sensor":"accelerometer","last_seen_at":null,"stale_since":null,"state":"waiting"}]}],"tunnels":[{"uuid":"t1","name":"logo","label":"LOGO","kind":"http","staff_only":false,"web_url":"https://x/t1/","local_port":null,"visitor_url":null}]}"# }
    private var source: String { #"{"uuid":"\#(src)","source_type":"maintnode","device_id":"\#(node)","device_name":"Node A","group":{"uuid":"\#(group)","name":"hat","hardware_type":"hat"},"channel":3,"sensor":"accelerometer","sensor_config":{"sensitivity":100},"is_active":true,"last_seen_at":null,"stale_since":null}"# }

    func testDevicesListDecodes() async throws {
        CaptureMock.reply = "[\(device)]"
        let d = try await inst.devices.list()[0]
        XCTAssertEqual(CaptureMock.lastPath, "\(base)/devices")
        XCTAssertEqual(d.groups[0].channels[0].state, "waiting")
        XCTAssertEqual(d.tunnels[0].webUrl, "https://x/t1/")
        XCTAssertNil(d.healthUrl)
    }

    func testRenameAndUpdateGroup() async throws {
        CaptureMock.reply = device
        _ = try await inst.devices.rename(nodeUuid: node, name: "Boiler")
        XCTAssertEqual(CaptureMock.lastMethod, "PATCH")
        XCTAssertEqual(CaptureMock.lastPath, "\(base)/devices/\(node)")
        XCTAssertEqual(CaptureMock.lastJSON?["name"] as? String, "Boiler")
        _ = try await inst.devices.updateGroup(nodeUuid: node, groupUuid: group, fields: ["interval": .int(120)])
        XCTAssertEqual(CaptureMock.lastPath, "\(base)/devices/\(node)/groups/\(group)")
        XCTAssertEqual(CaptureMock.lastJSON?["interval"] as? Int, 120)
    }

    func testSourcesCRUD() async throws {
        CaptureMock.reply = "[\(source)]"
        let l = try await inst.sources.list(pointId: 1)
        XCTAssertEqual(CaptureMock.lastPath, "\(base)/measurement-points/1/sources")
        XCTAssertEqual(l[0].group?.name, "hat")
        CaptureMock.reply = source
        _ = try await inst.sources.create(pointId: 1, fields: ["source_type": .string("mqtt"), "mqtt_device_id": .string("SN-1")])
        XCTAssertEqual(CaptureMock.lastMethod, "POST")
        XCTAssertEqual(CaptureMock.lastJSON?["mqtt_device_id"] as? String, "SN-1")
        _ = try await inst.sources.update(pointId: 1, uuid: src, fields: ["sensitivity": .int(50)])
        XCTAssertEqual(CaptureMock.lastPath, "\(base)/measurement-points/1/sources/\(src)")
        CaptureMock.reply = "{}"
        try await inst.sources.delete(pointId: 1, uuid: src)
        XCTAssertEqual(CaptureMock.lastMethod, "DELETE")
        do { try await inst.sources.delete(pointId: 1, uuid: "../x"); XCTFail("want validation error") } catch {}
    }

    func testStaffTunnelsAndVisitorFile() async throws {
        CaptureMock.reply = #"[{"uuid":"\#(src)","name":"ssh","label":"SSH","kind":"stcp","staff_only":true,"web_url":null,"local_port":22,"visitor_url":"https://x/v","installation_id":7,"installation_name":"Plant","node_uuid":"\#(node)","device_name":"Node A"}]"#
        let t = try await client().tunnels()[0]
        XCTAssertEqual(CaptureMock.lastPath, "https://x.test/api/tunnels")
        XCTAssertEqual(t.localPort, 22)
        XCTAssertEqual(t.installationName, "Plant")
        CaptureMock.reply = "serverAddr = \"frp\"\n"
        let data = try await client().tunnelVisitorFile(uuid: src)
        XCTAssertEqual(CaptureMock.lastPath, "https://x.test/api/tunnels/\(src)/visitor.toml")
        XCTAssertEqual(data, Data("serverAddr = \"frp\"\n".utf8))
    }
}
