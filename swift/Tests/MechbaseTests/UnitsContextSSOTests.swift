import XCTest
@testable import Mechbase

/// Unit prefs on `me`, display units on points, point context, and the
/// Microsoft sign-in (PKCE + code exchange) calls.
final class UnitsContextSSOTests: XCTestCase {
    private let base = URL(string: "https://example.test")!
    private var session: URLSession {
        let cfg = URLSessionConfiguration.ephemeral
        cfg.protocolClasses = [MockURLProtocol.self]
        return URLSession(configuration: cfg)
    }
    private var client: MechbaseClient { MechbaseClient(token: "tok", baseURL: base, session: session) }
    private var auth: MechbaseAuth { MechbaseAuth(baseURL: base, session: session) }

    override func tearDown() { MockURLProtocol.handler = nil; super.tearDown() }

    private func reply(_ body: String, status: Int = 200, capture: ((URLRequest, Data) -> Void)? = nil) {
        MockURLProtocol.handler = { req in
            capture?(req, req.httpBody ?? req.httpBodyStream.map(Self.read) ?? Data())
            return (status, Data(body.utf8))
        }
    }

    private static func read(_ s: InputStream) -> Data {
        s.open(); defer { s.close() }
        var out = Data(); var buf = [UInt8](repeating: 0, count: 4096)
        while s.hasBytesAvailable { let n = s.read(&buf, maxLength: buf.count); if n <= 0 { break }; out.append(buf, count: n) }
        return out
    }

    // MARK: - me.unit_prefs

    private let user = #""user":{"id":1,"username":"u","full_name":"U","email":"u@x.io"},"installations":[],"current_installation_id":null"#

    func testMeDecodesUnitPrefs() async throws {
        reply("{\(user),\"unit_prefs\":{\"acceleration\":\"g\",\"velocity\":\"in/s\",\"temperature\":\"°F\",\"pressure\":\"psi\",\"frequency\":\"CPM\"}}")
        let me = try await client.me()
        XCTAssertEqual(me.unitPrefs?.velocity, "in/s")
        XCTAssertEqual(me.unitPrefs?.temperature, "°F")
        XCTAssertEqual(me.unitPrefs?.frequency, "CPM")
    }

    func testMeWithoutUnitPrefsDecodesNil() async throws {
        reply("{\(user)}")
        let me = try await client.me()
        XCTAssertNil(me.unitPrefs)
        XCTAssertNil(me.currentInstallationId)
    }

    // MARK: - point.display_units

    private let point = #""uuid":"p","point_id":5,"name":"DE","asset_id":3,"transducer_type":"temp","measurement_unit_code":"c","location":"","status":1"#

    func testPointDecodesDisplayUnitsAndConverts() async throws {
        reply("{\(point),\"display_units\":{\"value\":{\"native\":\"°C\",\"unit\":\"°F\",\"scale\":1.8,\"offset\":32.0}}}")
        let p = try await client.forInstallation(id: 7).measurementPoints.get(id: 5)
        let du = try XCTUnwrap(p.displayUnits["value"])
        XCTAssertEqual(du, DisplayUnit(native: "°C", unit: "°F", scale: 1.8, offset: 32))
        XCTAssertEqual(du.convert(100), 212, accuracy: 1e-9)
    }

    func testPointWithoutDisplayUnitsIsEmpty() async throws {
        reply("{\(point)}")
        let p = try await client.forInstallation(id: 7).measurementPoints.get(id: 5)
        XCTAssertEqual(p.displayUnits, [:])
    }

    // MARK: - context

    func testContextDecodesFullBody() async throws {
        var path: String?
        reply(#"{"data_key":"rms","unit":"mm/s","running":true,"running_at":"2026-11-16T09:12:00Z","stale_since":"2026-11-15T00:00:00Z","limits":{"minor":4.5,"major":7.1},"week":[{"t":"2026-11-09T12:00:00Z","v":2.31},{"t":"2026-11-09T18:00:00Z","v":2.5}]}"#) { req, _ in
            path = req.url?.path
        }
        let ctx = try await client.forInstallation(id: 7).measurementPoints.context(pointId: 5)
        XCTAssertEqual(path, "/api/installations/7/measurement-points/5/context")
        XCTAssertEqual(ctx.dataKey, "rms")
        XCTAssertEqual(ctx.unit, "mm/s")
        XCTAssertEqual(ctx.running, true)
        XCTAssertEqual(ctx.runningAt, "2026-11-16T09:12:00Z")
        XCTAssertEqual(ctx.staleSince, "2026-11-15T00:00:00Z")
        XCTAssertEqual(ctx.limits?.minor, 4.5)
        XCTAssertEqual(ctx.limits?.major, 7.1)
        XCTAssertEqual(ctx.week, [TrendBin(t: "2026-11-09T12:00:00Z", v: 2.31), TrendBin(t: "2026-11-09T18:00:00Z", v: 2.5)])
    }

    func testContextDecodesNulls() async throws {
        reply(#"{"data_key":"value","unit":"°C","running":null,"running_at":null,"stale_since":null,"limits":null,"week":[]}"#)
        let ctx = try await client.forInstallation(id: 7).measurementPoints.context(pointId: 5)
        XCTAssertNil(ctx.running)
        XCTAssertNil(ctx.runningAt)
        XCTAssertNil(ctx.staleSince)
        XCTAssertNil(ctx.limits)
        XCTAssertEqual(ctx.week, [])
    }

    // MARK: - PKCE

    func testPKCEKnownAnswerRFC7636() {
        XCTAssertEqual(PKCE.challenge(for: "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"),
                       "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM")
    }

    func testPKCEGenerate() {
        let a = PKCE.generate(), b = PKCE.generate()
        XCTAssertEqual(a.verifier.count, 43)
        XCTAssertEqual(a.challenge.count, 43)
        XCTAssertNil(a.verifier.rangeOfCharacter(from: CharacterSet(charactersIn: "+/=")))
        XCTAssertEqual(a.challenge, PKCE.challenge(for: a.verifier))
        XCTAssertNotEqual(a.verifier, b.verifier)
    }

    // MARK: - SSO

    func testStartURLEncoding() {
        XCTAssertEqual(auth.ssoStartURL(codeChallenge: "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM", loginHint: "a+b@x.io").absoluteString,
                       "https://example.test/sso/native/start/?code_challenge=E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM&code_challenge_method=S256&login_hint=a%2Bb%40x.io")
        XCTAssertEqual(auth.ssoStartURL(codeChallenge: "c").absoluteString,
                       "https://example.test/sso/native/start/?code_challenge=c&code_challenge_method=S256")
    }

    func testExchangeSendsBodyAndReturnsToken() async throws {
        var seen: (URLRequest, Data)?
        reply(#"{"token":"tok-123"}"#) { seen = ($0, $1) }
        let token = try await auth.exchangeSSOCode(code: "c0de", codeVerifier: "v3r", deviceId: "dev-1")
        XCTAssertEqual(token, "tok-123")
        let (req, body) = try XCTUnwrap(seen)
        XCTAssertEqual(req.httpMethod, "POST")
        XCTAssertEqual(req.url?.absoluteString, "https://example.test/api/auth/sso/exchange")
        XCTAssertNil(req.value(forHTTPHeaderField: "Authorization"))
        let json = try XCTUnwrap(JSONSerialization.jsonObject(with: body) as? [String: String])
        XCTAssertEqual(json, ["code": "c0de", "code_verifier": "v3r", "device_id": "dev-1"])
    }

    func testExchange400SurfacesServerMessageAsAuth() async {
        reply(#"{"error":"Microsoft sign-in expired. Try again."}"#, status: 400)
        do {
            _ = try await auth.exchangeSSOCode(code: "used", codeVerifier: "v")
            XCTFail("expected throw")
        } catch MechbaseError.auth(let message) {
            XCTAssertTrue(message.contains("Microsoft sign-in expired. Try again."), message)
        } catch {
            XCTFail("unexpected \(error)")
        }
    }

    func testSSOCheckTrueAndEncodesEmail() async {
        var url: String?
        reply(#"{"sso":true}"#) { req, _ in url = req.url?.absoluteString }
        let sso = await auth.ssoCheck(email: "a+b@x.io")
        XCTAssertTrue(sso)
        XCTAssertEqual(url, "https://example.test/sso/check/?email=a%2Bb%40x.io")
    }

    func testSSOCheckFalseOnError() async {
        reply("oops", status: 500)
        let onServerError = await auth.ssoCheck(email: "a@x.io")
        XCTAssertFalse(onServerError)
        MockURLProtocol.handler = nil  // transport failure
        let onTransportError = await auth.ssoCheck(email: "a@x.io")
        XCTAssertFalse(onTransportError)
    }
}
