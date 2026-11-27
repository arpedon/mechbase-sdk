import XCTest
@testable import Mechbase

final class AccountPushTests: ParityTestCase {
    func testMeDecodesIsStaffAndDefaultsFalse() async throws {
        reply("MeOut")
        let staff = try await client.me().user.isStaff
        XCTAssertTrue(staff)
        ParityMock.reset(reply: #"{"user":{"id":1,"username":"u","full_name":"U","email":"u@x"},"installations":[],"current_installation_id":null}"#)
        let got = try await client.me().user.isStaff
        XCTAssertFalse(got)
    }

    func testUpdateMeSendsOnlySetFields() async throws {
        reply("MeOut")
        _ = try await client.updateMe(MeInput(firstName: "Ann", unitPrefs: UnitPrefsInput(velocity: "in/s")))
        XCTAssertEqual(method, "PATCH")
        XCTAssertEqual(url, "https://x.test/api/me/")
        XCTAssertEqual(json["first_name"] as? String, "Ann")
        XCTAssertNil(json["last_name"])
        XCTAssertEqual(json["unit_prefs"] as? [String: String], ["velocity": "in/s"])
    }

    func testUpdateMeValidationError() async {
        ParityMock.reset(status: 422, reply: #"{"detail":"first_name: too long"}"#)
        await expectError({ _ = try await self.client.updateMe(MeInput(firstName: "x")) }) {
            if case .validation(let m) = $0 { return m.contains("first_name") }; return false
        }
    }

    func testRegisterPushDevice() async throws {
        reply("PushDeviceOut", status: 201)
        let d = try await client.registerPushDevice(platform: .apns, token: "ab12", appVersion: "2.1")
        XCTAssertEqual(method, "POST")
        XCTAssertEqual(url, "https://x.test/api/push/devices")
        XCTAssertEqual(json as? [String: String], ["platform": "apns", "token": "ab12", "app_version": "2.1"])
        XCTAssertEqual(d.platform, "apns")
    }

    func testDeletePushDeviceEscapesTokenAndMaps404() async throws {
        ParityMock.reset(status: 204, reply: "")
        try await client.deletePushDevice(token: "fcm:APA91/b")
        XCTAssertEqual(method, "DELETE")
        XCTAssertEqual(url, "https://x.test/api/push/devices/fcm%3AAPA91%2Fb")
        ParityMock.reset(status: 404, reply: #"{"detail":"Not found"}"#)
        await expectError({ try await self.client.deletePushDevice(token: "gone") }) {
            if case .notFound = $0 { return true }; return false
        }
    }
}
