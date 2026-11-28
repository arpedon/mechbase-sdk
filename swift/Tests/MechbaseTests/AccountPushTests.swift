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

    func testMeDecodesNamesAndUnitChoices() async throws {
        ParityMock.reset(reply: #"{"user":{"id":1,"username":"u","full_name":"Ada L","first_name":"Ada","last_name":"L","email":"u@x"},"unit_prefs":{"acceleration":"g","velocity":"mm/s","temperature":"°C","pressure":"bar","frequency":"Hz"},"unit_choices":{"acceleration":[{"value":"g","label":"g"}],"velocity":[{"value":"in/s","label":"in/s"}],"temperature":[{"value":"°F","label":"°F"}],"pressure":[{"value":"psi","label":"psi"}],"frequency":[{"value":"Hz","label":"Hz"},{"value":"CPM","label":"CPM"}]},"installations":[]}"#)
        let me = try await client.me()
        XCTAssertEqual(me.user.firstName, "Ada")
        XCTAssertEqual(me.user.lastName, "L")
        XCTAssertEqual(me.unitChoices?.frequency.map(\.value), ["Hz", "CPM"])
        XCTAssertEqual(me.unitChoices?.temperature.first?.label, "°F")
    }

    func testMeWithoutNamesOrChoicesFromAnOlderServer() async throws {
        ParityMock.reset(reply: #"{"user":{"id":1,"username":"u","full_name":"U","email":"u@x"},"installations":[]}"#)
        let me = try await client.me()
        XCTAssertEqual(me.user.firstName, "")
        XCTAssertNil(me.unitChoices)
    }

    func testWebSession() async throws {
        reply("WebSessionOut")
        let s = try await client.webSession(next: "/2012/assets/5/")
        XCTAssertEqual(method, "POST")
        XCTAssertEqual(url, "https://x.test/api/auth/web-session")
        XCTAssertEqual(json as? [String: String], ["next": "/2012/assets/5/"])
        XCTAssertEqual(s.url.absoluteString, "https://x.test/auth/magic/abc/")
        XCTAssertEqual(s.expiresAt, "2026-11-27T10:00:00Z")
    }

    func testWebSessionErrors() async {
        ParityMock.reset(status: 422, reply: #"{"detail":"next: must be a path on this site or a device tunnel you can open."}"#)
        await expectError({ _ = try await self.client.webSession(next: "//evil") }) {
            if case .validation(let m) = $0 { return m.contains("next:") }; return false
        }
        ParityMock.reset(status: 403, reply: #"{"detail":"This token cannot open a web session."}"#)
        await expectError({ _ = try await self.client.webSession(next: "/") }) {
            if case .auth(let m) = $0 { return m.contains("web session") }; return false
        }
    }
}
