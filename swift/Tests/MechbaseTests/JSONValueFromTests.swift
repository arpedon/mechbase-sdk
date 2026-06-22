import XCTest
@testable import Mechbase

/// Regression tests for `JSONValue.from(_:)` numeric/bool disambiguation.
///
/// The original `wrap(_:)` tested `case let b as Bool` BEFORE `Int`/`Double`.
/// An `NSNumber` whose value is 0 or 1 (the common shape produced by
/// `JSONSerialization` for integer-valued numeric readings) bridges to `Bool`
/// via `as? Bool`, so a numerical reading of `1.0`/`0.0` would be wrapped as
/// `.bool(true)`/`.bool(false)` and serialized to the server as `{"value":true}`
/// — corrupting the measurement and disabling alarm evaluation. These tests pin
/// the corrected behavior: real numeric values stay numeric, real booleans stay
/// boolean.
final class JSONValueFromTests: XCTestCase {

    func testNumericOneIsNotCoercedToBool() {
        // A reading of 1 (e.g. 1 bar, 1 mA) round-tripped through
        // JSONSerialization produces an NSNumber that bridges to Bool.
        let obj = (try? JSONSerialization.jsonObject(with: Data(#"{"value":1}"#.utf8))) as! [String: Any]
        let v = JSONValue.from(obj)
        guard case let .object(o) = v else { return XCTFail("expected object") }
        XCTAssertEqual(o["value"], .int(1), "1 must stay an int, not become bool(true)")
    }

    func testNumericZeroIsNotCoercedToBool() {
        let obj = (try? JSONSerialization.jsonObject(with: Data(#"{"value":0}"#.utf8))) as! [String: Any]
        let v = JSONValue.from(obj)
        guard case let .object(o) = v else { return XCTFail("expected object") }
        XCTAssertEqual(o["value"], .int(0), "0 must stay an int, not become bool(false)")
    }

    func testDoubleOneFromSwiftDoubleStaysNumeric() {
        // The literal path the iOS app uses: payload() returns ["value": Double].
        let v = JSONValue.from(["value": 1.0 as Double])
        guard case let .object(o) = v else { return XCTFail("expected object") }
        switch o["value"] {
        case .double(let d): XCTAssertEqual(d, 1.0)
        case .int(let i): XCTAssertEqual(i, 1)
        default: XCTFail("1.0 must stay numeric, got \(String(describing: o["value"]))")
        }
    }

    func testDoubleZeroFromSwiftDoubleStaysNumeric() {
        let v = JSONValue.from(["value": 0.0 as Double])
        guard case let .object(o) = v else { return XCTFail("expected object") }
        switch o["value"] {
        case .double(let d): XCTAssertEqual(d, 0.0)
        case .int(let i): XCTAssertEqual(i, 0)
        default: XCTFail("0.0 must stay numeric, got \(String(describing: o["value"]))")
        }
    }

    func testNonZeroNonOneNumericsUnaffected() {
        let obj = (try? JSONSerialization.jsonObject(with: Data(#"{"a":12,"b":12.5}"#.utf8))) as! [String: Any]
        let v = JSONValue.from(obj)
        guard case let .object(o) = v else { return XCTFail("expected object") }
        XCTAssertEqual(o["a"], .int(12))
        XCTAssertEqual(o["b"], .double(12.5))
    }

    func testGenuineBoolStaysBool() {
        // pass_fail responses carry a real JSON boolean and must remain boolean.
        let obj = (try? JSONSerialization.jsonObject(with: Data(#"{"passed":true,"other":false}"#.utf8))) as! [String: Any]
        let v = JSONValue.from(obj)
        guard case let .object(o) = v else { return XCTFail("expected object") }
        XCTAssertEqual(o["passed"], .bool(true), "real JSON true must stay bool(true)")
        XCTAssertEqual(o["other"], .bool(false), "real JSON false must stay bool(false)")
    }

    func testSwiftBoolLiteralStaysBool() {
        let v = JSONValue.from(["passed": true, "failed": false])
        guard case let .object(o) = v else { return XCTFail("expected object") }
        XCTAssertEqual(o["passed"], .bool(true))
        XCTAssertEqual(o["failed"], .bool(false))
    }

    func testNestedNumericInArrayNotCoerced() {
        let obj = (try? JSONSerialization.jsonObject(
            with: Data(#"{"results":[{"label":"a","passed":true},{"label":"b","value":1}]}"#.utf8))) as! [String: Any]
        let v = JSONValue.from(obj)
        guard case let .object(o) = v, case let .array(arr) = o["results"] else {
            return XCTFail("expected object/array")
        }
        guard case let .object(second) = arr[1] else { return XCTFail("expected object") }
        XCTAssertEqual(second["value"], .int(1))
        guard case let .object(first) = arr[0] else { return XCTFail("expected object") }
        XCTAssertEqual(first["passed"], .bool(true))
    }
}
