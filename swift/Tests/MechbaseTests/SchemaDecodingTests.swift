import XCTest
@testable import Mechbase

/// Every parity response type decodes the schema's complete sample and its minimal one (nullable
/// fields null, defaulted fields absent).
final class SchemaDecodingTests: XCTestCase {
    private func check<T: Decodable>(_ type: T.Type, _ schema: String, file: StaticString = #filePath, line: UInt = #line) {
        for (variant, fixtures) in [("full", Fixture.full), ("nulls", Fixture.nulls)] {
            do { _ = try JSONDecoder().decode(T.self, from: Data(fixtures[schema]!.utf8)) } catch {
                XCTFail("\(T.self) \(variant): \(error)", file: file, line: line)
            }
        }
    }

    func testParityModelsDecode() {
        check(Me.self, "MeOut")
        check(Overview.self, "OverviewOut")
        check(ActivityPage.self, "CursorPage_ActivityOut_")
        check(SearchResults.self, "SearchOut")
        check(RunningHours.self, "HoursOut")
        check(NotificationSettings.self, "NotificationSettingsOut")
        check(DashboardSummary.self, "DashboardSummaryOut")
        check(Dashboard.self, "DashboardOut")
        check(DashboardSection.self, "DashboardSectionOut")
        check(DashboardTileRef.self, "TileRefOut")
        check(ReadingAnalysis.self, "ReadingAnalysisOut")
        check(ProcessResult.self, "ProcessOut")
        check(CompareResult.self, "CompareOut")
        check(AssetTrend.self, "TrendOut")
        check(FaultRecord.self, "FaultRecordOut")
        check(BaselineResult.self, "BaselineOut")
        check(BaselinePreview.self, "BaselinePreviewOut")
        check(Mechbase.Measurement.self, "MeasurementOut")
        check(MeasurementPoint.self, "MeasurementPointOut")
        check(Finding.self, "FindingOut")
        check(FindingChoices.self, "FindingChoicesOut")
        check(BearingList.self, "BearingListOut")
        check(Bearing.self, "BearingOut")
        check(OffsetPage<ExecutionSummary>.self, "Page_ExecutionSummaryOut_")
        check(ExecutionReport.self, "ExecutionReportOut")
        check(ItemResponse.self, "ItemResponseOut")
        check(OffsetPage<NonConformity>.self, "Page_NonConformityOut_")
        check(Survey.self, "SurveyOut")
        check(FileAttachment.self, "FileOut")
        check(RouteDetail.self, "RouteDetail")
        check(Route.self, "RouteOut")
        check(RouteItem.self, "RouteItemOut")
        check(OffsetPage<ItemHistoryEntry>.self, "Page_ItemHistoryOut_")
        check(ChecklistResult.self, "ChecklistOut")
        check(Device.self, "DeviceOut")
        check(DeviceLookup.self, "DeviceLookupOut")
        check(GroupChannels.self, "GroupChannelsOut")
        check(PushDevice.self, "PushDeviceOut")
        check(ZoneDocument.self, "ZoneDocumentOut")
        check(ZonePhoto.self, "ZonePhotoOut")
    }
}
