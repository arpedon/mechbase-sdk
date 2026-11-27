import XCTest
@testable import Mechbase

final class CommissioningTests: ParityTestCase {
    func testLookupAndClaim() async throws {
        reply("DeviceLookupOut", nulls: true)
        let l = try await inst.devices.lookup(balenaUuid: u1)
        XCTAssertEqual(url, "\(base)/devices/lookup/\(u1)")
        XCTAssertEqual(l.state, "claim")
        XCTAssertNil(l.installationId)
        reply("DeviceOut", status: 201)
        let d = try await inst.devices.claim(balenaUuid: u1, name: "Boiler node")
        XCTAssertEqual(method, "POST")
        XCTAssertEqual(url, "\(base)/devices")
        XCTAssertEqual(json as? [String: String], ["balena_uuid": u1, "name": "Boiler node"])
        XCTAssertEqual(d.tokenPush?.state, "none")
        XCTAssertEqual(d.config?.isCurrent, true)
        XCTAssertEqual(d.hardware, .object(["k": .int(1)]))
        ParityMock.reset(status: 409, reply: #"{"detail":"Claimed by another installation."}"#)
        await expectError({ _ = try await self.inst.devices.claim(balenaUuid: self.u1) }) {
            if case .conflict = $0 { return true }; return false
        }
        await expectError({ _ = try await self.inst.devices.lookup(balenaUuid: "../x") }) {
            if case .validation = $0 { return true }; return false
        }
    }

    func testDeviceNullsAndOlderServer() async throws {
        reply("DeviceOut", nulls: true)
        let d = try await inst.devices.get(nodeUuid: u1)
        XCTAssertNil(d.hardware)
        XCTAssertNil(d.config?.appliedVersion)
        XCTAssertNil(d.config?.isCurrent)
        // A server without the commissioning fields still decodes.
        ParityMock.reset(reply: #"{"node_uuid":"\#(u1)","name":"n","is_online":false,"last_seen_at":null,"claimed_at":null,"health":{},"health_warnings":[],"health_url":null,"groups":[],"tunnels":[]}"#)
        let got = try await inst.devices.get(nodeUuid: u1).tokenPush
        XCTAssertNil(got)
    }

    func testCredentialsChannelsGroups() async throws {
        reply("DeviceOut", status: 202)
        _ = try await inst.devices.resendCredentials(nodeUuid: u1)
        XCTAssertEqual(method, "POST")
        XCTAssertEqual(url, "\(base)/devices/\(u1)/credentials")
        reply("GroupChannelsOut", list: true)
        let g = try await inst.devices.channels(nodeUuid: u1)
        XCTAssertEqual(url, "\(base)/devices/\(u1)/channels")
        XCTAssertEqual(g.first?.channels.first?.state, "ok")
        reply("GroupChannelsOut", nulls: true, list: true)
        let got = try await inst.devices.channels(nodeUuid: u1).first?.slots
        XCTAssertNil(got)
        reply("DeviceOut", status: 201)
        _ = try await inst.devices.createGroup(nodeUuid: u1, fields: ["group_name": .string("usb"), "hardware_type": .string("ul"),
                                                                      "hardware_address": .int(0)])
        XCTAssertEqual(url, "\(base)/devices/\(u1)/groups")
        XCTAssertEqual(json["hardware_type"] as? String, "ul")
    }
}
